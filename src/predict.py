# -----------------------------------------------------------------------------
# Copyright (c) 2025-2026 Kodjo Jean DEGBEVI. All rights reserved.
# Licensed under the CC-BY-NC-4.0 License. See LICENSE file in the project root.
#
# Project: ForestWatch Togo - Land Cover & Deforestation AI Monitor
# Author: Kodjo Jean DEGBEVI (@kjd-dktech)
# -----------------------------------------------------------------------------

import pandas as pd
import numpy as np
import joblib
import sys
import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

CURRENT_FILE_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_FILE_DIR.parent
LOG_DIR = REPO_ROOT / "api" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("Predictor")
logger.setLevel(logging.INFO)
if not logger.handlers:
    fh = RotatingFileHandler(LOG_DIR / "predict.log", maxBytes=5*1024*1024, backupCount=2)
    fh.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(fh)
    
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(ch)

if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

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

        self.class_names = {
            0: 'Forêt', 
            1: 'Savanes/Buissons', 
            2: 'Cultures', 
            3: 'Urbain', 
            4: 'Sols nus', 
            5: 'Eau'
        }
        
        try:
            hf_repo_id = os.getenv("HF_MODEL_REPO_ID")
            hf_token = os.getenv("HF_TOKEN")
            
            if not Path(model_path).exists() or not Path(scaler_path).exists():
                if hf_repo_id:
                    logger.info(f"Artefacts introuvables localement. Téléchargement depuis Hugging Face ({hf_repo_id})...")
                    from huggingface_hub import hf_hub_download
                    
                    if not Path(model_path).exists():
                        logger.info("-> Téléchargement du modèle...")
                        model_path = hf_hub_download(repo_id=hf_repo_id, filename=Path(model_path).name, token=hf_token, local_dir=Path(model_path).parent)
                        
                    if not Path(scaler_path).exists():
                        logger.info("-> Téléchargement du scaler...")
                        scaler_path = hf_hub_download(repo_id=hf_repo_id, filename=Path(scaler_path).name, token=hf_token, local_dir=Path(scaler_path).parent)
                else:
                    raise FileNotFoundError("Artefacts manquants localement et 'HF_MODEL_REPO_ID' non défini dans .env.")

            self.model = joblib.load(model_path)
            self.scaler = joblib.load(scaler_path)
            logger.info(f"✅ Modèle et Scaler chargés avec succès depuis {Path(model_path).parent}.")
        except Exception as e:
            logger.error(f"Erreur de chargement des artefacts : {e}")
            raise RuntimeError(f"Erreur de chargement des artefacts : {e}")

        cols_to_drop_sys = ['system:index', '.geo', 'longitude', 'latitude', 'landcover']
        
        cols_to_drop_corr = [
            'NDWI_mean', 'NDVI_mean', 'B4_mean', 
            'NDWI_var', 'NDVI_var',               
            'B12_ent', 'NDWI_ent', 'B8_ent', 'NDVI_ent', 'NDBI_ent'
        ]
        
        cols_to_drop_importance = ['NDBI_asm', 'NDWI_asm', 'NDVI_asm', 'B12_asm']
        
        self.all_cols_to_drop = cols_to_drop_sys + cols_to_drop_corr + cols_to_drop_importance
        
        self.expected_features = self.scaler.feature_names_in_

    def preprocess(self, df):
        """
        Applique les mêmes transformations que lors de l'entraînement 
        (suppression des features, réagencement, mise à l'échelle).
        """
        df_clean = df.copy()

        indices_spectraux = ['NDVI', 'NDWI', 'NDBI']
        if any(idx not in df_clean.columns for idx in indices_spectraux):
            logger.info("Indices spectraux manquants. Tentative de calcul dynamique via les bandes brutes.")
            try:
                df_clean = calculate_indices(df_clean)
                logger.info("✅ Indices spectraux calculés avec succès.")
            except ValueError as e:
                logger.warning(f"Impossible de calculer les indices dynamiquement : {e}")

        is_valid, msg = has_minimum_glcm_features(df_clean, self.expected_features)
        if not is_valid:
            logger.error(f"Rejet : {msg}")
            raise ValueError(msg)
        
        missing_features = [f for f in self.expected_features if f not in df_clean.columns]
        if missing_features:
            logger.error(f"Colonnes manquantes finales : {missing_features}")
            raise ValueError(f"Colonnes manquantes dans les données fournies (après calculs) : {missing_features}")
            
        df_clean = df_clean[self.expected_features]
        
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

        X_scaled = self.preprocess(df)

        preds = self.model.predict(X_scaled)
        pred_probas = self.model.predict_proba(X_scaled)
        
        df_result = df.copy()
        df_result['prediction_class_id'] = preds
        df_result['prediction_label'] = df_result['prediction_class_id'].map(self.class_names)
        df_result['confidence_score'] = np.max(pred_probas, axis=1)

        return df_result