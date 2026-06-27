# Déploiement sur la Raspberry Pi (démarrage automatique au boot)

Pour un **vrai prototype**, le backend, le robot et le tunnel public doivent
démarrer tout seuls à l'allumage, sans rien lancer à la main. Des services
systemd s'en chargent et se relancent en cas de crash.

> **Le backend sert AUSSI le frontend** (à `/`). Il n'y a donc rien d'autre à
> démarrer : backend + robot + tunnel suffisent.

## ⚡ Installation en une commande (recommandé)

```bash
cd ~/PLBD
sudo ./deploy/install.sh            # robot réel (APP_MODE=hardware)
# sudo APP_MODE=mock ./deploy/install.sh   # PC de dev sans matériel
```

`install.sh` génère les 3 services (backend, robot, tunnel) avec **votre
utilisateur et vos chemins réels**, les active au boot et les démarre. Après ça,
**le seul geste à chaque connexion** :

```bash
./deploy/link.sh           # affiche le lien public du robot
./deploy/link.sh --new     # en régénère un nouveau (redémarre le tunnel)
```

Pré-requis du tunnel : installer **cloudflared** une fois
(`https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/`).
Sans lui, le service tunnel reste inactif mais backend + robot tournent quand même.

---

Le reste de ce document détaille la **méthode manuelle** (équivalente, si vous
préférez ne pas utiliser `install.sh`).

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
sudo cp deploy/agribotics-backend.service deploy/agribotics-robot.service \
        deploy/agribotics-tunnel.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now agribotics-backend agribotics-robot agribotics-tunnel
```

Le service **tunnel** lance `deploy/tunnel.sh` (cloudflared) et écrit l'URL
publique dans `.agribotics/tunnel_url.txt`. Récupérez-la avec `./deploy/link.sh`.

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
./deploy/link.sh --new                                       # nouveau lien public
```
