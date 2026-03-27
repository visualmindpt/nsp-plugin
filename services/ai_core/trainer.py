import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from sklearn.metrics import accuracy_score, classification_report
import numpy as np
import logging
import time

from .model_architectures import PresetClassifier, RefinementRegressor
from .training_utils import WeightedMSELoss

logger = logging.getLogger(__name__)

class ClassifierTrainer:
    def __init__(self, model: PresetClassifier, device: str = 'cuda'):
        self.model = model.to(device)
        self.device = device
        self.criterion = nn.CrossEntropyLoss()
        self.optimizer = optim.Adam(model.parameters(), lr=0.001)
        self.scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer, mode='min', patience=3, factor=0.5
        )
        
        self.train_losses = []
        self.val_losses = []
        self.val_accuracies = []
    
    def train_epoch(self, train_loader: DataLoader):
        self.model.train()
        total_loss = 0
        
        for batch in train_loader:
            stat_feat = batch['stat_features'].to(self.device)
            deep_feat = batch['deep_features'].to(self.device)
            labels = batch['label'].to(self.device)
            
            self.optimizer.zero_grad()
            
            outputs = self.model(stat_feat, deep_feat)
            loss = self.criterion(outputs, labels)
            
            loss.backward()
            self.optimizer.step()
            
            total_loss += loss.item()
        
        return total_loss / len(train_loader)
    
    def validate(self, val_loader: DataLoader):
        self.model.eval()
        total_loss = 0
        all_preds = []
        all_labels = []
        
        with torch.no_grad():
            for batch in val_loader:
                stat_feat = batch['stat_features'].to(self.device)
                deep_feat = batch['deep_features'].to(self.device)
                labels = batch['label'].to(self.device)
                
                outputs = self.model(stat_feat, deep_feat)
                loss = self.criterion(outputs, labels)
                
                total_loss += loss.item()
                
                _, preds = torch.max(outputs, 1)
                all_preds.extend(preds.cpu().numpy())
                all_labels.extend(labels.cpu().numpy())
        
        val_loss = total_loss / len(val_loader)
        val_acc = accuracy_score(all_labels, all_preds)
        
        return val_loss, val_acc, all_preds, all_labels
    
    def train(self, train_loader: DataLoader, val_loader: DataLoader, epochs: int = 50, patience: int = 7, num_presets: int = 4):
        best_val_loss = float('inf')
        patience_counter = 0
        
        for epoch in range(epochs):
            train_loss = self.train_epoch(train_loader)
            val_loss, val_acc, preds, labels = self.validate(val_loader)
            
            self.train_losses.append(train_loss)
            self.val_losses.append(val_loss)
            self.val_accuracies.append(val_acc)
            
            self.scheduler.step(val_loss)
            
            logger.info(f"Epoch {epoch+1}/{epochs}")
            logger.info(f"  Train Loss: {train_loss:.4f}")
            logger.info(f"  Val Loss: {val_loss:.4f} | Val Acc: {val_acc:.4f}")
            
            # Early stopping
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
                # Guardar melhor modelo
                torch.save(self.model.state_dict(), 'best_preset_classifier.pth')
                logger.info("  ✅ Melhor modelo guardado!")
            else:
                patience_counter += 1
                if patience_counter >= patience:
                    logger.info(f"\n⏹ Early stopping triggered após {epoch+1} epochs")
                    break
        
        # Carregar melhor modelo
        self.model.load_state_dict(torch.load('best_preset_classifier.pth'))
        
        # Report final
        _, _, final_preds, final_labels = self.validate(val_loader)
        logger.info("\n📊 Classification Report:")
        # Adicionar `labels` para garantir que todas as classes são mostradas no relatório, mesmo que não estejam na amostra de validação
        report_labels = list(range(num_presets))
        target_names = [f'Preset {i + 1}' for i in report_labels]
        logger.info(classification_report(final_labels, final_preds,
                                   labels=report_labels,
                                   target_names=target_names,
                                   zero_division=0))
        
        return self.model

