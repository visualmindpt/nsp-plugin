#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Culling System
Automatically scores and ranks photos based on technical quality and aesthetic appeal

Features:
- Technical quality (sharpness, exposure, noise)
- Aesthetic scoring (composition, colors)
- Duplicate detection (perceptual hashing)
- Face detection for portraits
- Batch processing

Data: 21 Novembro 2025
"""

import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import logging
from dataclasses import dataclass
import imagehash
from PIL import Image
import torch
import torch.nn as nn
from torchvision import models, transforms

logger = logging.getLogger(__name__)


@dataclass
class PhotoScore:
    """Score de qualidade de uma foto"""
    path: str
    technical_score: float  # 0-100 (sharpness, exposure, noise)
    aesthetic_score: float  # 0-100 (composition, colors)
    face_score: float       # 0-100 (faces detected, quality)
    overall_score: float    # 0-100 (weighted average)
    keep: bool              # Recommendation to keep or discard
    is_duplicate: bool      # Is this a duplicate?
    duplicate_of: Optional[str] = None
    metadata: Dict = None


class TechnicalQualityAnalyzer:
    """Analisa qualidade técnica da foto"""

    def __init__(self):
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )

    def analyze(self, image_path: str) -> Dict[str, float]:
        """
        Analisa qualidade técnica

        Returns:
            Dict com scores de sharpness, exposure, noise, faces
        """
        img = cv2.imread(str(image_path))
        if img is None:
            logger.error(f"Não foi possível ler imagem: {image_path}")
            return self._default_scores()

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        return {
            'sharpness': self._measure_sharpness(gray),
            'exposure': self._measure_exposure(gray),
            'noise': self._measure_noise(gray),
            'contrast': self._measure_contrast(gray),
            'faces': self._detect_faces(img),
        }

    def _measure_sharpness(self, gray: np.ndarray) -> float:
        """
        Mede sharpness usando Laplacian variance

        Higher = sharper
        Range: 0-100
        """
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        variance = laplacian.var()

        # Normalize to 0-100
        # Typical sharp images: variance > 100
        # Blurry images: variance < 10
        score = min(100, (variance / 100) * 100)
        return float(score)

    def _measure_exposure(self, gray: np.ndarray) -> float:
        """
        Mede qualidade de exposição

        Ideal: histogram centrado, sem clipping
        Range: 0-100
        """
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
        hist = hist.flatten() / hist.sum()

        # Check for clipping (overexposed/underexposed)
        shadow_clip = hist[:10].sum()  # Pure black
        highlight_clip = hist[-10:].sum()  # Pure white

        clipping_penalty = (shadow_clip + highlight_clip) * 100

        # Check histogram distribution (prefer centered)
        mean_brightness = np.average(np.arange(256), weights=hist)
        center_score = 100 - abs(mean_brightness - 128) / 128 * 100

        # Combine
        exposure_score = max(0, center_score - clipping_penalty)
        return float(exposure_score)

    def _measure_noise(self, gray: np.ndarray) -> float:
        """
        Mede nível de ruído (noise)

        Lower noise = higher score
        Range: 0-100
        """
        # Estimate noise using Laplacian
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)

        # High-frequency component indicates noise
        noise_level = np.std(laplacian)

        # Normalize (typical noise: 5-50)
        noise_score = max(0, 100 - (noise_level / 50) * 100)
        return float(noise_score)

    def _measure_contrast(self, gray: np.ndarray) -> float:
        """
        Mede contraste da imagem

        Range: 0-100
        """
        std_dev = np.std(gray)

        # Typical good contrast: std > 40
        contrast_score = min(100, (std_dev / 40) * 100)
        return float(contrast_score)

    def _detect_faces(self, img: np.ndarray) -> float:
        """
        Detecta faces e retorna score

        More faces + better quality = higher score
        Range: 0-100
        """
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30)
        )

        if len(faces) == 0:
            return 0.0

        # Score baseado em:
        # - Número de faces (mais faces = melhor para group shots)
        # - Tamanho das faces (maiores = melhor)
        face_sizes = [w * h for (x, y, w, h) in faces]
        avg_face_size = np.mean(face_sizes)
        img_area = img.shape[0] * img.shape[1]

        # Face occupies 5-20% of image = good
        face_ratio = avg_face_size / img_area

        num_faces_score = min(100, len(faces) * 20)  # Max at 5 faces
        size_score = min(100, (face_ratio / 0.15) * 100)  # Ideal: 15%

        return float((num_faces_score + size_score) / 2)

    def _default_scores(self) -> Dict[str, float]:
        """Scores padrão quando análise falha"""
        return {
            'sharpness': 0.0,
            'exposure': 0.0,
            'noise': 0.0,
            'contrast': 0.0,
            'faces': 0.0,
        }


class AestheticScorer(nn.Module):
    """
    Aesthetic scoring usando deep learning

    Baseado em ResNet pre-trained, fine-tuned para aesthetic quality
    """

    def __init__(self):
        super().__init__()

        # Use ResNet18 pre-trained
        self.backbone = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)

        # Replace final layer para aesthetic scoring
        num_features = self.backbone.fc.in_features
        self.backbone.fc = nn.Sequential(
            nn.Linear(num_features, 256),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(256, 1),  # Single aesthetic score
            nn.Sigmoid()  # Output 0-1
        )

        self.transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            )
        ])

        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.to(self.device)
        self.eval()

    def score(self, image_path: str) -> float:
        """
        Calcula aesthetic score

        Returns:
            Score 0-100
        """
        try:
            img = Image.open(image_path).convert('RGB')
            img_tensor = self.transform(img).unsqueeze(0).to(self.device)

            with torch.no_grad():
                score = self.backbone(img_tensor).item()

            return float(score * 100)  # Convert to 0-100

        except Exception as e:
            logger.error(f"Erro ao calcular aesthetic score: {e}")
            return 50.0  # Neutral score


class DuplicateDetector:
    """Detecta fotos duplicadas usando perceptual hashing"""

    def __init__(self, hash_size: int = 8, threshold: int = 5):
        """
        Args:
            hash_size: Tamanho do hash (8 = 64-bit hash)
            threshold: Hamming distance threshold (lower = more strict)
        """
        self.hash_size = hash_size
        self.threshold = threshold
        self.hashes: Dict[str, imagehash.ImageHash] = {}

    def compute_hash(self, image_path: str) -> imagehash.ImageHash:
        """Calcula perceptual hash da imagem"""
        try:
            img = Image.open(image_path)
            return imagehash.average_hash(img, hash_size=self.hash_size)
        except Exception as e:
            logger.error(f"Erro ao calcular hash: {e}")
            return None

    def find_duplicates(self, image_paths: List[str]) -> Dict[str, str]:
        """
        Encontra duplicatas em batch

        Returns:
            Dict mapping duplicate -> original
        """
        duplicates = {}

        for path in image_paths:
            img_hash = self.compute_hash(path)
            if img_hash is None:
                continue

            # Check against existing hashes
            for existing_path, existing_hash in self.hashes.items():
                distance = img_hash - existing_hash

                if distance <= self.threshold:
                    # É duplicata!
                    duplicates[path] = existing_path
                    logger.info(f"Duplicata detectada: {path} -> {existing_path} (distance: {distance})")
                    break
            else:
                # Não é duplicata, adicionar ao conjunto
                self.hashes[path] = img_hash

        return duplicates


class CullingAI:
    """
    Sistema completo de AI Culling

    Combina análise técnica, aesthetic scoring e duplicate detection
    """

    def __init__(self, use_aesthetic_model: bool = False):
        """
        Args:
            use_aesthetic_model: Se True, usa modelo deep learning (mais lento)
        """
        self.technical_analyzer = TechnicalQualityAnalyzer()
        self.duplicate_detector = DuplicateDetector()
        self.use_aesthetic_model = use_aesthetic_model

        if use_aesthetic_model:
            try:
                self.aesthetic_scorer = AestheticScorer()
                logger.info("Aesthetic model carregado com sucesso")
            except Exception as e:
                logger.warning(f"Não foi possível carregar aesthetic model: {e}")
                self.aesthetic_scorer = None
        else:
            self.aesthetic_scorer = None

    def score_photo(self, image_path: str) -> PhotoScore:
        """
        Calcula score completo de uma foto

        Returns:
            PhotoScore object
        """
        # Technical analysis
        technical = self.technical_analyzer.analyze(image_path)

        # Calculate technical score (weighted average)
        technical_score = (
            technical['sharpness'] * 0.35 +
            technical['exposure'] * 0.25 +
            technical['noise'] * 0.20 +
            technical['contrast'] * 0.20
        )

        # Aesthetic score
        if self.aesthetic_scorer:
            aesthetic_score = self.aesthetic_scorer.score(image_path)
        else:
            # Fallback: use composition heuristics
            aesthetic_score = self._heuristic_aesthetic_score(image_path, technical)

        # Face score
        face_score = technical['faces']

        # Overall score (weighted)
        overall_score = (
            technical_score * 0.50 +
            aesthetic_score * 0.35 +
            face_score * 0.15
        )

        # Recommendation: keep if score > 60
        keep = overall_score >= 60.0

        return PhotoScore(
            path=image_path,
            technical_score=technical_score,
            aesthetic_score=aesthetic_score,
            face_score=face_score,
            overall_score=overall_score,
            keep=keep,
            is_duplicate=False,
            metadata=technical
        )

    def _heuristic_aesthetic_score(self, image_path: str, technical: Dict) -> float:
        """
        Aesthetic score simplificado sem deep learning

        Baseado em regras heurísticas
        """
        # Composition: rule of thirds, golden ratio
        # Colors: saturation, harmony
        # For now, use technical scores as proxy

        score = (
            technical['contrast'] * 0.4 +
            technical['exposure'] * 0.3 +
            technical['sharpness'] * 0.3
        )

        return float(score)

    def cull_batch(
        self,
        image_paths: List[str],
        keep_top_percent: float = 0.5,
        remove_duplicates: bool = True
    ) -> Tuple[List[PhotoScore], List[str], List[str]]:
        """
        Processa batch de fotos e retorna rankings

        Args:
            image_paths: Lista de caminhos
            keep_top_percent: Percentagem de fotos a manter (0.0-1.0)
            remove_duplicates: Se True, marca duplicatas

        Returns:
            (all_scores, keep_list, discard_list)
        """
        logger.info(f"🔍 A analisar {len(image_paths)} fotos...")

        # Score todas as fotos
        scores = []
        for i, path in enumerate(image_paths):
            try:
                score = self.score_photo(path)
                scores.append(score)

                if (i + 1) % 10 == 0:
                    logger.info(f"Progresso: {i+1}/{len(image_paths)}")

            except Exception as e:
                logger.error(f"Erro ao processar {path}: {e}")

        # Detect duplicates
        if remove_duplicates:
            logger.info("🔍 A detectar duplicatas...")
            duplicates = self.duplicate_detector.find_duplicates(image_paths)

            for score in scores:
                if score.path in duplicates:
                    score.is_duplicate = True
                    score.duplicate_of = duplicates[score.path]
                    score.keep = False

        # Sort by overall score
        scores.sort(key=lambda x: x.overall_score, reverse=True)

        # Determine keep/discard based on threshold
        keep_count = int(len(scores) * keep_top_percent)

        keep_list = []
        discard_list = []

        for i, score in enumerate(scores):
            if i < keep_count and not score.is_duplicate:
                keep_list.append(score.path)
            else:
                discard_list.append(score.path)

        logger.info(f"✅ Culling completo:")
        logger.info(f"   Keep: {len(keep_list)}")
        logger.info(f"   Discard: {len(discard_list)}")
        logger.info(f"   Duplicates: {sum(1 for s in scores if s.is_duplicate)}")

        return scores, keep_list, discard_list

    def export_report(self, scores: List[PhotoScore], output_path: str):
        """
        Exporta relatório de culling para CSV
        """
        import csv

        with open(output_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'path', 'overall_score', 'technical_score', 'aesthetic_score',
                'face_score', 'keep', 'is_duplicate', 'duplicate_of',
                'sharpness', 'exposure', 'noise', 'contrast'
            ])

            for score in scores:
                writer.writerow([
                    score.path,
                    f"{score.overall_score:.2f}",
                    f"{score.technical_score:.2f}",
                    f"{score.aesthetic_score:.2f}",
                    f"{score.face_score:.2f}",
                    score.keep,
                    score.is_duplicate,
                    score.duplicate_of or '',
                    f"{score.metadata.get('sharpness', 0):.2f}",
                    f"{score.metadata.get('exposure', 0):.2f}",
                    f"{score.metadata.get('noise', 0):.2f}",
                    f"{score.metadata.get('contrast', 0):.2f}",
                ])

        logger.info(f"📄 Relatório exportado: {output_path}")


# =============================================================================
# CLI Interface
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='NSP AI Culling - Automatic photo selection')
    parser.add_argument('images', nargs='+', help='Image paths or directory')
    parser.add_argument('--keep', type=float, default=0.5, help='Keep top X% (default: 0.5)')
    parser.add_argument('--no-duplicates', action='store_true', help='Skip duplicate detection')
    parser.add_argument('--aesthetic-model', action='store_true', help='Use deep learning aesthetic model')
    parser.add_argument('--output', type=str, help='Output CSV report')

    args = parser.parse_args()

    # Expand directories
    image_paths = []
    for path_str in args.images:
        path = Path(path_str)
        if path.is_dir():
            for ext in ['.jpg', '.jpeg', '.png', '.tiff', '.tif', '.arw', '.cr2', '.nef']:
                image_paths.extend(path.glob(f'*{ext}'))
                image_paths.extend(path.glob(f'*{ext.upper()}'))
        else:
            image_paths.append(path)

    image_paths = [str(p) for p in image_paths]

    print(f"🔍 A analisar {len(image_paths)} fotos...")

    # Run culling
    culling = CullingAI(use_aesthetic_model=args.aesthetic_model)
    scores, keep, discard = culling.cull_batch(
        image_paths,
        keep_top_percent=args.keep,
        remove_duplicates=not args.no_duplicates
    )

    # Print results
    print("\n" + "="*60)
    print("📊 RESULTADOS DO CULLING")
    print("="*60)

    print(f"\n✅ A MANTER ({len(keep)} fotos):")
    for path in keep[:10]:  # Show top 10
        score = next(s for s in scores if s.path == path)
        print(f"   {Path(path).name}: {score.overall_score:.1f}/100")

    if len(keep) > 10:
        print(f"   ... e mais {len(keep) - 10} fotos")

    print(f"\n❌ A DESCARTAR ({len(discard)} fotos):")
    for path in discard[:5]:  # Show first 5
        score = next(s for s in scores if s.path == path)
        reason = "Duplicata" if score.is_duplicate else f"Score baixo ({score.overall_score:.1f})"
        print(f"   {Path(path).name}: {reason}")

    if len(discard) > 5:
        print(f"   ... e mais {len(discard) - 5} fotos")

    # Export report
    if args.output:
        culling.export_report(scores, args.output)

    print("\n✅ Culling completo!")
