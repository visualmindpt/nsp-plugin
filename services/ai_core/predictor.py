import torch
import torch.nn.functional as F
import numpy as np
import pandas as pd
from pathlib import Path
import logging
import joblib  # Para carregar scalers
import json  # Para preset_centers
import warnings

# Usar arquiteturas otimizadas (V2), alinhadas com train_models_v2
from .model_architectures_v2 import OptimizedPresetClassifier, OptimizedRefinementRegressor
from .image_feature_extractor import ImageFeatureExtractor
from .deep_feature_extractor import DeepFeatureExtractor

logger = logging.getLogger(__name__)

# Evitar warnings do sklearn sobre feature names no scaler
warnings.filterwarnings("ignore", category=UserWarning, module="sklearn")

def _infer_width_factor(state_dict: dict, key: str, base_channels: int) -> float:
    """
    Infere width_factor a partir do shape do primeiro bloco.
    """
    tensor = state_dict.get(key)
    if tensor is None:
        return 0.75  # fallback historico
    out_channels = tensor.shape[0]
    width = out_channels / base_channels
    return max(width, 0.5)


class LightroomAIPredictor:
    def __init__(self, classifier_path, refinement_path, preset_centers, 
                 scaler_stat, scaler_deep, scaler_deltas, delta_columns):
        """
        Sistema completo de predição
        """
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        # Carregar scalers e outros componentes auxiliares
        self.scaler_stat = joblib.load(scaler_stat) if isinstance(scaler_stat, (str, Path)) else scaler_stat
        self.scaler_deep = joblib.load(scaler_deep) if isinstance(scaler_deep, (str, Path)) else scaler_deep
        self.scaler_deltas = joblib.load(scaler_deltas) if isinstance(scaler_deltas, (str, Path)) else scaler_deltas
        
        # preset_centers pode vir como dict ou path para json
        if isinstance(preset_centers, (str, Path)):
            with open(preset_centers, 'r') as f:
                self.preset_centers = json.load(f)
            # Converter chaves de string para int se necessário
            self.preset_centers = {int(k): v for k, v in self.preset_centers.items()}
        else:
            self.preset_centers = preset_centers
            
        # delta_columns pode vir como list ou path para json
        if isinstance(delta_columns, (str, Path)):
            with open(delta_columns, 'r') as f:
                self.delta_columns = json.load(f)
        else:
            self.delta_columns = delta_columns

        # Carregar modelos
        # Assumir que os scalers têm n_features_in_ após fit
        stat_features_dim = self.scaler_stat.n_features_in_ if hasattr(self.scaler_stat, 'n_features_in_') else 0
        deep_features_dim = self.scaler_deep.n_features_in_ if hasattr(self.scaler_deep, 'n_features_in_') else 0
        
        # Se os scalers não tiverem n_features_in_, tentar inferir de um exemplo ou definir um valor padrão
        if stat_features_dim == 0:
            logger.warning("scaler_stat não tem 'n_features_in_'. Definindo dimensão padrão para features estatísticas (ex: 100).")
            stat_features_dim = 100 # Valor padrão, ajustar conforme necessário
        if deep_features_dim == 0:
            logger.warning("scaler_deep não tem 'n_features_in_'. Definindo dimensão padrão para deep features (ex: 512).")
            deep_features_dim = 512 # Valor padrão, ajustar conforme necessário

        classifier_state = torch.load(classifier_path, map_location=self.device)
        classifier_width = _infer_width_factor(classifier_state, 'stat_branch.0.weight', base_channels=64)
        self.classifier = OptimizedPresetClassifier(
            stat_features_dim=stat_features_dim,
            deep_features_dim=deep_features_dim,
            num_presets=len(self.preset_centers),
            width_factor=classifier_width
        )
        self.classifier.load_state_dict(classifier_state)
        self.classifier.to(self.device)
        self.classifier.eval()
        
        refinement_state = torch.load(refinement_path, map_location=self.device)
        refinement_width = _infer_width_factor(refinement_state, 'stat_branch.0.weight', base_channels=64)
        self.refinement = OptimizedRefinementRegressor(
            stat_features_dim=stat_features_dim,
            deep_features_dim=deep_features_dim,
            num_presets=len(self.preset_centers),
            num_params=len(self.delta_columns),
            width_factor=refinement_width
        )
        self.refinement.load_state_dict(refinement_state)
        self.refinement.to(self.device)
        self.refinement.eval()
        
        # Feature extractors
        self.stat_extractor = ImageFeatureExtractor()
        self.deep_extractor = DeepFeatureExtractor()
        
        logger.info("✅ LightroomAIPredictor inicializado com sucesso!")
    
    def predict(self, image_path, return_confidence=False):
        """
        Prediz configurações completas do Lightroom para uma imagem
        """
        # 1. Extrair features
        logger.info(f"📸 Extraindo features da imagem: {image_path}")
        stat_features_dict = self.stat_extractor.extract_all_features(image_path)
        
        # Converter dict para array na ordem correta para o scaler
        # Isso exige que a ordem das chaves seja consistente, o que é garantido se o dict for criado sempre da mesma forma
        # Ou, melhor, ter uma lista de nomes de features esperados
        
        # Para evitar problemas de ordem, vamos usar um array de zeros e preencher
        # Assumindo que self.scaler_stat.feature_names_in_ existe e define a ordem
        if hasattr(self.scaler_stat, 'feature_names_in_'):
            stat_features_array = np.array([stat_features_dict.get(name, 0.0) for name in self.scaler_stat.feature_names_in_])
        else:
            # Fallback: converter dict para array, mas a ordem pode não ser consistente
            logger.warning("scaler_stat não tem 'feature_names_in_'. A ordem das features estatísticas pode ser inconsistente.")
            stat_features_array = np.array(list(stat_features_dict.values()))
            
        stat_features_scaled = self.scaler_stat.transform(stat_features_array.reshape(1, -1))
        
        deep_features_array = self.deep_extractor.extract_features(image_path)
        deep_features_scaled = self.scaler_deep.transform(deep_features_array.reshape(1, -1))
        
        # Converter para tensors
        stat_tensor = torch.FloatTensor(stat_features_scaled).to(self.device)
        deep_tensor = torch.FloatTensor(deep_features_scaled).to(self.device)
        
        # 2. Classificar preset
        logger.info("🎨 Identificando preset base...")
        with torch.no_grad():
            preset_logits = self.classifier(stat_tensor, deep_tensor)
            preset_probs = F.softmax(preset_logits, dim=1)
            preset_id = torch.argmax(preset_probs, dim=1).item()
            confidence = preset_probs[0, preset_id].item()

        topk = min(3, preset_probs.shape[1])
        top_values, top_indices = torch.topk(preset_probs, k=topk, dim=1)
        top_candidates = [
            {"preset_id": int(idx), "confidence": float(val)}
            for idx, val in zip(top_indices[0], top_values[0])
        ]
        logger.info(f"   → Preset {preset_id + 1} (confiança: {confidence:.1%})")
        logger.debug("   → Top presets: %s", top_candidates)
        
        # 3. Obter valores base do preset
        preset_base = self.preset_centers.get(preset_id, {})
        if not preset_base:
            logger.error(f"Preset ID {preset_id} não encontrado nos centros de presets.")
            raise ValueError(f"Preset ID {preset_id} não encontrado.")
        
        # 4. Predizer refinamentos
        logger.info("⚙️  Calculando refinamentos...")
        preset_tensor = torch.LongTensor([preset_id]).to(self.device)
        
        with torch.no_grad():
            deltas_normalized = self.refinement(stat_tensor, deep_tensor, preset_tensor)
            deltas = self.scaler_deltas.inverse_transform(
                deltas_normalized.cpu().numpy()
            )[0]
        
        # 5. Calcular valores finais
        final_params = {}
        for i, delta_col in enumerate(self.delta_columns):
            param_name = delta_col.replace('delta_', '')
            base_value = preset_base.get(param_name, 0.0) # Usar 0.0 se o preset não tiver o feature
            delta_value = deltas[i]
            final_value = base_value + delta_value
            
            # Clamping aos limites do Lightroom
            final_value = self._clamp_parameter(param_name, final_value)
            
            final_params[param_name] = final_value
            # logger.debug(f"   {param_name}: {base_value:.2f} + {delta_value:.2f} = {final_value:.2f}")
        
        deltas_dict = {
            self.delta_columns[i].replace('delta_', ''): float(deltas[i])
            for i in range(len(deltas))
        }
        logger.debug("Δ refinements: %s", deltas_dict)
        logger.debug("🎚 parametros finais: %s", final_params)

        result = {
            'preset_id': preset_id,
            'preset_confidence': confidence,
            'preset_base': preset_base,
            'deltas': deltas_dict,
            'final_params': final_params
        }
        
        if return_confidence:
            result['all_preset_probs'] = preset_probs.cpu().numpy()[0]
        
        return result
    
    def _clamp_parameter(self, param_name, value):
        """
        Limita valores aos ranges válidos do Lightroom
        """
        # Estes ranges devem ser definidos de forma mais centralizada e completa
        ranges = {
            'exposure': (-5.0, 5.0),
            'contrast': (-100, 100),
            'highlights': (-100, 100),
            'shadows': (-100, 100),
            'whites': (-100, 100),
            'blacks': (-100, 100),
            'temperature': (2000, 50000), # Exemplo, ajustar conforme o Lightroom
            'tint': (-150, 150),
            'vibrance': (-100, 100),
            'saturation': (-100, 100),
            'clarity': (-100, 100),
            'dehaze': (-100, 100),
            'sharpness': (0, 150),
            'noise_reduction': (0, 100)
        }
        
        if param_name in ranges:
            min_val, max_val = ranges[param_name]
            return np.clip(value, min_val, max_val)
        
        return value
    
    def batch_predict(self, image_paths, output_csv='predictions.csv'):
        """
        Processa múltiplas imagens
        """
        results = []
        
        for i, path in enumerate(image_paths):
            logger.info(f"\n{'='*60}")
            logger.info(f"Processando {i+1}/{len(image_paths)}: {Path(path).name}")
            logger.info('='*60)
            
            try:
                result = self.predict(path)
                result['image_path'] = str(path)
                results.append(result)
            except Exception as e:
                logger.error(f"❌ Erro: {e}")
                continue
        
        # Salvar resultados
        if results:
            df_results = pd.DataFrame([
                {**{'image_path': r['image_path'], 
                    'preset_id': r['preset_id'],
                    'confidence': r['preset_confidence']},
                 **r['final_params']}
                for r in results
            ])
            
            df_results.to_csv(output_csv, index=False)
            logger.info(f"\n✅ Resultados salvos em {output_csv}")
        else:
            logger.warning("Nenhum resultado para salvar.")
        
        return results
