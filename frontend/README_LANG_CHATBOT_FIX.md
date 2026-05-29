# Correctif langue + chatbot Agri-Botics

Correctifs inclus :

1. La sélection de langue ne dépend plus de `chatbot.js`.
   - Même si le chatbot est absent ou cassé, l'écran de choix de langue fonctionne.
   - La fonction `chooseLang()` est maintenant dans `js/i18n.js`.

2. L'interface est traduite en :
   - français ;
   - arabe ;
   - darija marocaine.

3. Le chatbot est non bloquant :
   - il répond localement en simulation ;
   - il essaie le backend en mode réel ;
   - si le backend ne répond pas, il utilise une réponse locale.

4. Les fichiers corrigés sont présents dans :
   - `frontend_simulation/`
   - `frontend_real_backend/`

Lancement conseillé :

```bash
cd frontend/frontend_simulation
python3 -m http.server 5500
```

Puis ouvrir :

```text
http://localhost:5500/agribotics_v5.html
```

Si l'ancien écran reste bloqué dans le navigateur, vider le cache :
- Ctrl + Shift + R
- ou ouvrir en navigation privée.
