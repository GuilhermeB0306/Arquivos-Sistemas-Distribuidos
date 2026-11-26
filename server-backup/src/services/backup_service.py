import logging
from typing import List, Optional
from src.config.settings import Config
from src.domain.models import BackupFileRecord
from src.infrastructure.backup_repository import BackupRepository

logger = logging.getLogger("BackupService")

class BackupReplicationService:
    # Servico do servidor de backup para salvar replicas e atender failover
    def __init__(self, repository: BackupRepository):
        self.repository = repository
        self.server_id = Config.SERVER_ID

    def replicate_chunk(
        self,
        original_filename: str,
        part_number: int,
        total_parts: int,
        chunk_filename: str,
        content: bytes,
        primary_server_id: str
    ) -> str:
        saved_path = self.repository.save_replicated_chunk(
            chunk_filename=chunk_filename,
            content=content
        )
        logger.info(
            f"[{self.server_id}] Replica da parte {part_number}/{total_parts} ('{chunk_filename}', "
            f"{len(content)} bytes) recebida de [{primary_server_id}] e salva em '{saved_path}'"
        )
        return saved_path

    def get_chunk_failover(self, chunk_filename: str) -> Optional[bytes]:
        logger.info(
            f"[{self.server_id}] Failover ativado: fornecendo copia da fatia '{chunk_filename}'"
        )
        return self.repository.read_replicated_chunk(chunk_filename)

    def get_file_map_failover(self, original_filename: str) -> Optional[BackupFileRecord]:
        logger.info(f"[{self.server_id}] Consultando metadados via backup para '{original_filename}'")
        return self.repository.get_file_map(original_filename)

    def list_files_failover(self) -> List[BackupFileRecord]:
        logger.info(f"[{self.server_id}] Listando arquivos via backup")
        return self.repository.list_all_files()
