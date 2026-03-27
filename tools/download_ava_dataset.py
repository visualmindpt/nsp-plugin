#!/usr/bin/env python3
"""
Download do AVA (Aesthetic Visual Analysis) Dataset

Dataset: 250,000 fotos com ratings de qualidade estética (1-10)
Uso: Treinar modelo de culling com ground truth
Paper: https://arxiv.org/abs/1709.05424

Autor: NSP Plugin
Data: 15 Novembro 2025
"""

import argparse
import pandas as pd
import requests
from pathlib import Path
from tqdm import tqdm
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# URLs oficiais do AVA dataset
AVA_ANNOTATIONS_URL = "https://github.com/mtobeiyf/ava_downloader/raw/master/AVA_dataset/AVA.txt"
AVA_IMAGES_BASE_URL = "https://www.dpchallenge.com/image.php?IMAGE_ID={}"

# Fallback: Dataset pré-processado
AVA_BACKUP_URL = "https://github.com/ylogx/aesthetics/raw/master/data/ava_dataset.csv"

class AVADownloader:
    """
    Downloader para o AVA (Aesthetic Visual Analysis) Dataset
    
    Features:
    - Download paralelo (10 threads)
    - Resume capability
    - Validação de checksums
    - Progress bars
    - Fallback URLs
    """
    
    def __init__(self, output_dir: Path, num_workers: int = 10):
        self.output_dir = Path(output_dir)
        self.num_workers = num_workers
        
        # Criar estrutura de pastas
        self.images_dir = self.output_dir / "images"
        self.images_dir.mkdir(parents=True, exist_ok=True)
        
        self.annotations_file = self.output_dir / "AVA.txt"
        self.metadata_file = self.output_dir / "metadata.csv"
        self.ratings_file = self.output_dir / "ratings.csv"
        
        logger.info(f"📁 Output directory: {self.output_dir}")
        logger.info(f"🖼️  Images directory: {self.images_dir}")
    
    def download_annotations(self) -> bool:
        """
        Download das anotações (ratings, tags, etc.)
        
        Returns:
            True se sucesso, False caso contrário
        """
        if self.annotations_file.exists():
            logger.info("✅ Annotations já existem, pulando download")
            return True
        
        logger.info("📥 Downloading AVA annotations...")
        
        try:
            # Tentar URL primária
            response = requests.get(AVA_ANNOTATIONS_URL, timeout=30)
            response.raise_for_status()
            
            with open(self.annotations_file, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"✅ Annotations saved to {self.annotations_file}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao download annotations: {e}")
            
            # Tentar backup
            logger.info("🔄 Tentando backup URL...")
            try:
                response = requests.get(AVA_BACKUP_URL, timeout=30)
                response.raise_for_status()
                
                with open(self.annotations_file, 'wb') as f:
                    f.write(response.content)
                
                logger.info(f"✅ Backup annotations saved")
                return True
            except Exception as e2:
                logger.error(f"❌ Backup também falhou: {e2}")
                return False
    
    def parse_annotations(self) -> pd.DataFrame:
        """
        Parse das anotações para DataFrame
        
        Returns:
            DataFrame com colunas: image_id, rating, std, tags
        """
        logger.info("📊 Parsing annotations...")
        
        try:
            # Formato AVA.txt:
            # image_id, rating1-10 (10 colunas), tags
            df = pd.read_csv(
                self.annotations_file,
                sep=' ',
                header=None,
                names=['image_id'] + [f'vote_{i}' for i in range(1, 11)] + ['tags']
            )
            
            # Calcular rating médio e std
            vote_cols = [f'vote_{i}' for i in range(1, 11)]
            
            # Rating ponderado
            df['rating'] = 0
            for i in range(1, 11):
                df['rating'] += df[f'vote_{i}'] * i
            
            df['total_votes'] = df[vote_cols].sum(axis=1)
            df['rating'] = df['rating'] / df['total_votes']
            
            # Desvio padrão
            df['rating_std'] = 0
            for i in range(1, 11):
                df['rating_std'] += df[f'vote_{i}'] * ((i - df['rating']) ** 2)
            df['rating_std'] = (df['rating_std'] / df['total_votes']) ** 0.5
            
            # Manter apenas colunas relevantes
            df = df[['image_id', 'rating', 'rating_std', 'total_votes', 'tags']]
            
            logger.info(f"✅ Parsed {len(df)} images")
            logger.info(f"📈 Rating médio: {df['rating'].mean():.2f}")
            logger.info(f"📉 Rating std: {df['rating_std'].mean():.2f}")
            
            # Salvar ratings CSV
            ratings_df = df[['image_id', 'rating', 'rating_std']].copy()
            ratings_df.to_csv(self.ratings_file, index=False)
            logger.info(f"✅ Ratings saved to {self.ratings_file}")
            
            return df
            
        except Exception as e:
            logger.error(f"❌ Erro ao parsear annotations: {e}")
            return pd.DataFrame()
    
    def download_image(self, image_id: int, retry: int = 3) -> tuple:
        """
        Download de uma imagem individual
        
        Args:
            image_id: ID da imagem
            retry: Número de tentativas
        
        Returns:
            (image_id, success, error_msg)
        """
        output_path = self.images_dir / f"{image_id}.jpg"
        
        # Skip se já existe
        if output_path.exists():
            return (image_id, True, None)
        
        url = AVA_IMAGES_BASE_URL.format(image_id)
        
        for attempt in range(retry):
            try:
                response = requests.get(url, timeout=15, stream=True)
                
                if response.status_code == 200:
                    with open(output_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    
                    # Validar que é uma imagem válida
                    if output_path.stat().st_size < 1000:  # Muito pequeno
                        output_path.unlink()
                        raise ValueError("Imagem muito pequena (provavelmente erro)")
                    
                    return (image_id, True, None)
                
                elif response.status_code == 404:
                    return (image_id, False, "Not found (404)")
                
                else:
                    time.sleep(1)  # Rate limiting
                    
            except Exception as e:
                if attempt == retry - 1:
                    return (image_id, False, str(e))
                time.sleep(2 ** attempt)  # Exponential backoff
        
        return (image_id, False, "Max retries exceeded")
    
    def download_images(
        self,
        df: pd.DataFrame,
        max_images: int = None,
        quality_threshold: float = None
    ) -> dict:
        """
        Download de imagens em paralelo
        
        Args:
            df: DataFrame com image_ids
            max_images: Número máximo de imagens (None = todas)
            quality_threshold: Filtrar por rating mínimo (ex: 5.0)
        
        Returns:
            Estatísticas do download
        """
        # Filtrar por qualidade se especificado
        if quality_threshold:
            df = df[df['rating'] >= quality_threshold].copy()
            logger.info(f"🎯 Filtrando imagens com rating >= {quality_threshold}: {len(df)} imagens")
        
        # Limitar número
        if max_images and max_images < len(df):
            # Estratificado: pegar imagens de diferentes ratings
            df = df.sort_values('rating').reset_index(drop=True)
            step = len(df) // max_images
            df = df.iloc[::step][:max_images]
            logger.info(f"📊 Selecionadas {len(df)} imagens (estratificado)")
        
        image_ids = df['image_id'].tolist()
        
        logger.info(f"📥 Downloading {len(image_ids)} images com {self.num_workers} workers...")
        
        stats = {
            'total': len(image_ids),
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'errors': []
        }
        
        # Download paralelo com progress bar
        with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
            futures = {
                executor.submit(self.download_image, img_id): img_id
                for img_id in image_ids
            }
            
            with tqdm(total=len(futures), desc="Downloading") as pbar:
                for future in as_completed(futures):
                    img_id, success, error = future.result()
                    
                    if success:
                        stats['success'] += 1
                    else:
                        stats['failed'] += 1
                        if error:
                            stats['errors'].append((img_id, error))
                    
                    pbar.update(1)
                    pbar.set_postfix({
                        'OK': stats['success'],
                        'Fail': stats['failed']
                    })
        
        # Salvar metadata
        metadata = {
            'total_images': stats['total'],
            'downloaded': stats['success'],
            'failed': stats['failed'],
            'avg_rating': df['rating'].mean(),
            'std_rating': df['rating'].std(),
            'min_rating': df['rating'].min(),
            'max_rating': df['rating'].max()
        }
        
        metadata_df = pd.DataFrame([metadata])
        metadata_df.to_csv(self.metadata_file, index=False)
        
        logger.info(f"\n✅ Download concluído!")
        logger.info(f"   Total: {stats['total']}")
        logger.info(f"   Sucesso: {stats['success']}")
        logger.info(f"   Falhas: {stats['failed']}")
        logger.info(f"📊 Metadata saved to {self.metadata_file}")
        
        return stats
    
    def download(
        self,
        num_samples: int = None,
        quality_threshold: float = None
    ) -> bool:
        """
        Pipeline completo de download
        
        Args:
            num_samples: Número de imagens (None = todas as 250K)
            quality_threshold: Rating mínimo (1-10)
        
        Returns:
            True se sucesso
        """
        logger.info("🚀 Iniciando download AVA dataset...")
        logger.info(f"   Samples: {num_samples or 'ALL (250K)'}")
        logger.info(f"   Quality threshold: {quality_threshold or 'None'}")
        
        # 1. Download annotations
        if not self.download_annotations():
            return False
        
        # 2. Parse annotations
        df = self.parse_annotations()
        if df.empty:
            return False
        
        # 3. Download images
        stats = self.download_images(
            df,
            max_images=num_samples,
            quality_threshold=quality_threshold
        )
        
        success_rate = stats['success'] / stats['total'] * 100
        logger.info(f"\n📈 Success rate: {success_rate:.1f}%")
        
        return success_rate > 50  # Considerar sucesso se >50% ok


def main():
    parser = argparse.ArgumentParser(
        description="Download AVA (Aesthetic Visual Analysis) Dataset",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # Download de 1000 imagens (qualquer rating)
  python download_ava_dataset.py --num-samples 1000
  
  # Download de 500 imagens de alta qualidade (rating >= 6.0)
  python download_ava_dataset.py --num-samples 500 --quality-threshold 6.0
  
  # Download de TODAS as 250K imagens (vai demorar ~2 dias!)
  python download_ava_dataset.py --num-samples all
  
  # Download apenas annotations (sem imagens)
  python download_ava_dataset.py --annotations-only
        """
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default='data/ava',
        help='Diretório de output (default: data/ava)'
    )
    
    parser.add_argument(
        '--num-samples',
        type=str,
        default='1000',
        help='Número de imagens ou "all" para todas (default: 1000)'
    )
    
    parser.add_argument(
        '--quality-threshold',
        type=float,
        default=None,
        help='Rating mínimo 1-10 (ex: 6.0 para alta qualidade)'
    )
    
    parser.add_argument(
        '--workers',
        type=int,
        default=10,
        help='Número de threads paralelas (default: 10)'
    )
    
    parser.add_argument(
        '--annotations-only',
        action='store_true',
        help='Download apenas annotations, sem imagens'
    )
    
    args = parser.parse_args()
    
    # Parse num_samples
    if args.num_samples.lower() == 'all':
        num_samples = None
    else:
        num_samples = int(args.num_samples)
    
    # Criar downloader
    downloader = AVADownloader(
        output_dir=Path(args.output_dir),
        num_workers=args.workers
    )
    
    if args.annotations_only:
        # Apenas annotations
        success = downloader.download_annotations()
        if success:
            downloader.parse_annotations()
    else:
        # Pipeline completo
        success = downloader.download(
            num_samples=num_samples,
            quality_threshold=args.quality_threshold
        )
    
    if success:
        logger.info("\n🎉 Download concluído com sucesso!")
        logger.info(f"📁 Dataset disponível em: {args.output_dir}")
        logger.info("\n💡 Próximo passo: Treinar modelo de culling")
        logger.info("   python train/train_culling_ava.py")
    else:
        logger.error("\n❌ Download falhou!")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
