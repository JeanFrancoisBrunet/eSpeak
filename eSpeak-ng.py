#!/usr/bin/env python3
# ===============================================================================
#  Studio TTS (Text To Speech) – eSpeak NG + MBROLA
#  Raspberry PI5 (16 Go RAM, SSD NVMe 256 Go, OS Bookworm)
#
#  Auteur  : Jean‑François BRUNET - JFBConseils - Avril 2026
# ===============================================================================

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import subprocess
import threading
import configparser
import PyPDF2
import os
from PIL import Image, ImageTk

# ---------------------------------------------------------
# CHEMINS DYNAMIQUES
# ---------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(BASE_DIR, "icons", "ESpeak_logo.png")
CONFIG_PATH = os.path.join(BASE_DIR, "config.ini")

# ---------------------------------------------------------
# UTILITAIRES
# ---------------------------------------------------------
def get_espeak_voices():
    """Retourne les voix eSpeak réellement utilisables avec -v."""
    voices = []
    base = "/usr/lib/aarch64-linux-gnu/espeak-ng-data/voices"

    if not os.path.isdir(base):
        return []

    for root, dirs, files in os.walk(base):
        for f in files:
            if f.startswith("."):
                continue
            rel = os.path.relpath(os.path.join(root, f), base)
            voice = rel.replace("\\", "/")
            voices.append(voice)

    return sorted(voices)

def get_mbrola_voices():
    """Retourne uniquement les voix MBROLA réellement installées."""
    voices = []
    path = "/usr/share/mbrola"

    if os.path.isdir(path):
        for f in os.listdir(path):
            if os.path.isdir(os.path.join(path, f)):
                voices.append(f)

    return sorted(voices)

