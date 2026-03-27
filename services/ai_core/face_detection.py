#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Face Detection and Grouping System
Detecta faces em fotos e agrupa pessoas similares

Features:
- Face detection (OpenCV + deep learning)
- Face recognition (embeddings)
- Face clustering (agrupar mesma pessoa)
- Face quality scoring
- Batch processing

Data: 21 Novembro 2025
"""

import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import logging
from dataclasses import dataclass, field
import pickle
from sklearn.cluster import DBSCAN
from collections import defaultdict
from enum import Enum

logger = logging.getLogger(__name__)


class DetectionMethod(str, Enum):
    """Enum de métodos suportados para detecção de faces."""
    DNN = "dnn"
    HAAR = "haar"

    @classmethod
    def from_string(cls, value: str) -> "DetectionMethod":
        try:
            return cls[value.upper()]
        except KeyError:
            raise ValueError(f"Método de detecção inválido: {value}")


@dataclass
class FaceDetection:
    """Informação de uma face detectada"""
    image_path: str
    bbox: Tuple[int, int, int, int]  # (x, y, w, h)
    confidence: float
    embedding: Optional[np.ndarray] = None
    quality_score: float = 0.0
    person_id: Optional[int] = None
    method: DetectionMethod = DetectionMethod.DNN


@dataclass
class Person:
    """Grupo de faces da mesma pessoa"""
    person_id: int
    faces: List[FaceDetection] = field(default_factory=list)
    representative_face: Optional[FaceDetection] = None

    def add_face(self, face: FaceDetection):
        """Adiciona face ao grupo"""
        self.faces.append(face)

        # Update representative (escolher a de melhor qualidade)
        if self.representative_face is None or face.quality_score > self.representative_face.quality_score:
            self.representative_face = face

    @property
    def photo_count(self) -> int:
        """Número de fotos com esta pessoa"""
        return len(set(f.image_path for f in self.faces))

    @property
    def face_count(self) -> int:
        """Número total de faces detectadas"""
        return len(self.faces)


class FaceDetector:
    """
    Detecta faces em imagens usando deep learning

    Usa modelo DNN pré-treinado (mais preciso que Haar Cascades)
    """

    def __init__(self, model_type: str = 'opencv_dnn',
                 dnn_weights_path: Optional[str] = None,
                 dnn_config_path: Optional[str] = None):
        """
        Args:
            model_type: 'opencv_dnn' (preciso) ou 'haar' (rápido)
        """
        self.model_type = model_type
        self._dnn_weights_path = Path(dnn_weights_path) if dnn_weights_path else None
        self._dnn_config_path = Path(dnn_config_path) if dnn_config_path else None
        self.net = None
        self.face_cascade = None

        if model_type == 'opencv_dnn':
            if not self._load_dnn_model():
                logger.warning("⚠️ Falha ao carregar DNN, ativando fallback Haar")
                self._load_haar_cascade()
                self.model_type = 'haar'
            else:
                # Precarregar Haar para permitir troca dinâmica
                self._load_haar_cascade()
        else:
            self._load_haar_cascade()

    def _load_haar_cascade(self):
        """Carrega Haar Cascade (fallback)"""
        if getattr(self, 'face_cascade', None) is None:
            self.face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
            logger.info("✅ Face detection (Haar Cascade) carregado")

    def _load_dnn_model(self) -> bool:
        """Carrega modelo DNN pré-treinado."""
        if self.net is not None:
            return True

        try:
            if self._dnn_weights_path and self._dnn_config_path:
                prototxt = self._dnn_config_path
                caffemodel = self._dnn_weights_path
            else:
                model_path = Path(__file__).parent / 'models' / 'face_detection'
                prototxt = model_path / 'deploy.prototxt'
                caffemodel = model_path / 'res10_300x300_ssd_iter_140000.caffemodel'

            if prototxt.exists() and caffemodel.exists():
                self.net = cv2.dnn.readNetFromCaffe(str(prototxt), str(caffemodel))
                logger.info("✅ Face detection model (DNN) carregado")
                return True
            else:
                logger.warning("Modelo DNN não encontrado (deploy.prototxt/res10...).")
                return False
        except Exception as e:
            logger.error(f"Erro ao carregar modelo DNN: {e}")
            self.net = None
            return False

    def _ensure_method_available(self, method: DetectionMethod):
        """Garante que o método solicitado está carregado."""
        if method == DetectionMethod.DNN:
            if not self._load_dnn_model():
                raise RuntimeError("Modelo DNN indisponível. Verifique ficheiros em services/ai_core/models/face_detection.")
        else:
            if getattr(self, 'face_cascade', None) is None:
                self._load_haar_cascade()

    def detect(self, image_path: str, min_confidence: float = 0.5,
               method: Optional[DetectionMethod] = None) -> List[FaceDetection]:
        """
        Detecta faces numa imagem

        Args:
            image_path: Caminho da imagem
            min_confidence: Confiança mínima (0.0-1.0)
            method: Método de deteção (DNN/HAAR). Se None, usa self.model_type.

        Returns:
            Lista de faces detectadas
        """
        img = cv2.imread(str(image_path))
        if img is None:
            logger.error(f"Não foi possível ler imagem: {image_path}")
            return []

        detection_method = method or (DetectionMethod.DNN if self.model_type == 'opencv_dnn' else DetectionMethod.HAAR)
        self._ensure_method_available(detection_method)

        if detection_method == DetectionMethod.DNN:
            return self._detect_dnn(img, image_path, min_confidence)
        else:
            return self._detect_haar(img, image_path)

    def detect_faces(self, image_path: str, method: DetectionMethod = DetectionMethod.DNN,
                     min_confidence: float = 0.5) -> List[FaceDetection]:
        """Compat wrapper para API."""
        return self.detect(image_path, min_confidence=min_confidence, method=method)

    def _detect_dnn(self, img: np.ndarray, image_path: str, min_confidence: float) -> List[FaceDetection]:
        """Detecta faces usando DNN"""
        h, w = img.shape[:2]

        # Preparar input para o modelo
        blob = cv2.dnn.blobFromImage(
            cv2.resize(img, (300, 300)),
            1.0,
            (300, 300),
            (104.0, 177.0, 123.0)
        )

        self.net.setInput(blob)
        detections = self.net.forward()

        faces = []

        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]

            if confidence > min_confidence:
                # Get bounding box
                box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                (x, y, x2, y2) = box.astype("int")

                # Ensure box is within image bounds
                x = max(0, x)
                y = max(0, y)
                x2 = min(w, x2)
                y2 = min(h, y2)

                bbox_w = x2 - x
                bbox_h = y2 - y

                if bbox_w > 20 and bbox_h > 20:  # Min size
                    face = FaceDetection(
                        image_path=image_path,
                        bbox=(x, y, bbox_w, bbox_h),
                        confidence=float(confidence),
                        method=DetectionMethod.DNN
                    )
                    faces.append(face)

        logger.debug(f"Detectadas {len(faces)} faces em {Path(image_path).name}")
        return faces

    def _detect_haar(self, img: np.ndarray, image_path: str) -> List[FaceDetection]:
        """Detecta faces usando Haar Cascade"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        detected_faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30)
        )

        faces = []
        for (x, y, w, h) in detected_faces:
            face = FaceDetection(
                image_path=image_path,
                bbox=(x, y, w, h),
                confidence=1.0,  # Haar doesn't give confidence
                method=DetectionMethod.HAAR
            )
            faces.append(face)

        logger.debug(f"Detectadas {len(faces)} faces em {Path(image_path).name}")
        return faces


