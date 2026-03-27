"""
Culling AI - Classificação automática de Keep/Reject
Usa deep features + estatísticas da imagem para predizer se deve manter ou rejeitar
"""
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class CullingClassifier(nn.Module):
    """
    Classificador binário para Culling

    Input:
        - deep_features: 512 features do MobileNetV3
        - stats_features: ~10 features estatísticas (sharpness, exposure, etc.)

    Output:
        - keep_probability: probabilidade de Keep (0-1)
    """

    def __init__(self, deep_dim=512, stats_dim=10, hidden_dim=256, dropout=0.3):
        super().__init__()

        # Branch para deep features
        self.deep_branch = nn.Sequential(
            nn.Linear(deep_dim, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Dropout(dropout)
        )

        # Branch para features estatísticas
        self.stats_branch = nn.Sequential(
            nn.Linear(stats_dim, 64),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.Dropout(dropout / 2),
            nn.Linear(64, 32),
            nn.BatchNorm1d(32),
            nn.ReLU()
        )

        # Fusion layer
        self.fusion = nn.Sequential(
            nn.Linear(128 + 32, 64),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 1),  # Saída binária (probabilidade de Keep)
            nn.Sigmoid()
        )

    def forward(self, deep_features, stats_features):
        """
        Args:
            deep_features: (batch_size, 512)
            stats_features: (batch_size, 10)

        Returns:
            keep_prob: (batch_size, 1) - probabilidade de Keep
        """
        deep_out = self.deep_branch(deep_features)
        stats_out = self.stats_branch(stats_features)

        # Concatenar
        combined = torch.cat([deep_out, stats_out], dim=1)

        # Predição final
        keep_prob = self.fusion(combined)

        return keep_prob


class CullingPredictor:
    """
    Predictor completo para Culling
    Carrega modelo treinado e faz inferência
    """

    def __init__(
        self,
        model_path: Path,
        deep_extractor,
        stats_extractor,
        device: str = None
    ):
        """
        Args:
            model_path: Caminho para o modelo treinado (.pth)
            deep_extractor: DeepFeatureExtractor instance
            stats_extractor: ImageFeatureExtractor instance
            device: 'cuda', 'mps', 'cpu' (auto-detect se None)
        """
        self.deep_extractor = deep_extractor
        self.stats_extractor = stats_extractor

        # Auto-detect device
        if device is None:
            if torch.cuda.is_available():
                self.device = torch.device('cuda')
            elif torch.backends.mps.is_available():
                self.device = torch.device('mps')
            else:
                self.device = torch.device('cpu')
        else:
            self.device = torch.device(device)

        # Carregar modelo
        self.model = CullingClassifier()

        if model_path.exists():
            checkpoint = torch.load(model_path, map_location=self.device)
            self.model.load_state_dict(checkpoint['model_state_dict'])
            logger.info(f"✅ Culling model carregado de {model_path}")
        else:
            logger.warning(f"⚠️  Modelo de culling não encontrado em {model_path}. Criado modelo novo.")

        self.model.to(self.device)
        self.model.eval()

    def predict(self, image_path: str) -> dict:
        """
        Prediz se deve manter (Keep) ou rejeitar (Reject) a imagem

        Args:
            image_path: Caminho para a imagem

        Returns:
            {
                'decision': 'keep' ou 'reject',
                'keep_probability': 0.0 - 1.0,
                'confidence': 0.0 - 1.0,
                'reasons': ['sharp', 'good_exposure', ...]
            }
        """
        with torch.no_grad():
            # Extrair features
            deep_features = self.deep_extractor.extract_single(image_path)
            stats_features = self.stats_extractor.extract_single(image_path)

            # Converter para tensors
            deep_tensor = torch.tensor(deep_features, dtype=torch.float32).unsqueeze(0).to(self.device)
            stats_tensor = torch.tensor(stats_features, dtype=torch.float32).unsqueeze(0).to(self.device)

            # Predição
            keep_prob = self.model(deep_tensor, stats_tensor).item()

            # Decisão (threshold = 0.5)
            decision = 'keep' if keep_prob >= 0.5 else 'reject'

            # Confiança (distância do threshold)
            confidence = abs(keep_prob - 0.5) * 2  # 0-1

            # Analisar razões (baseado em stats)
            reasons = self._analyze_reasons(stats_features, keep_prob)

            return {
                'decision': decision,
                'keep_probability': float(keep_prob),
                'confidence': float(confidence),
                'reasons': reasons
            }

    def _analyze_reasons(self, stats_features, keep_prob):
        """
        Analisa os motivos da decisão baseado em estatísticas

        Features esperadas (exemplo):
        [sharpness, exposure_ok, contrast_ok, saturation, highlights_clipped, ...]
        """
        reasons = []

        # Verificar sharpness (assumindo index 0)
        if len(stats_features) > 0:
            sharpness = stats_features[0]
            if sharpness > 0.6:
                reasons.append('sharp')
            elif sharpness < 0.3:
                reasons.append('blurry')

        # Verificar exposure (assumindo index 1)
        if len(stats_features) > 1:
            exposure_score = stats_features[1]
            if 0.4 <= exposure_score <= 0.6:
                reasons.append('good_exposure')
            elif exposure_score < 0.3:
                reasons.append('underexposed')
            elif exposure_score > 0.7:
                reasons.append('overexposed')

        # Verificar contraste (assumindo index 2)
        if len(stats_features) > 2:
            contrast = stats_features[2]
            if contrast > 0.5:
                reasons.append('good_contrast')
            elif contrast < 0.2:
                reasons.append('low_contrast')

        # Adicionar razão geral baseada em keep_prob
        if keep_prob >= 0.8:
            reasons.append('high_quality')
        elif keep_prob <= 0.2:
            reasons.append('poor_quality')

        return reasons if reasons else ['no_issues_detected']


