import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
import logging

logger = logging.getLogger(__name__)

class PresetIdentifier:
    def __init__(self, dataset: pd.DataFrame):
        self.dataset = dataset
        self.preset_centers = {}
        # TODOS os 58 sliders do Lightroom para clustering e delta calculation
        self.features_for_clustering = [
            # Basic (6)
            'exposure', 'contrast', 'highlights', 'shadows', 'whites', 'blacks',

            # Presence (5)
            'texture', 'clarity', 'dehaze', 'vibrance', 'saturation',

            # White Balance (2)
            'temp', 'tint',

            # Sharpening (4)
            'sharpen_amount', 'sharpen_radius', 'sharpen_detail', 'sharpen_masking',

            # Noise Reduction (3)
            'nr_luminance', 'nr_detail', 'nr_color',

            # Effects (2)
            'vignette', 'grain',

            # Calibration (7)
            'shadow_tint', 'red_primary_hue', 'red_primary_saturation',
            'green_primary_hue', 'green_primary_saturation',
            'blue_primary_hue', 'blue_primary_saturation',

            # HSL (24 = 8 cores x 3 ajustes)
            'hsl_red_hue', 'hsl_red_saturation', 'hsl_red_luminance',
            'hsl_orange_hue', 'hsl_orange_saturation', 'hsl_orange_luminance',
            'hsl_yellow_hue', 'hsl_yellow_saturation', 'hsl_yellow_luminance',
            'hsl_green_hue', 'hsl_green_saturation', 'hsl_green_luminance',
            'hsl_aqua_hue', 'hsl_aqua_saturation', 'hsl_aqua_luminance',
            'hsl_blue_hue', 'hsl_blue_saturation', 'hsl_blue_luminance',
            'hsl_purple_hue', 'hsl_purple_saturation', 'hsl_purple_luminance',
            'hsl_magenta_hue', 'hsl_magenta_saturation', 'hsl_magenta_luminance',

            # Split Toning (5)
            'split_highlight_hue', 'split_highlight_saturation',
            'split_shadow_hue', 'split_shadow_saturation', 'split_balance',
        ]
        
    def identify_base_presets(self, n_presets=4, random_state=42):
        """
        Usa clustering para identificar padrões nos teus presets.
        n_presets: número esperado de presets base.
        """
        available_features = [f for f in self.features_for_clustering if f in self.dataset.columns]
        if not available_features:
            logger.error("Nenhuma feature de clustering encontrada no dataset.")
            raise ValueError("Dataset não contém features válidas para clustering.")

        X = self.dataset[available_features].fillna(0)
        
        if len(X) < n_presets:
            logger.warning(f"Número de amostras ({len(X)}) é menor que o número de presets ({n_presets}) a identificar. Reduzindo n_presets para {len(X)}.")
            n_presets = len(X)
            if n_presets == 0:
                logger.error("Dataset vazio, impossível identificar presets.")
                return {}
        
        # K-means para encontrar centros dos presets
        kmeans = KMeans(n_clusters=n_presets, random_state=random_state, n_init=10)
        self.dataset['preset_cluster'] = kmeans.fit_predict(X)
        
        # Centros = configurações médias de cada preset
        self.preset_centers = {}
        for i in range(n_presets):
            cluster_data = self.dataset[self.dataset['preset_cluster'] == i]
            if not cluster_data.empty:
                self.preset_centers[i] = cluster_data[available_features].mean().to_dict()
                
                logger.info(f"\n📋 Preset {i+1} (n={len(cluster_data)} fotos):")
                for param, value in self.preset_centers[i].items():
                    logger.info(f"  {param}: {value:.2f}")
            else:
                logger.warning(f"Cluster {i} está vazio. Pode indicar um n_presets demasiado alto.")
        
        return self.preset_centers
    
    def calculate_deltas(self):
        """
        Calcula o quanto ajustaste DEPOIS do preset base
        """
        if 'preset_cluster' not in self.dataset.columns:
            logger.error("Presets não identificados. Execute 'identify_base_presets' primeiro.")
            raise ValueError("Presets não identificados.")
            
        if not self.preset_centers:
            logger.error("Centros de presets vazios. Execute 'identify_base_presets' primeiro.")
            raise ValueError("Centros de presets vazios.")

        deltas = self.dataset.copy()
        
        # Usar apenas as features que foram usadas para clustering
        features_to_process = [f for f in self.features_for_clustering if f in self.dataset.columns]

        for idx, row in self.dataset.iterrows():
            preset_id = row['preset_cluster']
            preset_values = self.preset_centers.get(preset_id, {})
            
            for feature in features_to_process:
                base_value = preset_values.get(feature, 0.0) # Usar 0.0 se o preset não tiver o feature
                # Delta = valor final - valor do preset
                deltas.at[idx, f'delta_{feature}'] = row[feature] - base_value
        
        return deltas