class FaceRecognizer:
    """
    Reconhecimento facial usando embeddings

    Gera embedding (vetor de características) para cada face
    Permite comparar similaridade entre faces
    """

    def __init__(self, model_path: Optional[str] = None):
        """Inicializa face recognizer"""
        try:
            if model_path:
                model_file = Path(model_path)
            else:
                model_dir = Path(__file__).parent / 'models' / 'face_recognition'
                model_file = model_dir / 'openface.nn4.small2.v1.t7'

            if model_file.exists():
                self.net = cv2.dnn.readNetFromTorch(str(model_file))
                self.use_embeddings = True
                logger.info(f"✅ Face recognition model carregado ({model_file.name})")
            else:
                logger.warning(f"Modelo de face recognition não encontrado ({model_file}). Usando histograma.")
                self.use_embeddings = False
        except Exception as e:
            logger.warning(f"Erro ao carregar face recognition: {e}")
            self.use_embeddings = False

    def extract_embedding(self, img: np.ndarray, bbox: Tuple[int, int, int, int]) -> np.ndarray:
        """
        Extrai embedding de uma face

        Args:
            img: Imagem completa
            bbox: Bounding box da face (x, y, w, h)

        Returns:
            Embedding vector (128-d ou histogram)
        """
        x, y, w, h = bbox

        # Extrair região da face
        face_img = img[y:y+h, x:x+w]

        if face_img.size == 0:
            return np.zeros(128 if self.use_embeddings else 256)

        if self.use_embeddings:
            return self._extract_embedding_dnn(face_img)
        else:
            return self._extract_embedding_histogram(face_img)

    def _extract_embedding_dnn(self, face_img: np.ndarray) -> np.ndarray:
        """Extrai embedding usando DNN"""
        # Preparar face
        face_blob = cv2.dnn.blobFromImage(
            face_img,
            1.0 / 255,
            (96, 96),
            (0, 0, 0),
            swapRB=True,
            crop=False
        )

        self.net.setInput(face_blob)
        embedding = self.net.forward()

        return embedding.flatten()

    def _extract_embedding_histogram(self, face_img: np.ndarray) -> np.ndarray:
        """Fallback: usar histograma de cor como 'embedding'"""
        # Converter para HSV
        hsv = cv2.cvtColor(face_img, cv2.COLOR_BGR2HSV)

        # Calcular histograma
        hist = cv2.calcHist([hsv], [0, 1], None, [32, 32], [0, 180, 0, 256])
        hist = cv2.normalize(hist, hist).flatten()

        return hist

    def compute_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """
        Calcula similaridade entre dois embeddings

        Returns:
            Similaridade 0.0-1.0 (higher = more similar)
        """
        # Usar cosine similarity
        dot = np.dot(embedding1, embedding2)
        norm = np.linalg.norm(embedding1) * np.linalg.norm(embedding2)

        if norm == 0:
            return 0.0

        similarity = dot / norm

        # Normalize to 0-1
        similarity = (similarity + 1) / 2

        return float(similarity)


