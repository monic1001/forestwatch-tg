import sys
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any
import pandas as pd
import numpy as np
import io
import logging
from logging.handlers import RotatingFileHandler
import json

# --- Configuration des chemins et imports ---
CURRENT_FILE_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_FILE_DIR.parent
LOG_DIR = CURRENT_FILE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# --- Configuration du Logger ---
logger = logging.getLogger("API")
logger.setLevel(logging.INFO)
if not logger.handlers:
    fh = RotatingFileHandler(LOG_DIR / "api.log", maxBytes=5*1024*1024, backupCount=2)
    fh.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(fh)
    
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(ch)

# Ajout du root au path pour permettre l'import de 'src.predict'
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

# Import du module de prédiction
try:
    from src.predict import LandCoverPredictor
    predictor = LandCoverPredictor()
    EXPECTED_FEATURES = predictor.expected_features.tolist()
except Exception as e:
    # On gère l'erreur pour que l'API puisse au moins démarrer et renvoyer le statut
    logger.error(f"❌ Erreur CRITIQUE d'import du Predictor : {e}")
    predictor = None
    EXPECTED_FEATURES = []


# --- Configuration de l'API ---
app = FastAPI(
    title="ForestWatch Togo API",
    description="API de prédiction de classification d'occupation des sols et déforestation",
    version="1.0.0"
)

# Configuration CORS pour autoriser les requêtes cross-origin (ex: depuis une WebApp ou GEE)
origins = [
    "*", # A restreindre plus tard lors de la mise en place de la sécurité (ex: listes de domaines de confiance)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Autorise toutes les méthodes (GET, POST, etc.)
    allow_headers=["*"], # Autorise tous les headers
)

@app.get("/")
def read_root():
    return {
        "status": "online", 
        "message": "Bienvenue sur l'API ForestWatch Togo",
        "model_loaded": predictor is not None
    }

@app.post("/predict/file/")
async def predict_file(file: UploadFile = File(...)):
    """
    Endpoint global acceptant un fichier CSV, JSON, GeoJSON ou Excel (xlsx, xls).
    Gère la détection de format et renvoie les prédictions.
    """
    logger.info(f"📁 Fichier reçu : {file.filename}")
    
    # 1. Barrière I : Contrôle de la taille du fichier
    max_file_size = 50 * 1024 * 1024 # 50 MB
    
    if file.size and file.size > max_file_size:
        logger.warning(f"Rejet: Fichier trop volumineux ({file.size} bytes). Limite: {max_file_size} bytes.")
        raise HTTPException(status_code=413, detail="Payload Too Large: Le fichier dépasse la limite autorisée de 50 MB.")

    if not predictor:
        logger.error("Requête de prédiction mais modèle non chargé.")
        raise HTTPException(status_code=503, detail="Modèle IA non chargé sur le serveur.")

    try:
        # Lire le contenu du fichier uploadé en mémoire
        contents = await file.read()
        
        # 2e Barrière (Secours si file.size n'était pas évalué par Uvicorn)
        if len(contents) > max_file_size:
            logger.warning(f"Rejet post-lecture: Fichier trop volumineux ({len(contents)} bytes).")
            raise HTTPException(status_code=413, detail="Payload Too Large: Le fichier d'entrée dépasse la limite autorisée.")
            
        # Détection du format (CSV, Excel ou JSON/GeoJSON)
        if file.filename.endswith('.csv'):
            df = pd.read_csv(io.StringIO(contents.decode('utf-8')))
        elif file.filename.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(io.BytesIO(contents))
        elif file.filename.endswith(('.json', '.geojson')):
            data_json = json.loads(contents.decode('utf-8'))
            score_features = 'features' in data_json
            if score_features:
                # C'est un GeoJSON (on extrait les propriétés)
                properties_list = [feat.get('properties', {}) for feat in data_json['features']]
                df = pd.DataFrame(properties_list)
            else:
                # JSON classique tabulaire
                df = pd.DataFrame(data_json)
        else:
            logger.warning(f"Format non supporté: {file.filename}")
            raise ValueError("Le fichier doit être au format .csv, .xls, .xlsx, .json ou .geojson")
            
        logger.info(f"✅ Données extraites : {df.shape[0]} lignes pour l'inférence.")
        
        # Conserver l'ordre original des lignes
        # Faire la prédiction (predict gèrera les erreurs de features manquantes)
        results_df = predictor.predict(df)
        
        # Remplacer les NaN
        results_df = results_df.replace({pd.NA: None, np.nan: None})
        
        # On ajoute lat/lon SEULEMENT si ils existent dans le CSV soumis
        columns_to_return = []
        if 'latitude' in results_df.columns:
            columns_to_return.append('latitude')
        if 'longitude' in results_df.columns:
            columns_to_return.append('longitude')
            
        columns_to_return.extend(['prediction_label', 'confidence_score'])
        
        json_results = results_df[columns_to_return].to_dict(orient="records")
        
        logger.info(f"🎉 Prédiction réussie pour {file.filename}.")
        return {
            "filename": file.filename,
            "rows_processed": len(results_df),
            "predictions": json_results
        }
        
    except ValueError as ve:
        logger.error(f"Erreur de validation des données : {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Erreur inattendue : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de la prédiction : {str(e)}")


@app.post("/predict/pixel/")
def predict_pixel(data: Dict[str, Any] = Body(...)):
    """
    Endpoint acceptant un objet JSON représentant un seul point (pixel).
    Idéal pour des requêtes unitaires "en temps réel".
    """
    logger.info("🎯 Requête unitaire reçue pour un pixel.")
    if not predictor:
        raise HTTPException(status_code=503, detail="Modèle IA non chargé sur le serveur.")
        
    try:
        # data est un simple dictionnaire venant du Body json
        # On s'assure qu'il y a au moins une donnée
        if not data:
             raise ValueError("Le corps de la requête JSON est vide.")
             
        df_pixel = pd.DataFrame([data])
        
        results_df = predictor.predict(df_pixel)
        
        result_dict = {
            "prediction_label": results_df.iloc[0]['prediction_label'],
            "confidence_score": float(results_df.iloc[0]['confidence_score'])
        }
        
        if 'latitude' in df_pixel.columns and pd.notnull(df_pixel.iloc[0]['latitude']):
            result_dict['latitude'] = results_df.iloc[0]['latitude']
        if 'longitude' in df_pixel.columns and pd.notnull(df_pixel.iloc[0]['longitude']):
            result_dict['longitude'] = results_df.iloc[0]['longitude']
            
        logger.info(f"Prédiction réussie : {result_dict['prediction_label']} ({result_dict['confidence_score']})")
        return result_dict

    except ValueError as ve:
        logger.warning(f"Erreur validation pixel : {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Erreur inattendue pixel : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur interne : {str(e)}")
