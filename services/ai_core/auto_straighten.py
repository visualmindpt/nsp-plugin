"""
Auto-Straighten - Detecção e correção automática do horizonte
Usa OpenCV HoughLines para detectar linhas horizontais e calcular ângulo de rotação
"""
import cv2
import numpy as np
from pathlib import Path
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def detect_horizon_angle(image_path: str, min_line_length: int = 200, angle_threshold: float = 45.0) -> Dict:
    """
    Detecta o ângulo do horizonte na imagem usando Hough Line Transform

    Args:
        image_path: Caminho para a imagem
        min_line_length: Comprimento mínimo de linha para detectar (threshold do HoughLines)
        angle_threshold: Ângulo máximo para considerar uma linha horizontal (graus)

    Returns:
        {
            'angle': float,  # Ângulo de rotação necessário em graus
            'confidence': float,  # Confiança da detecção (0-1)
            'requires_correction': bool,  # Se precisa correção (|angle| > 0.5°)
            'num_lines_detected': int,  # Número de linhas horizontais detectadas
            'recommendation': str  # 'rotate', 'none', ou 'manual_check'
        }
    """
    try:
        # Carregar imagem
        img = cv2.imread(str(image_path))
        if img is None:
            logger.error(f"Não foi possível carregar a imagem: {image_path}")
            return _default_result()

        # Converter para grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Aplicar Gaussian Blur para reduzir ruído
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Detectar bordas com Canny
        edges = cv2.Canny(blurred, 50, 150, apertureSize=3)

        # Detectar linhas com HoughLines
        lines = cv2.HoughLines(edges, 1, np.pi/180, min_line_length)

        if lines is None or len(lines) == 0:
            logger.info(f"Nenhuma linha detectada em {Path(image_path).name}")
            return _default_result()

        # Extrair ângulos de linhas horizontais
        horizontal_angles = []
        for line in lines:
            rho, theta = line[0]
            # Converter theta para graus (-90 a 90)
            angle = (theta * 180 / np.pi) - 90

            # Filtrar apenas linhas próximas da horizontal
            if -angle_threshold < angle < angle_threshold:
                horizontal_angles.append(angle)

        if not horizontal_angles:
            logger.info(f"Nenhuma linha horizontal detectada em {Path(image_path).name}")
            return _default_result()

        # Calcular ângulo mediano (mais robusto que média)
        median_angle = float(np.median(horizontal_angles))

        # Calcular desvio padrão para confiança
        std_angle = float(np.std(horizontal_angles))
        confidence = _calculate_confidence(std_angle, len(horizontal_angles))

        # Determinar se precisa correção (threshold de 0.5 graus)
        requires_correction = abs(median_angle) > 0.5

        # Recomendação
        if not requires_correction:
            recommendation = 'none'
        elif confidence > 0.7:
            recommendation = 'rotate'
        else:
            recommendation = 'manual_check'  # Baixa confiança, verificar manualmente

        result = {
            'angle': round(median_angle, 2),
            'confidence': round(confidence, 2),
            'requires_correction': requires_correction,
            'num_lines_detected': len(horizontal_angles),
            'recommendation': recommendation
        }

        logger.info(f"Auto-straighten para {Path(image_path).name}: {result}")
        return result

    except Exception as e:
        logger.error(f"Erro ao detectar horizonte em {image_path}: {e}")
        return _default_result()


def _calculate_confidence(std_angle: float, num_lines: int) -> float:
    """
    Calcula confiança da detecção baseado em:
    - Desvio padrão dos ângulos (quanto menor, melhor)
    - Número de linhas detectadas (quanto mais, melhor)

    Returns:
        Confiança entre 0.0 e 1.0
    """
    # Confiança baseada em desvio padrão (penaliza alta variação)
    # std < 2° = alta confiança, std > 10° = baixa confiança
    std_confidence = max(0.0, 1.0 - (std_angle / 10.0))

    # Confiança baseada em número de linhas
    # < 3 linhas = baixa, > 10 linhas = alta
    lines_confidence = min(1.0, num_lines / 10.0)

    # Combinar (peso maior para desvio padrão)
    confidence = (std_confidence * 0.7) + (lines_confidence * 0.3)

    return confidence


def _default_result() -> Dict:
    """Resultado padrão quando não há detecção"""
    return {
        'angle': 0.0,
        'confidence': 0.0,
        'requires_correction': False,
        'num_lines_detected': 0,
        'recommendation': 'manual_check'
    }


def apply_rotation(image_path: str, angle: float, output_path: Optional[str] = None) -> str:
    """
    Aplica rotação à imagem (para testes - normalmente feito no Lightroom)

    Args:
        image_path: Caminho da imagem original
        angle: Ângulo de rotação em graus
        output_path: Caminho para salvar (se None, sobrescreve)

    Returns:
        Caminho da imagem rotacionada
    """
    try:
        # Carregar imagem
        img = cv2.imread(str(image_path))
        if img is None:
            raise ValueError(f"Não foi possível carregar {image_path}")

        # Obter dimensões
        height, width = img.shape[:2]
        center = (width // 2, height // 2)

        # Criar matriz de rotação
        rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)

        # Aplicar rotação
        rotated = cv2.warpAffine(img, rotation_matrix, (width, height),
                                 flags=cv2.INTER_LINEAR,
                                 borderMode=cv2.BORDER_REFLECT)

        # Salvar
        output = output_path if output_path else image_path
        cv2.imwrite(str(output), rotated)

        logger.info(f"Imagem rotacionada {angle}° e salva em {output}")
        return str(output)

    except Exception as e:
        logger.error(f"Erro ao rotacionar imagem: {e}")
        raise


# Função de teste rápida
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Uso: python auto_straighten.py <caminho_imagem>")
        sys.exit(1)

    image_path = sys.argv[1]
    result = detect_horizon_angle(image_path)

    print("\n🔍 Análise de Auto-Straighten:")
    print(f"  Ângulo detectado: {result['angle']}°")
    print(f"  Confiança: {result['confidence']*100:.1f}%")
    print(f"  Precisa correção: {'Sim' if result['requires_correction'] else 'Não'}")
    print(f"  Linhas detectadas: {result['num_lines_detected']}")
    print(f"  Recomendação: {result['recommendation']}")

    if result['requires_correction'] and result['recommendation'] == 'rotate':
        print(f"\n💡 Sugestão: Rotacionar {result['angle']}° no Lightroom")