def compute_stats_features(image_path: Path) -> np.ndarray:
    """
    Extrai features estatísticas rápidas da imagem

    Features:
    - Sharpness (variância de Laplacian)
    - Exposure (média de luminosidade normalizada)
    - Contraste (std de luminosidade)
    - Saturação média
    - Highlights clipped (% pixels > 250)
    - Shadows blocked (% pixels < 5)
    - Aspect ratio ok
    - File size normalizado
    - ISO normalizado
    - Focal length normalizado

    Returns:
        np.ndarray com 10 features normalizadas [0-1]
    """
    try:
        from PIL import Image
        import cv2

        # Carregar imagem
        img = Image.open(image_path)
        img_rgb = np.array(img.convert('RGB'))

        # Converter para grayscale e HSV
        img_gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
        img_hsv = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2HSV)

        features = []

        # 1. Sharpness (Laplacian variance)
        laplacian = cv2.Laplacian(img_gray, cv2.CV_64F)
        sharpness = laplacian.var()
        features.append(min(sharpness / 1000, 1.0))  # Normalizar

        # 2. Exposure (média de luminosidade V do HSV)
        exposure = img_hsv[:, :, 2].mean() / 255.0
        features.append(exposure)

        # 3. Contraste (std de luminosidade)
        contrast = img_gray.std() / 128.0  # Normalizar
        features.append(min(contrast, 1.0))

        # 4. Saturação média
        saturation = img_hsv[:, :, 1].mean() / 255.0
        features.append(saturation)

        # 5. Highlights clipped
        highlights_clipped = (img_gray > 250).sum() / img_gray.size
        features.append(highlights_clipped)

        # 6. Shadows blocked
        shadows_blocked = (img_gray < 5).sum() / img_gray.size
        features.append(shadows_blocked)

        # 7. Aspect ratio ok (perto de 3:2 ou 4:3)
        h, w = img_gray.shape
        aspect = w / h
        aspect_ok = 1.0 if 1.2 <= aspect <= 1.8 else 0.5
        features.append(aspect_ok)

        # 8. Resolução normalizada (megapixels / 50)
        megapixels = (w * h) / 1_000_000
        features.append(min(megapixels / 50, 1.0))

        # 9-10. Placeholder para EXIF (será preenchido se disponível)
        features.append(0.5)  # ISO placeholder
        features.append(0.5)  # Focal length placeholder

        return np.array(features, dtype=np.float32)

    except Exception as e:
        logger.error(f"Erro ao extrair stats features: {e}")
        # Retornar features neutras em caso de erro
        return np.array([0.5] * 10, dtype=np.float32)
