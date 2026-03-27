import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
import xml.etree.ElementTree as ET
import logging
import zlib
import struct # Import struct for handling binary data
from typing import Optional, Union

logger = logging.getLogger(__name__)

class LightroomCatalogExtractor:
    def __init__(self, catalog_path):
        self.catalog_path = catalog_path
        self.conn = None
        
    def _connect(self):
        if not self.catalog_path.exists():
            raise FileNotFoundError(f"Catálogo Lightroom não encontrado em: {self.catalog_path}")
        self.conn = sqlite3.connect(self.catalog_path)
        
    def _disconnect(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def extract_edits(self, min_rating=3):
        """
        Extrai fotos editadas com suas configurações
        min_rating: só fotos com rating >= X (fotos que gostas)
        """
        self._connect()
        try:
            query = """
            SELECT 
                AgLibraryFile.idx_filename,
                AgLibraryFile.baseName,
                AgLibraryFolder.pathFromRoot,
                AgLibraryRootFolder.absolutePath,
                Adobe_images.rating,
                Adobe_images.fileFormat,
                Adobe_AdditionalMetadata.xmp
            FROM Adobe_images
            JOIN AgLibraryFile ON Adobe_images.rootFile = AgLibraryFile.id_local
            JOIN AgLibraryFolder ON AgLibraryFile.folder = AgLibraryFolder.id_local
            JOIN AgLibraryRootFolder ON AgLibraryFolder.rootFolder = AgLibraryRootFolder.id_local
            JOIN Adobe_AdditionalMetadata ON Adobe_images.id_local = Adobe_AdditionalMetadata.image
            WHERE Adobe_images.rating >= ?
            AND Adobe_AdditionalMetadata.xmp IS NOT NULL
            """
            
            df = pd.read_sql_query(query, self.conn, params=(min_rating,))
            return df
        finally:
            self._disconnect()
    
    def parse_xmp_settings(self, xmp_string):
        """
        Extrai parâmetros de edição do XMP
        """
        try: # Top-level try-except to catch any unexpected errors
            if not isinstance(xmp_string, (str, bytes)):
                logger.warning(f"Tipo de XMP inesperado: {type(xmp_string)}. Esperado str ou bytes. Retornando dicionário vazio.")
                return {}
            
            # Ensure xmp_string is bytes for ET.fromstring and zlib.decompress
            if isinstance(xmp_string, str):
                xmp_string = xmp_string.encode('utf-8')

            # Namespaces do Lightroom
            ns = {
                'crs': 'http://ns.adobe.com/camera-raw-settings/1.0/',
                'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#'
            }

            root = None
            try:
                root = ET.fromstring(xmp_string)
            except ET.ParseError:
                # If direct parsing fails, try to decompress (Lightroom often stores XMP compressed)
                try:
                    # Lightroom XMP is often deflated with a 4-byte length prefix
                    if isinstance(xmp_string, bytes) and len(xmp_string) >= 4:
                        # Read the first 4 bytes as the uncompressed length (little-endian)
                        uncompressed_length = struct.unpack('<I', xmp_string[:4])[0]
                        compressed_data = xmp_string[4:]
                        
                        decompressed_xmp = zlib.decompress(compressed_data).decode('utf-8')
                        root = ET.fromstring(decompressed_xmp)
                    else:
                        logger.warning(f"XMP string too short or not bytes for decompression attempt. Length: {len(xmp_string)}")
                        raise ET.ParseError("Not a valid XML or insufficient data for decompression", 0)
                except (zlib.error, UnicodeDecodeError, ET.ParseError, struct.error) as e:
                    logger.warning(f"Erro ao fazer parse/descomprimir XMP: {e}. String XMP (primeiros 200 chars): {xmp_string[:200]}...")
                    return {}
            
            if root is None:
                logger.warning("Não foi possível obter o root do XML após parsing ou descompressão.")
                return {}

            try:
                # TODOS os 58 parâmetros de edição do Lightroom
                params = {
                    # Basic (6)
                    'exposure': self._get_param(root, 'crs:Exposure2012', ns),
                    'contrast': self._get_param(root, 'crs:Contrast2012', ns),
                    'highlights': self._get_param(root, 'crs:Highlights2012', ns),
                    'shadows': self._get_param(root, 'crs:Shadows2012', ns),
                    'whites': self._get_param(root, 'crs:Whites2012', ns),
                    'blacks': self._get_param(root, 'crs:Blacks2012', ns),

                    # Presence (5)
                    'texture': self._get_param(root, 'crs:Texture', ns),
                    'clarity': self._get_param(root, 'crs:Clarity2012', ns),
                    'dehaze': self._get_param(root, 'crs:Dehaze', ns),
                    'vibrance': self._get_param(root, 'crs:Vibrance', ns),
                    'saturation': self._get_param(root, 'crs:Saturation', ns),

                    # White Balance (2)
                    'temp': self._get_param(root, 'crs:Temperature', ns),
                    'tint': self._get_param(root, 'crs:Tint', ns),

                    # Sharpening (4)
                    'sharpen_amount': self._get_param(root, 'crs:Sharpness', ns),
                    'sharpen_radius': self._get_param(root, 'crs:SharpenRadius', ns, 1.0),
                    'sharpen_detail': self._get_param(root, 'crs:SharpenDetail', ns, 25.0),
                    'sharpen_masking': self._get_param(root, 'crs:SharpenEdgeMasking', ns),

                    # Noise Reduction (3)
                    'nr_luminance': self._get_param(root, 'crs:LuminanceSmoothing', ns),
                    'nr_detail': self._get_param(root, 'crs:LuminanceNoiseReductionDetail', ns, 50.0),
                    'nr_color': self._get_param(root, 'crs:ColorNoiseReduction', ns, 25.0),

                    # Effects (2)
                    'vignette': self._get_param(root, 'crs:PostCropVignetteAmount', ns),
                    'grain': self._get_param(root, 'crs:GrainAmount', ns),

                    # Calibration (7)
                    'shadow_tint': self._get_param(root, 'crs:ShadowTint', ns),
                    'red_primary_hue': self._get_param(root, 'crs:RedHue', ns),
                    'red_primary_saturation': self._get_param(root, 'crs:RedSaturation', ns),
                    'green_primary_hue': self._get_param(root, 'crs:GreenHue', ns),
                    'green_primary_saturation': self._get_param(root, 'crs:GreenSaturation', ns),
                    'blue_primary_hue': self._get_param(root, 'crs:BlueHue', ns),
                    'blue_primary_saturation': self._get_param(root, 'crs:BlueSaturation', ns),

                    # HSL Completo (24 sliders = 8 cores x 3 ajustes)
                    'hsl_red_hue': self._get_param(root, 'crs:HueAdjustmentRed', ns),
                    'hsl_red_saturation': self._get_param(root, 'crs:SaturationAdjustmentRed', ns),
                    'hsl_red_luminance': self._get_param(root, 'crs:LuminanceAdjustmentRed', ns),

                    'hsl_orange_hue': self._get_param(root, 'crs:HueAdjustmentOrange', ns),
                    'hsl_orange_saturation': self._get_param(root, 'crs:SaturationAdjustmentOrange', ns),
                    'hsl_orange_luminance': self._get_param(root, 'crs:LuminanceAdjustmentOrange', ns),

                    'hsl_yellow_hue': self._get_param(root, 'crs:HueAdjustmentYellow', ns),
                    'hsl_yellow_saturation': self._get_param(root, 'crs:SaturationAdjustmentYellow', ns),
                    'hsl_yellow_luminance': self._get_param(root, 'crs:LuminanceAdjustmentYellow', ns),

                    'hsl_green_hue': self._get_param(root, 'crs:HueAdjustmentGreen', ns),
                    'hsl_green_saturation': self._get_param(root, 'crs:SaturationAdjustmentGreen', ns),
                    'hsl_green_luminance': self._get_param(root, 'crs:LuminanceAdjustmentGreen', ns),

                    'hsl_aqua_hue': self._get_param(root, 'crs:HueAdjustmentAqua', ns),
                    'hsl_aqua_saturation': self._get_param(root, 'crs:SaturationAdjustmentAqua', ns),
                    'hsl_aqua_luminance': self._get_param(root, 'crs:LuminanceAdjustmentAqua', ns),

                    'hsl_blue_hue': self._get_param(root, 'crs:HueAdjustmentBlue', ns),
                    'hsl_blue_saturation': self._get_param(root, 'crs:SaturationAdjustmentBlue', ns),
                    'hsl_blue_luminance': self._get_param(root, 'crs:LuminanceAdjustmentBlue', ns),

                    'hsl_purple_hue': self._get_param(root, 'crs:HueAdjustmentPurple', ns),
                    'hsl_purple_saturation': self._get_param(root, 'crs:SaturationAdjustmentPurple', ns),
                    'hsl_purple_luminance': self._get_param(root, 'crs:LuminanceAdjustmentPurple', ns),

                    'hsl_magenta_hue': self._get_param(root, 'crs:HueAdjustmentMagenta', ns),
                    'hsl_magenta_saturation': self._get_param(root, 'crs:SaturationAdjustmentMagenta', ns),
                    'hsl_magenta_luminance': self._get_param(root, 'crs:LuminanceAdjustmentMagenta', ns),

                    # Split Toning (5)
                    'split_highlight_hue': self._get_param(root, 'crs:SplitToningHighlightHue', ns),
                    'split_highlight_saturation': self._get_param(root, 'crs:SplitToningHighlightSaturation', ns),
                    'split_shadow_hue': self._get_param(root, 'crs:SplitToningShadowHue', ns),
                    'split_shadow_saturation': self._get_param(root, 'crs:SplitToningShadowSaturation', ns),
                    'split_balance': self._get_param(root, 'crs:SplitToningBalance', ns),

                    # Transform/Upright (2) - Endireitar horizonte com algoritmo nativo do Lightroom
                    'upright_version': self._get_param(root, 'crs:UprightVersion', ns, 1.0),
                    'upright_mode': self._get_param(root, 'crs:UprightTransform', ns, 0.0),
                    # Upright Modes: 0=Off, 1=Auto, 2=Level, 3=Vertical, 4=Full, 5=Guided
                }
                return params
            except Exception as e:
                logger.warning(f"Erro ao construir dicionário de parâmetros XMP: {e}. Retornando dicionário vazio.")
                return {}
        except Exception as e:
            logger.error(f"Erro inesperado em parse_xmp_settings: {type(e).__name__}: {e}. String XMP (primeiros 200 chars): {xmp_string[:200]}...")
            return {}
    
    def _get_param(self, root, param_name, ns, default=0.0):
        """Helper para extrair parâmetro individual, procurando em atributos do rdf:Description."""
        try:
            # O param_name já inclui o prefixo 'crs:', então precisamos separá-lo
            ns_prefix, tag_name = param_name.split(':', 1)
            
            # Encontra o elemento rdf:Description
            description_elem = root.find('.//rdf:Description', ns)
            
            if description_elem is not None:
                # Constrói o nome do atributo com o namespace completo
                attr_full_name = f"{{{ns[ns_prefix]}}}{tag_name}"
                
                if attr_full_name in description_elem.attrib:
                    return float(description_elem.attrib[attr_full_name])
            
            return default
        except Exception as e:
            logger.debug(f"Erro ao extrair parâmetro {param_name}: {e}")
            return default
    
    def create_dataset(
        self,
        output_path: str = 'lightroom_dataset.csv',
        min_rating: int = 3,
        image_root_override: Optional[Union[str, Path]] = None,
    ):
        """
        Cria dataset completo para treino.
        Se image_root_override for fornecido, ele substitui o caminho absoluto vindo do catálogo.

        Filtra automaticamente:
        - Ficheiros que não existem no disco
        - Referências a outros catálogos
        - Ficheiros movidos ou apagados
        """
        df = self.extract_edits(min_rating=min_rating)
        total_in_catalog = len(df)

        override_root = None
        if image_root_override:
            override_root = Path(image_root_override)
            logger.info(f"Override de caminho raiz para imagens definido: {override_root}")

        logger.info(f"📊 Processing {total_in_catalog} photos from catalog...")

        settings_list = []
        skipped_not_found = 0
        skipped_not_file = 0
        for idx, row in df.iterrows():
            try:
                settings = self.parse_xmp_settings(row['xmp'])

                catalog_root = None
                raw_root = row.get('absolutePath')
                if override_root is not None:
                    catalog_root = override_root
                elif isinstance(raw_root, str) and raw_root.strip():
                    catalog_root = Path(raw_root.strip())

                if catalog_root is None:
                    logger.warning(f"Sem caminho raiz válido para {row['idx_filename']}, ignorando imagem.")
                    continue

                relative_path = ''
                raw_relative = row.get('pathFromRoot')
                if isinstance(raw_relative, str):
                    relative_path = raw_relative.replace(':', '/').strip('/').strip()

                if relative_path:
                    full_image_path = catalog_root / Path(relative_path) / row['idx_filename']
                else:
                    full_image_path = catalog_root / row['idx_filename']

                # VALIDAÇÃO: Verificar se o ficheiro existe antes de adicionar
                if not full_image_path.exists():
                    skipped_not_found += 1
                    if skipped_not_found <= 5:  # Mostrar só os primeiros 5
                        logger.debug(f"Ficheiro não existe, ignorando: {full_image_path}")
                    continue

                # Verificar se é um ficheiro (não diretório)
                if not full_image_path.is_file():
                    skipped_not_file += 1
                    logger.warning(f"Caminho não é ficheiro, ignorando: {full_image_path}")
                    continue

                settings['image_path'] = str(full_image_path)
                settings['rating'] = row['rating']
                settings_list.append(settings)
            except Exception as e:
                logger.error(f"Erro ao processar XMP para {row['baseName']}: {e}")

        # Sumário da filtragem
        new_dataset = pd.DataFrame(settings_list)
        logger.info("")
        logger.info("=" * 70)
        logger.info("📊 CATALOG PROCESSING SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Total photos in catalog: {total_in_catalog}")
        logger.info(f"Valid photos (exist on disk): {len(settings_list)}")
        if skipped_not_found > 0:
            logger.info(f"⚠️  Skipped (file not found): {skipped_not_found}")
            logger.info(f"   These are likely from other catalogs or were moved/deleted")
        if skipped_not_file > 0:
            logger.info(f"⚠️  Skipped (not a file): {skipped_not_file}")
        logger.info(f"✅ Photos ready for training: {len(settings_list)}")
        logger.info("=" * 70)
        logger.info("")

        # NOTA: Para treino incremental, cada catálogo deve gerar seu próprio dataset
        # O MODELO é que acumula conhecimento, não o dataset CSV!
        # Dataset CSV é apenas entrada temporária para o treino atual

        dataset = new_dataset
        dataset.to_csv(output_path, index=False)
        logger.info(f"✅ Dataset criado com {len(dataset)} imagens para este catálogo")
        logger.info(f"   Saved to: {output_path}")
        logger.info("")
        logger.info("💡 Note: For incremental training:")
        logger.info("   - This dataset contains ONLY photos from current catalog")
        logger.info("   - Previous knowledge is in the MODEL (not in this CSV)")
        logger.info("   - Model will be fine-tuned with these new photos")
        logger.info("")
        return dataset
