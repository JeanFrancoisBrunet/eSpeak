# eSpeak — Studio TTS

Studio de synthèse vocale (Text-To-Speech) sur Raspberry Pi 5, basé sur **eSpeak NG** et les voix **MBROLA**. Interface graphique Tkinter permettant de lire à voix haute du texte saisi, chargé depuis un fichier `.txt`, ou extrait d'un `.pdf`.

## Fonctionnement

### Voix et langues
- Détection automatique des voix **eSpeak NG** installées (`espeak-ng-data/voices`) et des voix **MBROLA** installées (`/usr/share/mbrola`).
- Les langues disponibles sont déduites des voix eSpeak effectivement présentes sur le système (aucune langue codée en dur qui ne serait pas installée).
- Sélection en cascade : choix de la langue, puis de la voix correspondante (eSpeak ou MBROLA) dans un second menu déroulant.

### Réglages de la voix
| Réglage               | Plage             | Description                                                           |
|---                    |---                |---                                                                    |
| Vitesse               | 80 – 250 mots/min | Débit de la synthèse                                                  |
| Pitch                 | 0 – 99            | Hauteur de la voix                                                    |
| Volume                | 0 – 200 %         | Amplitude du son                                                      |
| Pauses entre les mots | Oui / Non         | Insère un espacement supplémentaire pour ralentir/détacher la diction |

Les réglages et la voix choisie sont **sauvegardés automatiquement** à la fermeture dans `config.ini` et rechargés au prochain lancement.

### Import de texte
- **Charger TXT** : ouvre un fichier `.txt` et en affiche le contenu dans la zone de texte.
- **Charger PDF** : extrait le texte d'un PDF via **PyPDF2**, avec un recollement intelligent des lignes coupées par la mise en page :
  - une ligne qui ne se termine pas par une ponctuation finale (`. ? ! : ; …`) est recollée à la suivante ;
  - une ligne vide marque une fin de paragraphe ;
  - un repère `§` en début de ligne force un nouveau paragraphe.

### Lecture
- **▶ Lire** : lit l'intégralité du texte de la zone.
- **¶ Lire Paragraphe** : identifie le paragraphe où se trouve le curseur (découpage sur les lignes vides, les `§`, ou une ponctuation de fin de phrase) et ne lit que celui-ci.
- **■ Stop** : interrompt la lecture en cours (le processus `espeak-ng` est arrêté proprement).
- **💾 Enregistrer WAV** : génère un fichier audio `.wav` du texte au lieu de le lire directement.
- Lecture asynchrone dans un thread dédié : l'interface reste réactive pendant la synthèse.

## Lancement
```bash
python3 eSpeak-ng.py
```

## Dépendances
Système :
```bash
sudo apt install espeak-ng mbrola mbrola-fr7
```
*(remplacer `mbrola-fr7` par la ou les voix MBROLA souhaitées)*

Python :
```bash
pip install pypdf2 pillow --break-system-packages
```

## Configuration (`config.ini`)
Générée et mise à jour automatiquement par l'application ; exemple :
```ini
[TTS]
lang = Français
voice = [MBROLA] mb-fr7
speed = 115
pitch = 40
volume = 120
pause = True
```

## Structure du dépôt
```
eSpeak/
├── eSpeak-ng.py       # Application principale (Tkinter)
├── config.ini         # Préférences utilisateur (généré à l'exécution)
└── icons/             # Logo utilisé par le splash screen et l'interface (ESpeak_logo.png, non inclus ici)
```

> `config.ini` reflète les préférences propres à chaque installation (voix, vitesse, pitch, volume) ; à exclure du suivi de version ou à ne fournir qu'à titre d'exemple.

## Prérequis
- Raspberry Pi 5 (ou toute distribution Linux) avec `espeak-ng` et les voix `mbrola` installées
- Python 3
- `python3-tk`

## Auteur
Jean-François BRUNET - JFBConseils - Juillet 2026
