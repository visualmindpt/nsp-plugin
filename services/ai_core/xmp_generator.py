from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class XMPGenerator:
    def __init__(self):
        # Template XMP com placeholders para os parâmetros
        self.xmp_template = """<?xml version="1.0" encoding="UTF-8"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="Adobe XMP Core 7.0-c000">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description rdf:about=""
      xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/">
      <crs:Version>15.0</crs:Version>
      <crs:ProcessVersion>11.0</crs:ProcessVersion>
      <crs:WhiteBalance>As Shot</crs:WhiteBalance>
      <crs:Exposure2012>{exposure}</crs:Exposure2012>
      <crs:Contrast2012>{contrast}</crs:Contrast2012>
      <crs:Highlights2012>{highlights}</crs:Highlights2012>
      <crs:Shadows2012>{shadows}</crs:Shadows2012>
      <crs:Whites2012>{whites}</crs:Whites2012>
      <crs:Blacks2012>{blacks}</crs:Blacks2012>
      <crs:Temperature>{temperature}</crs:Temperature>
      <crs:Tint>{tint}</crs:Tint>
      <crs:Vibrance>{vibrance}</crs:Vibrance>
      <crs:Saturation>{saturation}</crs:Saturation>
      <crs:Clarity2012>{clarity}</crs:Clarity2012>
      <crs:Dehaze>{dehaze}</crs:Dehaze>
      <crs:Sharpness>{sharpness}</crs:Sharpness>
      <crs:LuminanceSmoothing>{noise_reduction}</crs:LuminanceSmoothing>
      <crs:HasSettings>True</crs:HasSettings>
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>"""
    
    def generate(self, params, output_path):
        """
        Gera ficheiro XMP com os parâmetros preditos
        """
        # Formatar valores para 2 casas decimais
        formatted_params = {k: f"{v:.2f}" for k, v in params.items()}
        
        try:
            # Preencher template
            xmp_content = self.xmp_template.format(**formatted_params)
            
            # Guardar
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(xmp_content)
            
            logger.info(f"✅ XMP guardado: {output_path}")
        except KeyError as e:
            logger.error(f"Parâmetro em falta no template XMP: {e}. Verifique se todos os parâmetros esperados estão presentes.")
            raise
        except Exception as e:
            logger.error(f"Erro ao gerar ou guardar XMP em {output_path}: {e}")
            raise
    
    def generate_for_image(self, image_path, params):
        """
        Cria XMP sidecar para uma imagem específica
        """
        image_path_obj = Path(image_path)
        xmp_path = image_path_obj.with_suffix('.xmp')
        self.generate(params, xmp_path)
        return xmp_path