class FaceGrouper:
    """
    Agrupa faces da mesma pessoa usando clustering
    """

    def __init__(self, similarity_threshold: float = 0.6):
        """
        Args:
            similarity_threshold: Threshold para considerar mesma pessoa (0.0-1.0)
        """
        self.similarity_threshold = similarity_threshold
        self.face_recognizer = FaceRecognizer()

    def group_faces(self, faces: List[FaceDetection]) -> List[Person]:
        """
        Agrupa faces por pessoa

        Args:
            faces: Lista de faces detectadas

        Returns:
            Lista de Person objects
        """
        if len(faces) == 0:
            return []

        logger.info(f"🧑 A agrupar {len(faces)} faces...")

        # Extract embeddings para todas as faces
        embeddings = []
        valid_faces = []

        for face in faces:
            if face.embedding is None:
                # Carregar imagem e extrair embedding
                img = cv2.imread(face.image_path)
                if img is not None:
                    embedding = self.face_recognizer.extract_embedding(img, face.bbox)
                    face.embedding = embedding
                    embeddings.append(embedding)
                    valid_faces.append(face)
            else:
                embeddings.append(face.embedding)
                valid_faces.append(face)

        if len(embeddings) == 0:
            return []

        embeddings = np.array(embeddings)

        # Clustering usando DBSCAN
        # eps = 1 - similarity_threshold (convert similarity to distance)
        eps = 1.0 - self.similarity_threshold

        clustering = DBSCAN(eps=eps, min_samples=1, metric='cosine')
        labels = clustering.fit_predict(embeddings)

        # Organizar em Person objects
        persons_dict = defaultdict(list)

        for face, label in zip(valid_faces, labels):
            face.person_id = int(label)
            persons_dict[label].append(face)

        # Criar Person objects
        persons = []
        for person_id, person_faces in persons_dict.items():
            person = Person(person_id=person_id)
            for face in person_faces:
                person.add_face(face)
            persons.append(person)

        # Sort por número de fotos
        persons.sort(key=lambda p: p.photo_count, reverse=True)

        logger.info(f"✅ Encontradas {len(persons)} pessoas diferentes")

        return persons


