import torch
import torchvision.models as models
from torchvision.models import MobileNet_V3_Small_Weights, ResNet18_Weights
import torchvision.transforms as transforms
from PIL import Image
import numpy as np
import logging
from services.ai_core.image_feature_extractor import ImageFeatureExtractor # Importar para usar _load_image

logger = logging.getLogger(__name__)

# Instanciar ImageFeatureExtractor para aceder a _load_image
_image_loader = ImageFeatureExtractor()

class DeepFeatureExtractor:
    def __init__(self, model_name='mobilenet_v3_small'):
        """
        Usa modelo pré-treinado para extrair features
        mobilenet_v3_small: rápido, leve (5.5M params)
        """
        self.device = torch.device('cuda' if torch.cuda.is_available() and torch.cuda.is_available() else 'cpu')
        
        # Carregar modelo pré-treinado com a nova API 'weights'
        if model_name == 'mobilenet_v3_small':
            self.model = models.mobilenet_v3_small(weights=MobileNet_V3_Small_Weights.DEFAULT)
            # Remover classificador final, manter apenas feature extractor
            self.model = torch.nn.Sequential(*list(self.model.children())[:-1])
            self.feature_dim = 576
        elif model_name == 'resnet18':
            self.model = models.resnet18(weights=ResNet18_Weights.DEFAULT)
            self.model = torch.nn.Sequential(*list(self.model.children())[:-1])
            self.feature_dim = 512
        else:
            raise ValueError(f"Modelo '{model_name}' não suportado.")
        
        self.model.to(self.device)
        self.model.eval() # Modo de avaliação
        
        # Transformações padrão ImageNet
        self.transform = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406],
                               std=[0.229, 0.224, 0.225])
        ])
    
    def extract_features(self, image_path):
        """
        Extrai features deep de uma imagem
        """
        try:
            img_np = _image_loader._load_image(image_path)
            img = Image.fromarray(img_np)
            img_tensor = self.transform(img).unsqueeze(0).to(self.device)
            
            with torch.no_grad():
                features = self.model(img_tensor)
                features = features.squeeze().cpu().numpy()
            
            return features
        except Exception as e:
            logger.error(f"Erro ao extrair deep features de {image_path}: {e}")
            return np.zeros(self.feature_dim) # Devolver array de zeros em caso de erro
    
    def extract_batch(self, image_paths, batch_size=32):
        """
        Processa múltiplas imagens em batch (mais rápido)
        """
        all_features = []
        
        for i in range(0, len(image_paths), batch_size):
            batch_paths = image_paths[i:i+batch_size]
            batch_tensors = []
            
            for path in batch_paths:
                try:
                    img_np = _image_loader._load_image(path)
                    img = Image.fromarray(img_np)
                    img_tensor = self.transform(img)
                    batch_tensors.append(img_tensor)
                except Exception as e:
                    logger.warning(f"Erro em {path}: {e}. Usando tensor vazio.")
                    # Tensor vazio para manter batch size e evitar quebrar o batch
                    batch_tensors.append(torch.zeros(3, 224, 224))
            
            if not batch_tensors: # Se o batch estiver vazio
                continue

            batch = torch.stack(batch_tensors).to(self.device)
            
            with torch.no_grad():
                features = self.model(batch)
                # A saída pode ter diferentes formas dependendo do modelo (ex: [batch_size, C, H, W] ou [batch_size, C])
                # Precisamos de achatar para [batch_size, C]
                features = features.view(features.size(0), -1).cpu().numpy()
            
            all_features.append(features)
            
            logger.info(f"Processado batch {i//batch_size + 1}/{len(image_paths)//batch_size + 1}")
        
        if not all_features:
            return np.empty((0, self.feature_dim)) # Retornar array vazio se não houver features
            
        return np.vstack(all_features)