class RefinementTrainer:
    def __init__(self, model: RefinementRegressor, param_weights: torch.Tensor, device: str = 'cuda'):
        self.model = model.to(device)
        self.device = device
        self.criterion = WeightedMSELoss(param_weights)
        
        # Optimizer com weight decay para regularização
        self.optimizer = optim.AdamW(model.parameters(), lr=0.001, weight_decay=0.01)
        
        self.scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer, mode='min', patience=5, factor=0.5, verbose=True
        )
        
        self.train_losses = []
        self.val_losses = []
        self.best_val_loss = float('inf')
    
    def train_epoch(self, train_loader: DataLoader):
        self.model.train()
        total_loss = 0
        
        for batch in train_loader:
            stat_feat = batch['stat_features'].to(self.device)
            deep_feat = batch['deep_features'].to(self.device)
            preset_id = batch['label'].to(self.device) # Usar 'label' como preset_id
            deltas = batch['deltas'].to(self.device)
            
            self.optimizer.zero_grad()
            
            predicted_deltas = self.model(stat_feat, deep_feat, preset_id)
            loss = self.criterion(predicted_deltas, deltas)
            
            loss.backward()
            
            # Gradient clipping para estabilidade
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
            
            self.optimizer.step()
            
            total_loss += loss.item()
        
        return total_loss / len(train_loader)
    
    def validate(self, val_loader: DataLoader):
        self.model.eval()
        total_loss = 0
        all_predictions = []
        all_targets = []
        
        with torch.no_grad():
            for batch in val_loader:
                stat_feat = batch['stat_features'].to(self.device)
                deep_feat = batch['deep_features'].to(self.device)
                preset_id = batch['label'].to(self.device) # Usar 'label' como preset_id
                deltas = batch['deltas'].to(self.device)
                
                predicted_deltas = self.model(stat_feat, deep_feat, preset_id)
                loss = self.criterion(predicted_deltas, deltas)
                
                total_loss += loss.item()
                
                all_predictions.append(predicted_deltas.cpu().numpy())
                all_targets.append(deltas.cpu().numpy())
        
        val_loss = total_loss / len(val_loader)
        
        predictions = np.vstack(all_predictions)
        targets = np.vstack(all_targets)
        
        # Calcular MAE por parâmetro (mais interpretável)
        mae_per_param = np.abs(predictions - targets).mean(axis=0)
        
        return val_loss, mae_per_param, predictions, targets
    
    def train(self, train_loader: DataLoader, val_loader: DataLoader, epochs: int = 100, patience: int = 15, delta_columns: list = [], scaler_deltas=None):
        patience_counter = 0
        
        for epoch in range(epochs):
            train_loss = self.train_epoch(train_loader)
            val_loss, mae_per_param, preds, targets = self.validate(val_loader)
            
            self.train_losses.append(train_loss)
            self.val_losses.append(val_loss)
            
            self.scheduler.step(val_loss)
            
            logger.info(f"\nEpoch {epoch+1}/{epochs}")
            logger.info(f"  Train Loss: {train_loss:.6f}")
            logger.info(f"  Val Loss: {val_loss:.6f}")
            
            # Mostrar MAE por parâmetro a cada 10 epochs
            if (epoch + 1) % 10 == 0:
                logger.info("\n  MAE por parâmetro:")
                for i, col in enumerate(delta_columns):
                    param_name = col.replace('delta_', '')
                    logger.info(f"    {param_name}: {mae_per_param[i]:.4f}")
            
            # Early stopping
            if val_loss < self.best_val_loss:
                self.best_val_loss = val_loss
                patience_counter = 0
                torch.save(self.model.state_dict(), 'best_refinement_model.pth')
                logger.info("  ✅ Melhor modelo guardado!")
            else:
                patience_counter += 1
                if patience_counter >= patience:
                    logger.info(f"\n ⏹ Early stopping após {epoch+1} epochs")
                    break
        
        # Carregar melhor modelo
        self.model.load_state_dict(torch.load('best_refinement_model.pth'))
        
        # Análise final
        _, final_mae, final_preds, final_targets = self.validate(val_loader)
        
        logger.info("\n📊 Análise Final de Precisão:")
        logger.info("=" * 50)
        for i, col in enumerate(delta_columns):
            param_name = col.replace('delta_', '')
            mae = final_mae[i]
            
            # Desnormalizar para valores reais
            if scaler_deltas:
                mae_real = mae * scaler_deltas.scale_[i]
            else:
                mae_real = mae # Se não houver scaler, usar o MAE normal
            
            logger.info(f"{param_name:20s}: MAE = {mae_real:.3f}")
        
        return self.model