def extract_pdf_text(path):
    """Extrait et nettoie le texte d'un PDF.

    Stratégie de recollement des lignes coupées :
    - Une ligne coupée par la mise en page ne se termine PAS par un signe de
      ponctuation finale (. ? ! : ;) ET la ligne suivante commence par une
      minuscule → on recolle sans saut de ligne.
    - Une ligne qui se termine par une ponctuation finale → fin de phrase,
      on vide le buffer dans cleaned.
    - Une ligne vide → fin de paragraphe (double saut).
    - Une ligne qui commence par § → nouveau paragraphe forcé.
    """
    PONCTUATION_FINALE = (".", "?", "!", ":", ";", "…")

    text = ""
    with open(path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

    lines = text.split("\n")
    cleaned = []
    buffer = ""

    def flush_buffer():
        nonlocal buffer
        if buffer:
            cleaned.append(buffer.strip())
            buffer = ""

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Ligne vide → fin de paragraphe
        if stripped == "":
            flush_buffer()
            continue

        # Nouveau paragraphe marqué par §
        if stripped.startswith("§"):
            flush_buffer()
            buffer = stripped
            continue

        # Accumulation dans le buffer
        if buffer:
            buffer += " " + stripped
        else:
            buffer = stripped

        # Fin de phrase détectée → on vide
        if stripped.endswith(PONCTUATION_FINALE):
            flush_buffer()
            continue

        # Ligne coupée sans ponctuation finale : on ne vide le buffer que
        # si la ligne suivante est vide ou commence par §.
        # Une majuscule seule ne suffit PAS à couper :
        # ce peut être un nom propre au milieu d'une phrase.
        next_stripped = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if next_stripped == "" or next_stripped.startswith("§"):
            flush_buffer()
        # Sinon → coupure de mise en page, on continue d'accumuler

    flush_buffer()

    return "\n\n".join(cleaned)

# ---------------------------------------------------------
# PERSISTANCE DE LA CONFIGURATION
# ---------------------------------------------------------
def load_config():
    """Charge les préférences sauvegardées, ou retourne les valeurs par défaut."""
    config = configparser.ConfigParser()
    defaults = {
        "lang": "Français",
        "voice": "[MBROLA] mb-fr7",
        "speed": "105",
        "pitch": "30",
        "volume": "50",
        "pause": "True",
    }
    if os.path.exists(CONFIG_PATH):
        config.read(CONFIG_PATH, encoding="utf-8")
        if "TTS" in config:
            for key in defaults:
                if key in config["TTS"]:
                    defaults[key] = config["TTS"][key]
    return defaults


def save_config(lang, voice, speed, pitch, volume, pause):
    """Sauvegarde les préférences actuelles dans config.ini."""
    config = configparser.ConfigParser()
    config["TTS"] = {
        "lang": lang,
        "voice": voice,
        "speed": str(speed),
        "pitch": str(pitch),
        "volume": str(volume),
        "pause": str(pause),
    }
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        config.write(f)

# ---------------------------------------------------------
# LECTURE ASYNCHRONE – thread-safe
# ---------------------------------------------------------
current_process = None
process_lock = threading.Lock()

def speak_async(cmd, on_done=None):
    """Lance espeak-ng dans un sous-processus et notifie on_done à la fin."""
    global current_process
    try:
        proc = subprocess.Popen(cmd)
        with process_lock:
            current_process = proc
        proc.wait()
    finally:
        with process_lock:
            current_process = None
        if on_done:
            on_done()

def stop_speech():
    """Arrête proprement la lecture en cours."""
    global current_process
    with process_lock:
        if current_process:
            current_process.terminate()
            current_process = None

# ---------------------------------------------------------
# SPLASH SCREEN
# ---------------------------------------------------------
class SplashScreen(tk.Toplevel):
    def __init__(self, root, logo_path):
        super().__init__(root)

        self.overrideredirect(True)
        self.configure(bg="#222222")

        try:
            img = Image.open(logo_path)
            img = img.resize((120, 120), Image.LANCZOS)
            self.logo = ImageTk.PhotoImage(img)
        except Exception:
            self.logo = None

        width, height = 300, 250
        x = (self.winfo_screenwidth() - width) // 2
        y = (self.winfo_screenheight() - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")

        frame = tk.Frame(self, bg="#222222")
        frame.pack(expand=True)

        if self.logo:
            tk.Label(frame, image=self.logo, bg="#222222").pack(pady=10)

        tk.Label(frame, text="Chargement du Studio TTS…",
                 fg="white", bg="#222222",
                 font=("Arial", 12)).pack(pady=10)

        self.update()

# ---------------------------------------------------------
# APPLICATION PRINCIPALE
# ---------------------------------------------------------
class TTSApp:
    def __init__(self, root):
        self.root = root
        root.title("Studio – eSpeak NG & MBROLA")
        root.configure(bg="#222222")

        fg = "#ffffff"
        bg = "#222222"

        # Chargement des préférences sauvegardées
        prefs = load_config()

        # Variables de l'interface
        self.lang_var   = tk.StringVar()
        self.voice_var  = tk.StringVar()
        self.speed_var  = tk.IntVar(value=int(prefs["speed"]))
        self.pitch_var  = tk.IntVar(value=int(prefs["pitch"]))
        self.volume_var = tk.IntVar(value=int(prefs["volume"]))
        self.pause_var  = tk.BooleanVar(value=prefs["pause"].lower() == "true")

        # Détection des voix disponibles
        espeak = get_espeak_voices()
        mbrola = get_mbrola_voices()

        def detect_available_languages(espeak_voices):
            langs = {}
            for v in espeak_voices:
                base = os.path.basename(v)
                short = base.split("-")[0]
                if len(short) == 2:
                    langs[short] = True
            return sorted(langs.keys())

        available_langs = detect_available_languages(espeak)

        LANG_LABELS = {
            "fr": "Français",   "en": "Anglais",    "de": "Allemand",
            "es": "Espagnol",   "it": "Italien",     "pt": "Portugais",
            "nl": "Néerlandais","fi": "Finnois",     "hu": "Hongrois",
            "pl": "Polonais",   "cs": "Tchèque",     "da": "Danois",
            "et": "Estonien",   "lv": "Letton",      "lt": "Lituanien",
            "mk": "Macédonien", "no": "Norvégien",   "bg": "Bulgare",
            "hr": "Croate",     "ga": "Gaélique",    "cy": "Gallois",
            "an": "Aragonais",  "bs": "Bosniaque",   "ca": "Catalan",
            "el": "Grec",       "is": "Islandais",
        }
        LANG_LABELS = {k: v for k, v in LANG_LABELS.items() if k in available_langs}

        self.LANG_LABELS = LANG_LABELS
        self.lang_codes  = list(LANG_LABELS.keys())
        lang_labels      = list(LANG_LABELS.values())

        # Dictionnaire langue → voix disponibles
        self.voices_by_lang = {lang: [] for lang in LANG_LABELS}

        for v in espeak:
            base  = os.path.basename(v)
            short = base.split("-")[0]
            if short in self.voices_by_lang:
                self.voices_by_lang[short].append(f"[eSpeak] {v}")

        for v in mbrola:
            short = v[:2]
            if short in self.voices_by_lang:
                self.voices_by_lang[short].append(f"[MBROLA] mb-{v}")

        # ---------------------------------------------------------
        # LOGO
        # ---------------------------------------------------------
        try:
            img = Image.open(LOGO_PATH)
            img = img.resize((150, 80), Image.LANCZOS)
            self.logo_image = ImageTk.PhotoImage(img)
        except Exception as e:
            print("Erreur chargement logo eSpeak :", e)
            self.logo_image = None

        # ---------------------------------------------------------
        # INTERFACE
        # ---------------------------------------------------------
        top = tk.Frame(root, bg=bg)
        top.pack(pady=10)

        if self.logo_image:
            tk.Label(top, image=self.logo_image, bg=bg).grid(row=0, column=0, rowspan=2, padx=10)

        tk.Label(top, text="Langue :", fg=fg, bg=bg).grid(row=0, column=1, padx=10)
        self.lang_menu = ttk.Combobox(top, textvariable=self.lang_var,
                                      values=lang_labels, state="readonly")
        self.lang_menu.grid(row=0, column=2)
        self.lang_menu.bind("<<ComboboxSelected>>", self.update_voice_menu)

        tk.Label(top, text="Voix :", fg=fg, bg=bg).grid(row=1, column=1, padx=10)
        self.voice_menu = ttk.Combobox(top, textvariable=self.voice_var, state="readonly")
        self.voice_menu.grid(row=1, column=2)

        # Restauration de la langue sauvegardée
        saved_lang = prefs["lang"]
        if saved_lang in lang_labels:
            self.lang_var.set(saved_lang)
            self.lang_menu.current(lang_labels.index(saved_lang))
        else:
            self.lang_var.set("Français")
            if "Français" in lang_labels:
                self.lang_menu.current(lang_labels.index("Français"))

        self.update_voice_menu()

        # Restauration de la voix sauvegardée
        saved_voice = prefs["voice"]
        voices = self.voice_menu["values"]
        if saved_voice in voices:
            self.voice_var.set(saved_voice)
        elif voices:
            self.voice_var.set(voices[0])

        tk.Checkbutton(top, text="Pauses entre les mots",
                       variable=self.pause_var, fg=fg, bg=bg,
                       selectcolor=bg).grid(row=2, column=2, padx=10, pady=10, sticky="w")

        # Sliders
        sliders = tk.Frame(root, bg=bg)
        sliders.pack(pady=10)

        tk.Label(sliders, text="Vitesse (mots/min)", fg=fg, bg=bg).grid(row=0, column=0, padx=20)
        tk.Scale(sliders, from_=80, to=250, orient="horizontal",
                 variable=self.speed_var, bg=bg, fg=fg).grid(row=1, column=0, padx=20)

        tk.Label(sliders, text="Pitch", fg=fg, bg=bg).grid(row=0, column=1, padx=20)
        tk.Scale(sliders, from_=0, to=99, orient="horizontal",
                 variable=self.pitch_var, bg=bg, fg=fg).grid(row=1, column=1, padx=20)

        tk.Label(sliders, text="Volume (%)", fg=fg, bg=bg).grid(row=0, column=2, padx=20)
        tk.Scale(sliders, from_=0, to=200, orient="horizontal",
                 variable=self.volume_var, bg=bg, fg=fg).grid(row=1, column=2, padx=20)

        # Boutons d'action
        actions = tk.Frame(root, bg=bg)
        actions.pack(pady=10)

        self.btn_lire = tk.Button(actions, text="▶  Lire", command=self.speak)
        self.btn_lire.pack(side="left", padx=10)

        tk.Button(actions, text="¶  Lire Paragraphe",
                  command=self.speak_paragraph).pack(side="left", padx=10)
        tk.Button(actions, text="■  Stop",
                  command=stop_speech).pack(side="left", padx=10)
        tk.Button(actions, text="💾  Enregistrer WAV",
                  command=self.save_wav).pack(side="left", padx=10)

        # Zone de texte
        self.text_box = tk.Text(root, height=15, width=80, bg="#333333", fg="#ffffff")
        self.text_box.pack(pady=10)

        self.char_label = tk.Label(root, text="0 caractères", fg=fg, bg=bg)
        self.char_label.pack()
        self.text_box.bind("<KeyRelease>", self.update_char_count)

        # Boutons bas
        bottom = tk.Frame(root, bg=bg)
        bottom.pack(pady=10)

        tk.Button(bottom, text="Charger TXT",
                  command=self.load_txt).pack(side="left", padx=10)
        tk.Button(bottom, text="Charger PDF",
                  command=self.load_pdf).pack(side="left", padx=10)
        tk.Button(bottom, text="Effacer texte",
                  command=self.clear_text).pack(side="left", padx=10)

        # Sauvegarde des prefs à la fermeture
        root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ---------------------------------------------------------
    # CONSTRUCTION DE LA COMMANDE ESPEAK (factorisée)
    # ---------------------------------------------------------
    def build_cmd(self, text, output_file=None):
        raw_voice = self.voice_var.get()
        if "] " not in raw_voice:
            return None
        voice_clean = raw_voice.split("] ", 1)[1]

        cmd = [
            "espeak-ng",
            f"-v{voice_clean}",
            f"-s{self.speed_var.get()}",
            f"-p{self.pitch_var.get()}",
            f"-a{self.volume_var.get()}",
        ]
        if output_file:
            cmd += ["-w", output_file]
        cmd.append(text)
        return cmd

    # ---------------------------------------------------------
    # VALIDATION COMMUNE
    # ---------------------------------------------------------
    def _get_validated_text(self):
        text = self.text_box.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("Attention", "Aucun texte à lire.")
            return None
        return self.prepare_text(text)

    def _check_voice(self):
        if not self.voice_var.get():
            messagebox.showwarning("Attention", "Aucune voix sélectionnée.")
            return False
        return True

    # ---------------------------------------------------------
    # FONCTIONS
    # ---------------------------------------------------------
    def update_voice_menu(self, event=None):
        index = self.lang_menu.current()
        if index < 0:
            self.voice_menu["values"] = []
            self.voice_var.set("")
            return
        lang_code = self.lang_codes[index]
        voices = self.voices_by_lang.get(lang_code, [])
        self.voice_menu["values"] = voices
        self.voice_var.set(voices[0] if voices else "")

    def update_char_count(self, event=None):
        text = self.text_box.get("1.0", tk.END)
        self.char_label.config(text=f"{len(text.strip())} caractères")

    def prepare_text(self, text):
        if self.pause_var.get():
            text = text.replace(" ", "  ")
        return text

    def _set_reading_state(self, reading: bool):
        if reading:
            self.btn_lire.config(text="⏳ Lecture…", state="disabled")
        else:
            self.btn_lire.config(text="▶  Lire", state="normal")

    def speak(self):
        text = self._get_validated_text()
        if text is None:
            return
        if not self._check_voice():
            return

        cmd = self.build_cmd(text)
        if cmd is None:
            return

        # Arrêt de toute lecture en cours avant d'en démarrer une nouvelle
        stop_speech()

        self._set_reading_state(True)

        def on_done():
            self.root.after(0, lambda: self._set_reading_state(False))

        threading.Thread(target=speak_async, args=(cmd,),
                         kwargs={"on_done": on_done}, daemon=True).start()

    def speak_paragraph(self):
        text = self.text_box.get("1.0", tk.END)

        lines = text.split("\n")
        paragraphs = []
        current = []

        for line in lines:
            stripped = line.strip()
            if stripped == "" or stripped.startswith("§") or stripped.endswith("."):
                if stripped != "":
                    current.append(stripped)
                if current:
                    paragraphs.append(" ".join(current).strip())
                    current = []
            else:
                current.append(stripped)

        if current:
            paragraphs.append(" ".join(current).strip())

        cursor_line = int(self.text_box.index("insert").split(".")[0])
        line_count  = 1
        target_index = 0

        for i, p in enumerate(paragraphs):
            p_lines = p.count(" ") // 12 + 1
            if line_count + p_lines > cursor_line:
                target_index = i
                break
            line_count += p_lines

        if target_index >= len(paragraphs):
            return

        if not self._check_voice():
            return

        # Arrêt de toute lecture en cours avant d'en démarrer une nouvelle
        stop_speech()

        paragraph = self.prepare_text(paragraphs[target_index])
        cmd = self.build_cmd(paragraph)
        if cmd is None:
            return

        threading.Thread(target=speak_async, args=(cmd,), daemon=True).start()

    def save_wav(self):
        text = self.text_box.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("Attention", "Aucun texte à enregistrer.")
            return

        filename = filedialog.asksaveasfilename(
            defaultextension=".wav",
            filetypes=[("Fichier WAV", "*.wav")],
            initialfile="lecture.wav",
            initialdir=BASE_DIR,
        )
        if not filename:
            return

        if not self._check_voice():
            return

        text = self.prepare_text(text)
        cmd  = self.build_cmd(text, output_file=filename)
        if cmd is None:
            return

        def do_save():
            subprocess.run(cmd)
            # Retour dans le thread principal pour afficher la boîte de dialogue
            self.root.after(0, lambda: messagebox.showinfo(
                "Enregistré", f"Fichier sauvegardé :\n{filename}"
            ))

        threading.Thread(target=do_save, daemon=True).start()

    def load_txt(self):
        file = filedialog.askopenfilename(
            initialdir=BASE_DIR,
            filetypes=[("Text files", "*.txt")]
        )
        if not file:
            return
        with open(file, "r", encoding="utf-8") as f:
            self.text_box.delete("1.0", tk.END)
            self.text_box.insert(tk.END, f.read())
        self.update_char_count()

    def load_pdf(self):
        file = filedialog.askopenfilename(
            initialdir=BASE_DIR,
            filetypes=[("PDF files", "*.pdf")]
        )
        if not file:
            return
        text = extract_pdf_text(file)
        self.text_box.delete("1.0", tk.END)
        self.text_box.insert(tk.END, text)
        self.update_char_count()

    def clear_text(self):
        self.text_box.delete("1.0", tk.END)
        self.update_char_count()

    def on_close(self):
        """Sauvegarde les préférences et ferme proprement."""
        stop_speech()
        save_config(
            lang   = self.lang_var.get(),
            voice  = self.voice_var.get(),
            speed  = self.speed_var.get(),
            pitch  = self.pitch_var.get(),
            volume = self.volume_var.get(),
            pause  = self.pause_var.get(),
        )
        self.root.destroy()

# ---------------------------------------------------------
# LANCEMENT
# ---------------------------------------------------------
root = tk.Tk()
root.withdraw()

splash = SplashScreen(root, LOGO_PATH)

def start_app():
    splash.destroy()
    root.deiconify()
    TTSApp(root)

root.after(1500, start_app)
root.mainloop()
