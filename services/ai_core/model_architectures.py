import torch
import torch.nn as nn
import torch.nn.functional as F

class PresetClassifier(nn.Module):
    def __init__(self, stat_features_dim, deep_features_dim, num_presets):
        """
        Combina features estatísticas + deep features para classificar presets.
        """
        super(PresetClassifier, self).__init__()
        
        # Branch para features estatísticas
        self.stat_branch = nn.Sequential(
            nn.Linear(stat_features_dim, 128),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(0.3)
        )
        
        # Branch para deep features
        self.deep_branch = nn.Sequential(
            nn.Linear(deep_features_dim, 256),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(256, 64),
            nn.ReLU(),
            nn.Dropout(0.3)
        )
        
        # Combinar ambas as branches
        # A entrada para a fusão é a concatenação das saídas das branches (64 + 64 = 128)
        self.fusion = nn.Sequential(
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, num_presets)
        )
    
    def forward(self, stat_features, deep_features):
        stat_out = self.stat_branch(stat_features)
        deep_out = self.deep_branch(deep_features)
        
        # Concatenar
        combined = torch.cat([stat_out, deep_out], dim=1)
        
        # Classificação final
        output = self.fusion(combined)
        return output

class RefinementRegressor(nn.Module):
    def __init__(self, stat_features_dim, deep_features_dim, num_presets, num_params):
        """
        Prediz os deltas de refinamento sobre o preset base.
        """
        super(RefinementRegressor, self).__init__()
        
        # Embedding do preset escolhido
        # num_presets é o número total de presets, 32 é a dimensão do embedding
        self.preset_embedding = nn.Embedding(num_presets, 32)
        
        # Features estatísticas
        self.stat_branch = nn.Sequential(
            nn.Linear(stat_features_dim, 128),
            nn.ReLU(),
            nn.BatchNorm1d(128),
            nn.Dropout(0.3),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(0.2)
        )
        
        # Deep features
        self.deep_branch = nn.Sequential(
            nn.Linear(deep_features_dim, 256),
            nn.ReLU(),
            nn.BatchNorm1d(256),
            nn.Dropout(0.3),
            nn.Linear(256, 64),
            nn.ReLU(),
            nn.Dropout(0.2)
        )
        
        # Fusão: stat(64) + deep(64) + preset_emb(32) = 160
        self.fusion = nn.Sequential(
            nn.Linear(160, 128),
            nn.ReLU(),
            nn.BatchNorm1d(128),
            nn.Dropout(0.2),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(64, num_params)  # Output: deltas para cada parâmetro
        )
    
    def forward(self, stat_features, deep_features, preset_id):
        # Embedding do preset
        preset_emb = self.preset_embedding(preset_id)
        
        # Processar features
        stat_out = self.stat_branch(stat_features)
        deep_out = self.deep_branch(deep_features)
        
        # Concatenar tudo
        combined = torch.cat([stat_out, deep_out, preset_emb], dim=1)
        
        # Predizer deltas
        deltas = self.fusion(combined)
        
        return deltas
