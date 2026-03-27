import time
import json
import numpy as np
import torch
import torch.optim as optim
from torch.utils.data import DataLoader
import logging

from .feedback_collector import FeedbackCollector
from .predictor import LightroomAIPredictor
from .training_utils import LightroomDataset, WeightedMSELoss
from .trainer import RefinementTrainer # Para usar a lógica de treino existente

logger = logging.getLogger(__name__)

class ActiveLearningRetrainer:
    def __init__(self, feedback_collector: FeedbackCollector, predictor: LightroomAIPredictor):
        self.feedback = feedback_collector
        self.predictor = predictor
        self.device = self.predictor.device # Usar o mesmo dispositivo do predictor
    
    def collect_retraining_data(self, min_samples: int = 50):
        """
        Coleta dados para re-treino a partir de predições com feedback negativo.
        """
        # Casos onde o modelo falhou (rating <= 3 e user_edited = 1)
        poor_predictions_df = self.feedback.get_poor_predictions(rating_threshold=3)
        
        if len(poor_predictions_df) < min_samples:
            logger.warning(f"Apenas {len(poor_predictions_df)} amostras de feedback negativo. Mínimo: {min_samples}. Não há dados suficientes para re-treino.")
            return None

        logger.info(f"Coletados {len(poor_predictions_df)} casos para re-treino incremental.")
        
        new_data = {
            'image_paths': [],
            'stat_features': [],
            'deep_features': [],
            'preset_labels': [],
            'target_params': []
        }
        
        # Reutilizar os extratores de features do predictor
        stat_extractor = self.predictor.stat_extractor
        deep_extractor = self.predictor.deep_extractor

        for idx, row in poor_predictions_df.iterrows():
            try:
                img_path = Path(row['image_path'])
                
                # Features estatísticas
                stat_feat_dict = stat_extractor.extract_all_features(img_path)
                # Converter dict para array na ordem correta para o scaler
                if hasattr(self.predictor.scaler_stat, 'feature_names_in_'):
                    stat_feat_array = np.array([stat_feat_dict.get(name, 0.0) for name in self.predictor.scaler_stat.feature_names_in_])
                else:
                    stat_feat_array = np.array(list(stat_feat_dict.values())) # Fallback
                
                # Deep features
                deep_feat_array = deep_extractor.extract_features(img_path)
                
                # Targets (valores corrigidos pelo utilizador)
                final_params = json.loads(row['final_params'])
                
                # Garantir que a ordem dos parâmetros é a mesma que delta_columns
                target_params_list = [final_params.get(col.replace('delta_', ''), 0.0) 
                                      for col in self.predictor.delta_columns]
                
                new_data['image_paths'].append(str(img_path))
                new_data['stat_features'].append(stat_feat_array)
                new_data['deep_features'].append(deep_feat_array)
                new_data['preset_labels'].append(row['predicted_preset'])
                new_data['target_params'].append(target_params_list)
                
            except Exception as e:
                logger.error(f"Erro ao processar imagem {row['image_path']} para re-treino: {e}")
                continue
        
        if not new_data['image_paths']:
            return None

        # Converter listas para arrays numpy
        new_data['stat_features'] = np.array(new_data['stat_features'])
        new_data['deep_features'] = np.array(new_data['deep_features'])
        new_data['preset_labels'] = np.array(new_data['preset_labels'])
        new_data['target_params'] = np.array(new_data['target_params'])

        return new_data
    
    def incremental_retrain(self, new_data: dict, epochs: int = 20, batch_size: int = 16):
        """
        Re-treino incremental do modelo de refinamento com novos dados.
        """
        logger.info("Iniciando re-treino incremental do modelo de refinamento...")
        
        # Preparar novos dados
        X_stat_new = self.predictor.scaler_stat.transform(new_data['stat_features'])
        X_deep_new = self.predictor.scaler_deep.transform(new_data['deep_features'])
        y_new = self.predictor.scaler_deltas.transform(new_data['target_params'])
        preset_new = new_data['preset_labels']
        
        # Criar dataset e dataloader
        new_dataset = LightroomDataset(X_stat_new, X_deep_new, preset_new, y_new)
        new_loader = DataLoader(new_dataset, batch_size=batch_size, shuffle=True)
        
        # Reutilizar o modelo de refinamento existente do predictor
        refinement_model = self.predictor.refinement
        
        # Reutilizar a função de perda e pesos
        # Assumir que os pesos foram definidos no treino original e podem ser recuperados
        # Ou, passar os pesos explicitamente para o construtor do retrainer
        # Por simplicidade, vamos assumir que os pesos são um tensor Float
        # TODO: Definir param_importance e weights de forma mais robusta
        param_importance = {
            'exposure': 2.0, 'contrast': 1.5, 'highlights': 1.8, 'shadows': 1.8,
            'temperature': 2.0, 'vibrance': 1.2, 'clarity': 1.0, 'whites': 1.3,
            'blacks': 1.3, 'tint': 1.0, 'saturation': 1.2, 'dehaze': 0.8,
            'sharpness': 0.5, 'noise_reduction': 0.5
        }
        weights_list = [param_importance.get(col.replace('delta_', ''), 1.0) 
                        for col in self.predictor.delta_columns]
        weights_tensor = torch.FloatTensor(weights_list).to(self.device)
        
        criterion = WeightedMSELoss(weights_tensor)
        
        # Optimizer com learning rate menor para re-treino incremental
        optimizer = optim.AdamW(refinement_model.parameters(), lr=0.0001, weight_decay=0.01)
        
        refinement_model.train() # Colocar o modelo em modo de treino
        
        for epoch in range(epochs):
            total_loss = 0
            
            for batch in new_loader:
                stat_feat = batch['stat_features'].to(self.device)
                deep_feat = batch['deep_features'].to(self.device)
                preset_id = batch['label'].to(self.device)
                deltas = batch['deltas'].to(self.device)
                
                optimizer.zero_grad()
                
                predicted = refinement_model(stat_feat, deep_feat, preset_id)
                loss = criterion(predicted, deltas)
                
                loss.backward()
                optimizer.step()
                
                total_loss += loss.item()
            
            avg_loss = total_loss / len(new_loader)
            logger.info(f"Epoch {epoch+1}/{epochs} - Loss: {avg_loss:.6f}")
        
        # Guardar modelo atualizado
        timestamp = int(time.time())
        model_save_path = Path(f'models/best_refinement_model_retrained_{timestamp}.pth')
        model_save_path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(refinement_model.state_dict(), model_save_path)

        logger.info(f"Re-treino incremental concluído! Modelo guardado em {model_save_path}")
        
        refinement_model.eval() # Colocar o modelo de volta em modo de avaliação
        
        # O predictor precisa de ser atualizado para usar o novo modelo
        # Ou, o servidor precisa de recarregar o predictor
        # Por agora, o predictor interno do retrainer está atualizado.
        # Para o servidor, seria necessário um mecanismo de recarregamento.
