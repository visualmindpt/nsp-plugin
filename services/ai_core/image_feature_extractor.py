import rawpy
import cv2
from PIL import Image
import numpy as np
from pathlib import Path
import logging
import time
from functools import wraps

logger = logging.getLogger(__name__)


def retry_on_io_error(max_retries=3, delay=0.5):
    """
    Decorator to retry file operations on I/O errors.
    Useful for external drives with connection issues.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (OSError, IOError, FileNotFoundError) as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"I/O error in {func.__name__} (attempt {attempt + 1}/{max_retries}): {e}. "
                            f"Retrying in {delay}s..."
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"Failed after {max_retries} attempts in {func.__name__}: {e}"
                        )
            raise last_error
        return wrapper
    return decorator

class ImageFeatureExtractor:
    def __init__(self):
        # Carregar o classificador de rostos uma vez na inicialização
        try:
            self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            if self.face_cascade.empty():
                logger.warning("Não foi possível carregar o classificador de rostos. A detecção de rostos pode não funcionar.")
        except Exception as e:
            logger.error(f"Erro ao carregar haarcascade para detecção de rostos: {e}")
            self.face_cascade = None
    
    def extract_all_features(self, image_path):
        """
        Extrai todas as features de uma imagem
        """
        # Carregar imagem (RAW ou JPEG)
        img = self._load_image(image_path)
        
        features = {}
        features.update(self._histogram_features(img))
        features.update(self._color_features(img))
        features.update(self._exposure_features(img))
        features.update(self._composition_features(img))
        
        return features
    
    @retry_on_io_error(max_retries=3, delay=1.0)
    def _load_image(self, path):
        """
        Carrega RAW ou JPEG com retry automático para problemas de I/O.

        Útil quando as fotos estão em discos externos que podem ter
        conexão instável ou problemas temporários de I/O.
        """
        path_str = str(path)

        # Verificar se o ficheiro existe antes de tentar carregar
        if not Path(path_str).exists():
            raise FileNotFoundError(f"Ficheiro não encontrado: {path_str}")

        if path_str.lower().endswith(('.cr2', '.nef', '.arw', '.dng', '.orf', '.rw2')): # Adicionado mais extensões RAW
            # RAW
            try:
                with rawpy.imread(path_str) as raw:
                    # Usar half_size para acelerar e reduzir memória para features
                    img = raw.postprocess(use_camera_wb=True, half_size=True, no_auto_bright=True, output_bps=8)
            except rawpy.LibRawFileUnsupportedError:
                logger.warning(f"Formato RAW não suportado para {path_str}, tentando PIL.")
                img = np.array(Image.open(path_str).convert('RGB'))
            except (OSError, IOError) as e:
                # I/O errors will be caught by the retry decorator
                logger.error(f"Erro de I/O ao processar RAW {path_str}: {e}, tentando PIL.")
                raise  # Re-raise to trigger retry
            except Exception as e:
                logger.error(f"Erro ao processar RAW {path_str}: {e}, tentando PIL.")
                try:
                    img = np.array(Image.open(path_str).convert('RGB'))
                except Exception as pil_error:
                    logger.error(f"Falha também com PIL para {path_str}: {pil_error}")
                    raise
        else:
            # JPEG/TIFF/PNG
            img = np.array(Image.open(path_str).convert('RGB'))

        # Resize para 512px (mais rápido e consistente para features)
        h, w = img.shape[:2]
        if max(h, w) > 512:
            scale = 512 / max(h, w)
            img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

        return img
    
    def _histogram_features(self, img):
        """
        Features baseadas em histograma
        """
        features = {}
        
        # Garantir que a imagem é RGB (3 canais)
        if img.ndim < 3 or img.shape[2] != 3:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB) # Converter para RGB se for grayscale
            
        for i, color in enumerate(['r', 'g', 'b']):
            hist = cv2.calcHist([img], [i], None, [256], [0, 256])
            hist = hist.flatten()
            if hist.sum() == 0: # Evitar divisão por zero para imagens totalmente pretas/brancas
                hist = np.ones_like(hist) # Substituir por um histograma uniforme para evitar erros
            hist = hist / hist.sum()  # Normalizar
            
            # Estatísticas do histograma
            # Usar np.arange(256) para os bins
            bins = np.arange(256)
            
            features[f'{color}_mean'] = np.sum(hist * bins) / 255
            features[f'{color}_std'] = np.sqrt(np.sum(hist * (bins - features[f'{color}_mean']*255)**2)) / 255
            features[f'{color}_skew'] = self._calculate_skewness(hist, bins)
            
            # Distribuição de intensidade
            features[f'{color}_shadows'] = np.sum(hist[:64])  # 0-25%
            features[f'{color}_midtones'] = np.sum(hist[64:192])  # 25-75%
            features[f'{color}_highlights'] = np.sum(hist[192:])  # 75-100%
        
        return features
    
    def _color_features(self, img):
        """
        Features de cor e temperatura
        """
        features = {}
        
        # Garantir que a imagem é RGB (3 canais)
        if img.ndim < 3 or img.shape[2] != 3:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB) # Converter para RGB se for grayscale

        # Temperatura de cor (ratio R/B)
        # Usar float para evitar overflow e garantir precisão
        r_mean = np.mean(img[:,:,0].astype(np.float32))
        b_mean = np.mean(img[:,:,2].astype(np.float32))
        features['color_temperature'] = r_mean / (b_mean + 1e-6)
        
        # Saturação média
        hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
        features['saturation_mean'] = np.mean(hsv[:,:,1]) / 255
        features['saturation_std'] = np.std(hsv[:,:,1]) / 255
        
        # Dominância de cor (mediana do hue)
        features['dominant_hue'] = np.median(hsv[:,:,0]) # Hue é 0-179 em OpenCV para 8-bit
        
        return features
    
    def _exposure_features(self, img):
        """
        Features relacionadas com exposição
        """
        features = {}
        
        # Brilho geral
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        features['brightness_mean'] = np.mean(gray) / 255
        features['brightness_std'] = np.std(gray) / 255
        
        # Clipping (zonas queimadas/subexpostas)
        features['clipped_highlights'] = np.sum(gray > 250) / gray.size
        features['clipped_shadows'] = np.sum(gray < 5) / gray.size
        
        # Contraste (diferença entre percentis)
        features['contrast_range'] = (np.percentile(gray, 95) - np.percentile(gray, 5)) / 255
        
        # Dynamic range
        features['dynamic_range'] = (np.max(gray) - np.min(gray)) / 255
        
        return features
    
    def _composition_features(self, img):
        """
        Features de composição
        """
        features = {}
        
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        
        # Deteção de rostos (útil para presets de retrato)
        if self.face_cascade:
            faces = self.face_cascade.detectMultiScale(gray, 1.1, 4)
            
            features['has_face'] = 1 if len(faces) > 0 else 0
            features['num_faces'] = len(faces)
            
            if len(faces) > 0:
                # Face ocupa quanto % da imagem
                face_areas = [w*h for (x,y,w,h) in faces]
                features['face_coverage'] = sum(face_areas) / (img.shape[0] * img.shape[1])
            else:
                features['face_coverage'] = 0
        else:
            features['has_face'] = 0
            features['num_faces'] = 0
            features['face_coverage'] = 0
        
        # Detecção de linhas (horizonte, arquitetura)
        try:
            edges = cv2.Canny(gray, 50, 150)
            lines = cv2.HoughLines(edges, 1, np.pi/180, 100)
            features['num_lines'] = len(lines) if lines is not None else 0
        except Exception as e:
            logger.warning(f"Erro na detecção de linhas: {e}")
            features['num_lines'] = 0
        
        return features
    
    def _calculate_skewness(self, hist, bins):
        """Calcula skewness do histograma"""
        # Certificar que o histograma está normalizado e os bins são os valores de intensidade
        mean = np.sum(hist * bins)
        std = np.sqrt(np.sum(hist * (bins - mean)**2))
        
        if std == 0: # Evitar divisão por zero
            return 0.0
            
        skew = np.sum(hist * ((bins - mean) / std)**3)
        return skew