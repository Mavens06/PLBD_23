# Déploiement sur la Raspberry Pi (démarrage automatique au boot)

Pour un **vrai prototype**, le backend et le robot doivent démarrer tout seuls à
l'allumage, sans `start_demo.sh` lancé à la main. Ces deux services systemd s'en
chargent et se relancent en cas de crash.

## 1. Pré-requis sur la Pi

```bash
cd ~/PLBD
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt      # installe aussi les libs robot (ARM)
cp backend/.env.example .env                      # puis renseigner GEMINI_API_KEY
```

Donner à l'utilisateur l'accès au matériel (I2C pour le PCA9685, série pour le RS485) :

```bash
sudo usermod -aG gpio,i2c,dialout "$USER"
sudo raspi-config    # activer I2C (Interface Options → I2C)
# se déconnecter/reconnecter pour appliquer les groupes
```

Vérifier le câblage avant d'activer les services :

```bash
APP_MODE=hardware ./.venv/bin/python -m raspberry_pi.hardware_test --test all
```

## 2. Installer les services

Adapter `User=` et les chemins (`/home/pi/PLBD`) dans les deux fichiers `.service`
si votre utilisateur ou dossier diffèrent, puis :

```bash
sudo cp deploy/agribotics-backend.service deploy/agribotics-robot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now agribotics-backend agribotics-robot
```

## 3. Superviser

```bash
systemctl status agribotics-backend agribotics-robot
journalctl -u agribotics-robot -f       # logs du robot en direct
curl http://localhost:8000/health
curl http://localhost:8000/api/status
```

## 4. Résilience réseau

Si le backend est momentanément injoignable pendant une mission, le robot
**ne perd aucune mesure** : elles sont mises en file sur le disque
(`AGRIBOTICS_ROBOT_OUTBOX`, défaut `.agribotics/robot_outbox.jsonl`) et
retransmises automatiquement au début de la mission suivante.

## 5. Mettre à jour / arrêter

```bash
sudo systemctl restart agribotics-backend agribotics-robot   # après un git pull
sudo systemctl disable --now agribotics-robot                # arrêter le robot
```
