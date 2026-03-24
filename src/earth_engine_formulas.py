# -----------------------------------------------------------------------------
# Copyright (c) 2025-2026 Kodjo Jean DEGBEVI. All rights reserved.
# Licensed under the CC-BY-NC-4.0 License. See LICENSE file in the project root.
#
# Project: ForestWatch Togo - Land Cover & Deforestation AI Monitor
# Author: Kodjo Jean DEGBEVI (@kjd-dktech)
# -----------------------------------------------------------------------------

import pandas as pd
import numpy as np

def calculate_indices(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcule les indices spectraux à partir des bandes brutes de Sentinel-2.
    Si les bandes ne sont pas présentes, lève une ValueError.
    """
    required_bands = ['B4', 'B8', 'B12', 'B11', 'B3']
    for band in required_bands:
        if band not in df.columns:
            raise ValueError(f"La bande brute {band} est requise pour calculer les indices spectraux.")

    computed_df = df.copy()

    # NDVI = (NIR - Red) / (NIR + Red)
    computed_df['NDVI'] = (computed_df['B8'] - computed_df['B4']) / (computed_df['B8'] + computed_df['B4'] + 1e-10)

    # NDWI = (Green - NIR) / (Green + NIR)
    computed_df['NDWI'] = (computed_df['B3'] - computed_df['B8']) / (computed_df['B3'] + computed_df['B8'] + 1e-10)

    # NDBI = (SWIR1 - NIR) / (SWIR1 + NIR)
    computed_df['NDBI'] = (computed_df['B11'] - computed_df['B8']) / (computed_df['B11'] + computed_df['B8'] + 1e-10)
    
    return computed_df


def has_minimum_glcm_features(df: pd.DataFrame, expected_features: list) -> bool:
    """
    Vérifie si le DataFrame contient au moins les features GLCM minimales requises
    pour inférer le modèle, même s'il ne s'agit pas d'un pixel isolé brut.
    L'API demande un minimum de contexte spatial
    """
    missing_features = [feat for feat in expected_features if feat not in df.columns]
    
    glcm_features = [f for f in expected_features if any(ext in f for ext in ['_contrast', '_corr', '_asm'])]
    missing_glcm = [f for f in missing_features if f in glcm_features]
    
    if len(missing_glcm) > 0:
         return False, f"Impossible de procéder. Les métriques spatiales GLCM suivantes manquent : {missing_glcm}. Veuillez extraire les GLCM via un rayon > 0."
        
    return True, "OK"