class FaceQualityScorer:
    """Avalia qualidade de faces detectadas"""

    @staticmethod
    def score(img: np.ndarray, bbox: Tuple[int, int, int, int]) -> float:
        """
        Calcula quality score de uma face

        Considera:
        - Tamanho (faces maiores = melhor)
        - Sharpness
        - Brightness
        - Frontalidade (se possível)

        Returns:
            Score 0-100
        """
        x, y, w, h = bbox

        # Extract face region
        face_img = img[y:y+h, x:x+w]

        if face_img.size == 0:
            return 0.0

        scores = []

        # 1. Size score (prefer larger faces)
        img_area = img.shape[0] * img.shape[1]
        face_area = w * h
        size_ratio = face_area / img_area

        # Ideal: face ocupa 10-30% da imagem
        if 0.1 <= size_ratio <= 0.3:
            size_score = 100
        elif size_ratio < 0.1:
            size_score = (size_ratio / 0.1) * 100
        else:
            size_score = max(0, 100 - (size_ratio - 0.3) * 200)

        scores.append(size_score)

        # 2. Sharpness score
        gray_face = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
        laplacian = cv2.Laplacian(gray_face, cv2.CV_64F)
        sharpness = laplacian.var()
        sharpness_score = min(100, (sharpness / 50) * 100)
        scores.append(sharpness_score)

        # 3. Brightness score (prefer well-lit faces)
        mean_brightness = gray_face.mean()
        # Ideal: 100-150
        if 100 <= mean_brightness <= 150:
            brightness_score = 100
        elif mean_brightness < 100:
            brightness_score = (mean_brightness / 100) * 100
        else:
            brightness_score = max(0, 100 - (mean_brightness - 150) / 2)

        scores.append(brightness_score)

        # Overall score (average)
        overall = np.mean(scores)

        return float(overall)


