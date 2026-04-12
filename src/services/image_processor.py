"""
Serviço de processamento de imagens
Preparado para fase 2: API de upload de fotos
"""

from typing import Optional, Dict


class ImageProcessor:
    """Serviço para processar imagens (preparado para fase 2)"""
    
    def __init__(self):
        """Inicializar processador de imagens"""
        print("ℹ️  ImageProcessor carregado (não implementado - fase 2)")
    
    def process_from_file(self, image_path: str) -> Optional[Dict]:
        """
        Processar imagem de arquivo
        
        Args:
            image_path: Caminho da imagem
            
        Returns:
            Dict: Dados extraídos da imagem ou None
        """
        raise NotImplementedError("Implementado na fase 2 (API de fotos)")
    
    def process_from_bytes(self, image_bytes: bytes) -> Optional[Dict]:
        """
        Processar imagem de bytes
        
        Args:
            image_bytes: Conteúdo da imagem em bytes
            
        Returns:
            Dict: Dados extraídos da imagem ou None
        """
        raise NotImplementedError("Implementado na fase 2 (API de fotos)")
    
    def validate_image(self, image_bytes: bytes) -> bool:
        """
        Validar se é uma imagem válida
        
        Args:
            image_bytes: Conteúdo da imagem
            
        Returns:
            bool: True se válida
        """
        raise NotImplementedError("Implementado na fase 2 (API de fotos)")


if __name__ == "__main__":
    processor = ImageProcessor()
    print("ImageProcessor carregado com sucesso")
