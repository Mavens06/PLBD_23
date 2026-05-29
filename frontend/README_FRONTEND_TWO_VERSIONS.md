# Frontend Agri-Botics — deux versions

Ce dossier conserve la même structure que le fichier fourni :

- `frontend_real_backend/` : version prévue pour le robot réel + backend/ML.
- `frontend_simulation/` : version de démonstration locale, sans robot ni backend.

## Corrections appliquées

- Style visuel conservé.
- Page Carte conservée uniquement comme affichage dynamique des mesures.
- La coloration de la carte dépend uniquement des valeurs captées : humidité, pH, température.
- Suppression du mode/actions sur la carte.
- Section Conseils simplifiée : uniquement zone par zone.
- Suppression de la section "Parcelle entière".
- Pour cultiver une seule culture partout : choisir une culture puis cliquer sur "Appliquer partout".
- Pour des cultures différentes : cliquer sur une zone et choisir sa culture.
- Recommandations plus quantitatives et courtes : eau en mm/L·m², chaux en g/m², compost en kg/m², fertilisation organique indicative.

## Lancement simulation

```bash
cd frontend_simulation
python3 -m http.server 5501
```

Ouvrir : `http://localhost:5501/agribotics_v5.html`

## Lancement version réelle

```bash
cd frontend_real_backend
python3 -m http.server 5500
```

Ouvrir : `http://localhost:5500/agribotics_v5.html`

