# 🌳 ForestWatch Togo : Land Cover & Deforestation AI Monitor

Un système d'intelligence artificielle analysant les images satellites multispectrales (Sentinel-2) via Google Earth Engine pour classifier l'occupation des sols et surveiller l'évolution du couvert forestier au Togo. Pensez de l'extraction des données (Data Engineering) jusqu'au déploiement du modèle (AI Engineering), en passant par l'analyse géospatiale (Data Analysis).

**Dataset constitué** : [Lien vers Google Drive](https://drive.google.com/file/d/1q_eiRnCmQ5TSvsFPq1zPfdpX3ipYQkkC/view?usp=sharing)

---

## Objectif du projet
Fournir un outil robuste et automatisable permettant de détecter les différentes classes d'occupations des sols, avec un focus majeur sur la télédétection forestière.

## État de l'art du projet (Phases accomplies)

### 1. Data Collection & Engineering (Google Earth Engine)
- Extraction de données satellitaires **Sentinel-2 Level-2A** sur des coordonnées précises au Togo.
- Calcul de **37 features géospatiales et radiométriques** pour 21 000 pixels (sans données manquantes) comprenant :
  - **Bandes brutes** (Visible, NIR, SWIR).
  - **Indices spectraux** (NDVI, NDWI, NDBI, etc.) adaptés à la végétation, l'eau et l'urbain.
  - **Textures GLCM** (Variance, Contraste, ASM, Entropie) pour cartographier la complexité structurelle des paysages.

### 2. Modélisation et Optimisation (Machine Learning)
L'algorithme choisi est le **Random Forest**, idéal pour son interprétabilité radiométrique et sa robustesse. Tout le processus (Processing, Tuning) est documenté dans notre [`modeling.ipynb`](./notebooks/modeling.ipynb) :
- **Ingénierie des caractéristiques** : Suppression des variables ultra-corrélées mathématiquement (Moyennes, Variances, Entropie) au profit de leurs paires structurales (Valeurs Brutes, Contraste, ASM).
- **Adaptation au "Plafond radiométrique"** : Fusion stratégique des classes ambigües ("Buissons" et "Savanes") en une classe "Végétation Mixte" (passage de 7 à 6 classes pour s'adapter à la limite de la résolution à 10 m).
- **Optimisation** : GridSearchCV avec optimisation de la métrique `F1-macro` pour rééquilibrer numériquement le modèle et forcer la détection optimale de la signature "Forêt" face à une classe floristique majoritaire écrasante.

### Performances du Modèle Final
Le modèle optimal obtenu assure le meilleur équilibre Précision/Rappel pour notre cible métier stricte (les forêts).
- **Exactitude Globale (Accuracy)** : ~76.2%
- **F1-Macro** : 0.77
- **Classe "Forêt"** : Précision 0.77 / Rappel 0.69 / F1-score 0.72

---

## 3. MLOps & API Engineering (Production)
Le pipeline d'inférence a été industrialisé, sécurisé et conteneurisé.
- **Backend REST** : Microservice propulsé par **FastAPI** & **Uvicorn**.
- **Artifact Decoupling (Hugging Face)** : L'espace de travail est *stateless*. Si les poids (`.joblib`) sont absents localement, le kernel d'inférence récupère dynamiquement les artefacts de production depuis le Hub Hugging Face (via [`huggingface_hub`](https://huggingface.co/kjd-dktech/forestwatch-tg)).
- **Sécurité & Guardrails** : Endpoints protégés par `X-API-Key`. Payload limités à 50MB. Validation stricte des features (calcul à la volée des indices spectraux si les bandes brutes sont fournies et rejet automatique des inputs invalides).
- **Conteneurisation (Docker Hub)** : L'API est packagée et distribuée sous la forme d'une image cloud-native allégée ([`kjddktech/forestwatchtg-api:latest`](https://hub.docker.com/r/kjddktech/forestwatchtg-api:latest)).

---

## Déploiement en Production (Quickstart)

L'environnement d'exécution est entièrement isolé. L'utilisateur final n'a plus besoin du code source, seul le proxy de configuration Docker est requis.

### 1. Variables d'environnement
Créez un fichier [`.env`](./.env.example) dans le dossier de déploiement :
```env
API_KEY=votre_cle_api_secrete_ici
HF_MODEL_REPO_ID=kjd-dktech/forestwatch-tg
HF_TOKEN=
```

### 2. Lancement du Conteneur
Utilisez le [`docker-compose.prod.yml`](./docker-compose.prod.yml) (disponible dans la repository) :
```bash
docker compose -f docker-compose.prod.yml up -d
```

L'API bootera sur le port `8000`.
> 💡 **Tip :** La documentation interactive Swagger est auto-générée et testable sur `http://localhost:8000/docs`.

---

## � Architecture du Code Source

Pour les développeurs et curieux qui souhaitent explorer le repository :

- 📁 **[`api/`](./api/)** : Couche serveur (Routing HTTP).
  - 📄 [`main.py`](./api/main.py) : Définition de l'application FastAPI, sécurité (`X-API-Key`), parsing GeoJSON et limites d'upload.
- 📁 **[`src/`](./src/)** : Moteur d'inférence ML.
  - 📄 [`predict.py`](./src/predict.py) : Classe `LandCoverPredictor`. Gère le singleton du modèle, la validation, et le pull dynamique Hugging Face.
  - 📄 [`earth_engine_formulas.py`](./src/earth_engine_formulas.py) : Fonctions de calcul géospatial à la volée (NDVI, NDWI...) et guardrails GLCM.
- 📁 **[`notebooks/`](./notebooks/)** : Historique Data Science (R&D).
  - 📄 [`data_collection.ipynb`](./notebooks/data_collection.ipynb) : Logique d'extraction via Google Earth Engine.
  - 📄 [`collection_processing.ipynb`](./notebooks/collection_processing.ipynb) : Traitement de la collecte et création finale du dataset CSV.
  - 📄 [`modeling.ipynb`](./notebooks/modeling.ipynb) : Phase d'EDA, Feature Engineering et GridSearch.
  - 📄 [`model_export_pipeline.ipynb`](./notebooks/model_export_pipeline.ipynb) : Pipeline pur (Clean Build) générant les artefacts de production.
- ⚙️ **Infrastructure & Ops** :
  - 📄 [`Dockerfile`](./Dockerfile) & 📄 [`docker-compose.prod.yml`](./docker-compose.prod.yml) : Fichiers de conteneurisation.
  - 📄 [`requirements-prod.txt`](./requirements-prod.txt) : Dépendances allégées pour l'environnement d'exécution de l'API.

---

## Prochaines étapes
* **🔜 Interface Web (Démo / UI)** : Création d’un front-end interactif (Dashboard) interfaçant l'API pour permettre un upload utilisateur simplifié, et la projection visuelle des cartes prédictives spatiales.