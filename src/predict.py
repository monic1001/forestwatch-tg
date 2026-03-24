import pandas as pd
import numpy as np
import joblib
import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


# -------------------------------------------------------------------#
# ------------ Configuration des chemins et imports -----------------#
# -------------------------------------------------------------------#
CURRENT_FILE_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_FILE_DIR.parent
LOG_DIR = REPO_ROOT / "api" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# --- Configuration du Logger ---
logger = logging.getLogger("Predictor")
logger.setLevel(logging.INFO)
if not logger.handlers:
    # Handler Fichier
    fh = RotatingFileHandler(LOG_DIR / "predict.log", maxBytes=5*1024*1024, backupCount=2)
    fh.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(fh)
    # Handler Console
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(ch)

# Ajout du root au path pour permettre les imports absolus
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

# Import dynamique des formules
from src.earth_engine_formulas import calculate_indices, has_minimum_glcm_features

class LandCoverPredictor:
    """
    Classe d'inférence pour la classification d'occupation des sols.
    Assure le chargement du modèle, l'application stricte du pipeline
    de prétraitement, et le mapping des prédictions.
    """
    def __init__(self, 
                 model_path=None, 
                 scaler_path=None):
        """
        Initialise le prédicteur en chargeant le modèle et le scaler sauvegardés.
        """
        model_path = model_path or REPO_ROOT / "models" / "rfc_production_v1.joblib"
        scaler_path = scaler_path or REPO_ROOT / "models" / "scaler_production.joblib"

        # Mapping explicite des classes issues de la modélisation à 6 classes
        self.class_names = {
            0: 'Forêt', 
            1: 'Savanes/Buissons', 
            2: 'Cultures', 
            3: 'Urbain', 
            4: 'Sols nus', 
            5: 'Eau'
        }
        
        # Chargement des artefacts persistants
        try:
            self.model = joblib.load(model_path)
            self.scaler = joblib.load(scaler_path)
            logger.info(f"✅ Modèle et Scaler chargés avec succès depuis {Path(model_path).parent}.")
        except FileNotFoundError as e:
            logger.error(f"Fichier artefact manquant.\nErreur: {e}")
            raise RuntimeError(f"Fichier artefact manquant.\nErreur: {e}")

        # -------------------------------------------------------------------#
        # ------------------- Pipeline de suppression -----------------------#
        # -------------------------------------------------------------------#
        # 1. Colonnes inutiles ou d'identification
        cols_to_drop_sys = ['system:index', '.geo', 'longitude', 'latitude', 'landcover']
        
        # 2. Colonnes hautement corrélées (> 0.95) identifiées lors de l'EDA
        cols_to_drop_corr = [
            'NDWI_mean', 'NDVI_mean', 'B4_mean', 
            'NDWI_var', 'NDVI_var',               
            'B12_ent', 'NDWI_ent', 'B8_ent', 'NDVI_ent', 'NDBI_ent'
        ]
        
        # 3. Colonnes à faible importance (< 0.02) éliminées avant GridSearchCV
        cols_to_drop_importance = ['NDBI_asm', 'NDWI_asm', 'NDVI_asm', 'B12_asm']
        
        # Concaténation de la règle de filtre
        self.all_cols_to_drop = cols_to_drop_sys + cols_to_drop_corr + cols_to_drop_importance
        
        # Sauvegarde de l'ordre exact et des noms des features attendues par le scaler
        self.expected_features = self.scaler.feature_names_in_

    def preprocess(self, df):
        """
        Applique les mêmes transformations que lors de l'entraînement 
        (suppression des features, réagencement, mise à l'échelle).
        """
        df_clean = df.copy()

        # --- Intégration de l'option C (Calcul dynamique) ---
        indices_spectraux = ['NDVI', 'NDWI', 'NDBI']
        if any(idx not in df_clean.columns for idx in indices_spectraux):
            logger.info("Indices spectraux manquants. Tentative de calcul dynamique via les bandes brutes.")
            try:
                df_clean = calculate_indices(df_clean)
                logger.info("✅ Indices spectraux calculés avec succès.")
            except ValueError as e:
                logger.warning(f"Impossible de calculer les indices dynamiquement : {e}")

        # --- Validation stricte (GLCM) ---
        is_valid, msg = has_minimum_glcm_features(df_clean, self.expected_features)
        if not is_valid:
            logger.error(f"Rejet strict : {msg}")
            raise ValueError(msg)
        
        # Vérifier si on a bien TOUTES les features requises au final
        missing_features = [f for f in self.expected_features if f not in df_clean.columns]
        if missing_features:
            logger.error(f"Colonnes manquantes finales : {missing_features}")
            raise ValueError(f"Colonnes manquantes dans les données fournies (après calculs) : {missing_features}")
            
        # Ne conserver QUE les features attendues par le modèle, et dans LE BON ORDRE
        df_clean = df_clean[self.expected_features]
            
        # Application de la standardisation
        # scikit-learn appliquera le transform en suivant scrupuleusement l'ordre des colonnes
        data_scaled = self.scaler.transform(df_clean)
        
        return data_scaled

    def predict(self, data):
        """
        Fait une prédiction sur le jeu de données.
        `data` peut être un chemin vers un fichier CSV ou un DataFrame Pandas.
        """
        if isinstance(data, (str, Path)):
            data_path = Path(data)
            if not data_path.exists():
                raise FileNotFoundError(f"Le fichier {data_path} est introuvable.")
            df = pd.read_csv(data_path)
        elif isinstance(data, pd.DataFrame):
            df = data.copy()
        else:
            raise ValueError("L'entrée doit être un chemin vers un CSV (str, Path) ou un DataFrame Pandas.")

        # Prétraitement de la donnée
        X_scaled = self.preprocess(df)

        # Inférence
        preds = self.model.predict(X_scaled)
        pred_probas = self.model.predict_proba(X_scaled)

        # Construction du résultat :
        # On retourne le DataFrame d'origine enrichi des prédictions
        df_result = df.copy()
        df_result['prediction_class_id'] = preds
        df_result['prediction_label'] = df_result['prediction_class_id'].map(self.class_names)
        df_result['confidence_score'] = np.max(pred_probas, axis=1)

        return df_result