class FaceAnalysisSystem:
    """
    Sistema completo de análise facial

    Integra detection, recognition e grouping
    """

    def __init__(
        self,
        model_type: str = 'opencv_dnn',
        similarity_threshold: float = 0.6,
        dnn_model_path: Optional[str] = None,
        dnn_config_path: Optional[str] = None,
        recognition_model_path: Optional[str] = None
    ):
        self.detector = FaceDetector(
            model_type=model_type,
            dnn_weights_path=dnn_model_path,
            dnn_config_path=dnn_config_path
        )
        self.grouper = FaceGrouper(similarity_threshold=similarity_threshold)
        self.quality_scorer = FaceQualityScorer()
        self.recognizer = FaceRecognizer(model_path=recognition_model_path)

    def analyze_batch(
        self,
        image_paths: List[str],
        min_confidence: float = 0.5,
        compute_quality: bool = True
    ) -> Tuple[List[FaceDetection], List[Person]]:
        """
        Analisa batch de imagens

        Args:
            image_paths: Lista de caminhos
            min_confidence: Confiança mínima para detecção
            compute_quality: Se True, calcula quality scores

        Returns:
            (all_faces, persons)
        """
        logger.info(f"📸 A analisar {len(image_paths)} imagens...")

        all_faces = []

        for i, path in enumerate(image_paths):
            try:
                # Detect faces
                faces = self.detector.detect(path, min_confidence=min_confidence)

                # Compute quality scores
                if compute_quality and len(faces) > 0:
                    img = cv2.imread(path)
                    if img is not None:
                        for face in faces:
                            face.quality_score = self.quality_scorer.score(img, face.bbox)

                all_faces.extend(faces)

                if (i + 1) % 20 == 0:
                    logger.info(f"Progresso: {i+1}/{len(image_paths)}")

            except Exception as e:
                logger.error(f"Erro ao processar {path}: {e}")

        logger.info(f"✅ Detectadas {len(all_faces)} faces em {len(image_paths)} imagens")

        # Group faces by person
        if len(all_faces) > 0:
            persons = self.grouper.group_faces(all_faces)
        else:
            persons = []

        return all_faces, persons

    def export_groups(self, persons: List[Person], output_path: str):
        """
        Exporta grupos de pessoas para JSON
        """
        import json

        data = {
            'total_persons': len(persons),
            'persons': []
        }

        for person in persons:
            person_data = {
                'person_id': person.person_id,
                'photo_count': person.photo_count,
                'face_count': person.face_count,
                'representative_face': {
                    'image': person.representative_face.image_path,
                    'quality_score': person.representative_face.quality_score
                } if person.representative_face else None,
                'photos': list(set(f.image_path for f in person.faces))
            }
            data['persons'].append(person_data)

        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"📄 Grupos exportados: {output_path}")


# =============================================================================
# CLI Interface
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='NSP Face Detection & Grouping')
    parser.add_argument('images', nargs='+', help='Image paths or directory')
    parser.add_argument('--confidence', type=float, default=0.5, help='Min confidence (0.0-1.0)')
    parser.add_argument('--similarity', type=float, default=0.6, help='Similarity threshold (0.0-1.0)')
    parser.add_argument('--output', type=str, help='Output JSON file')
    parser.add_argument('--model', choices=['opencv_dnn', 'haar'], default='opencv_dnn')

    args = parser.parse_args()

    # Expand directories
    image_paths = []
    for path_str in args.images:
        path = Path(path_str)
        if path.is_dir():
            for ext in ['.jpg', '.jpeg', '.png']:
                image_paths.extend(path.glob(f'*{ext}'))
                image_paths.extend(path.glob(f'*{ext.upper()}'))
        else:
            image_paths.append(path)

    image_paths = [str(p) for p in image_paths]

    print(f"📸 A analisar {len(image_paths)} imagens...")

    # Run analysis
    system = FaceAnalysisSystem(
        model_type=args.model,
        similarity_threshold=args.similarity
    )

    all_faces, persons = system.analyze_batch(
        image_paths,
        min_confidence=args.confidence
    )

    # Print results
    print("\n" + "="*60)
    print("👥 RESULTADOS")
    print("="*60)

    print(f"\n✅ Total de faces detectadas: {len(all_faces)}")
    print(f"✅ Total de pessoas identificadas: {len(persons)}")

    print(f"\n📊 TOP 10 PESSOAS:")
    for i, person in enumerate(persons[:10], 1):
        print(f"{i}. Pessoa #{person.person_id}:")
        print(f"   Fotos: {person.photo_count}")
        print(f"   Faces: {person.face_count}")
        if person.representative_face:
            print(f"   Melhor foto: {Path(person.representative_face.image_path).name} (Q: {person.representative_face.quality_score:.1f})")

    # Export
    if args.output:
        system.export_groups(persons, args.output)

    print("\n✅ Análise completa!")
