import time
import logging
from typing import List, Optional
from src.config.settings import Config
from src.domain.models import FileRecord
from src.infrastructure.storage_repository import StorageRepository
from src.services.token_ring_service import TokenRingService

logger = logging.getLogger("FileService")

class FileManagementService:
    """
    Camada de Serviço (Regras de Negócio):
    Coordena a leitura e escrita de arquivos integrando o StorageRepository com o TokenRingService.
    """
    def __init__(self, repository: StorageRepository, token_ring: TokenRingService):
        self.repository = repository
        self.token_ring = token_ring
        self.server_id = Config.SERVER_ID

    def upload_file(self, filename: str, content: bytes, client_id: str) -> FileRecord:
        """
        Operação de Escrita: Exige posse do Token para entrar na Região Crítica.
        """
        op_desc = f"Upload '{filename}' por {client_id}"
        self.token_ring.enter_critical_section(op_desc)
        try:
            # Simula um pequeno tempo de escrita em disco para evidenciar a concorrência nos logs
            time.sleep(1.0)
            record = self.repository.save_file(
                filename=filename,
                content=content,
                client_id=client_id,
                server_id=self.server_id
            )
            logger.info(f"✅ [{self.server_id}] Arquivo '{filename}' ({len(content)} bytes) gravado com sucesso!")
            return record
        finally:
            self.token_ring.exit_critical_section(op_desc)

    def download_file(self, filename: str) -> Optional[bytes]:
        """
        Operação de Leitura: Executa imediatamente em paralelo sem aguardar o Token.
        """
        logger.info(f"📥 [{self.server_id}] Atendendo leitura (Download) do arquivo '{filename}' (Livre de Token)")
        return self.repository.read_file(filename)

    def list_files(self) -> List[FileRecord]:
        """
        Operação de Leitura do Catálogo.
        """
        logger.info(f"📋 [{self.server_id}] Listando catálogo de arquivos")
        return self.repository.list_files()
