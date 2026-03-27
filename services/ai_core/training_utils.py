import torch
import torch.nn as nn
from torch.utils.data import Dataset

class LightroomDataset(Dataset):
    def __init__(self, stat_features, deep_features, labels, delta_params=None):
        """
        Dataset para treino de modelos de IA do Lightroom.
        Pode ser usado para o classificador (apenas labels) ou para o refinador (labels e delta_params).
        """
        self.stat_features = torch.FloatTensor(stat_features)
        self.deep_features = torch.FloatTensor(deep_features)
        self.labels = torch.LongTensor(labels) # Para o classificador (preset_cluster)
        
        self.delta_params = None
        if delta_params is not None:
            self.delta_params = torch.FloatTensor(delta_params) # Para o refinador (deltas)
    
    def __len__(self):
        return len(self.labels)
    
    def __getitem__(self, idx):
        sample = {
            'stat_features': self.stat_features[idx],
            'deep_features': self.deep_features[idx],
            'label': self.labels[idx]
        }
        if self.delta_params is not None:
            sample['deltas'] = self.delta_params[idx]
        return sample

class WeightedMSELoss(nn.Module):
    def __init__(self, param_weights):
        """
        Permite dar mais importância a certos parâmetros na função de perda MSE.
        param_weights: Tensor de pesos para cada parâmetro.
        """
        super(WeightedMSELoss, self).__init__()
        self.param_weights = param_weights # Espera-se um tensor Float
    
    def forward(self, predictions, targets):
        # Garantir que os pesos estão no mesmo dispositivo que as previsões
        weighted_param_weights = self.param_weights.to(predictions.device)
        
        squared_errors = (predictions - targets) ** 2
        weighted_errors = squared_errors * weighted_param_weights
        return weighted_errors.mean()
