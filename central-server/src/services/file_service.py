import time
import logging
from typing import List, Optional
from src.config.settings import Config
from src.domain.models import FileRecord
from src.infrastructure.storage_repository import StorageRepository
from src.infrastructure.backup_grpc_client import BackupGrpcClient
from src.services.token_ring_service import TokenRingService

logger = logging.getLogger("FileService")

class FileManagementService:
    """
    Camada de Serviço (Regras de Negócio dos Servidores Centrais):
    - SaveChunk: Exige posse do TOKEN (Token Ring) para:
      1. Gravar a metade do arquivo localmente (storage_data/central-X/);
      2. Replicar uma cópia de segurança via gRPC para o 'server-backup';
      3. Registrar ambos os caminhos no Banco de Metadados SQLite na Região Crítica.
    """
    def __init__(
        self,
        repository: StorageRepository,
        token_ring: TokenRingService,
        backup_client: BackupGrpcClient
    ):
        self.repository = repository
        self.token_ring = token_ring
        self.backup_client = backup_client
        self.server_id = Config.SERVER_ID

    def save_chunk(
        self,
        original_filename: str,
        part_number: int,
        total_parts: int,
        chunk_filename: str,
        content: bytes,
        original_size: int,
        client_id: str
    ) -> dict:
        op_desc = f"Gravar + Replicar Parte {part_number}/{total_parts} ('{chunk_filename}') por {client_id}"
        self.token_ring.enter_critical_section(op_desc)
        try:
            time.sleep(0.8)

            # 1. Replica a fatia via gRPC para o Container de Redundância (server-backup)
            backup_res = self.backup_client.replicate_chunk(
                original_filename=original_filename,
                part_number=part_number,
                total_parts=total_parts,
                chunk_filename=chunk_filename,
                content=content
            )

            # 2. Salva na pasta local deste Servidor Central e registra no Banco SQLite
            saved_path = self.repository.save_chunk_and_register(
                original_filename=original_filename,
                part_number=part_number,
                total_parts=total_parts,
                chunk_filename=chunk_filename,
                content=content,
                original_size=original_size,
                client_id=client_id,
                backup_server_address=backup_res["backup_server_address"],
                backup_saved_path=backup_res["backup_saved_path"]
            )
            logger.info(
                f"✅ [{self.server_id}] Parte {part_number}/{total_parts} salva em '{saved_path}' "
                f"e replicada em '{backup_res['backup_saved_path']}'!"
            )
            return {
                "chunk_path": saved_path,
                "backup_path": backup_res["backup_saved_path"],
                "replicated": backup_res["replicated"]
            }
        finally:
            self.token_ring.exit_critical_section(op_desc)

    def get_chunk(self, chunk_filename: str) -> Optional[bytes]:
        logger.info(f"📥 [{self.server_id}] Lendo fatia local '{chunk_filename}' (Leitura Livre)")
        return self.repository.read_local_chunk(chunk_filename)

    def get_file_map(self, original_filename: str) -> Optional[FileRecord]:
        logger.info(f"🗺️ [{self.server_id}] Consultando Mapa de Chunks no Banco para '{original_filename}'")
        return self.repository.get_file_map(original_filename)

    def list_files(self) -> List[FileRecord]:
        logger.info(f"📋 [{self.server_id}] Consultando catálogo completo de arquivos fatiados")
        return self.repository.list_all_files()
