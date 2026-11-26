import time
import hashlib
import threading
import logging
from typing import List, Optional
from src.config.settings import Config
from src.domain.models import FileRecord
from src.infrastructure.storage_repository import StorageRepository
from src.infrastructure.backup_grpc_client import BackupGrpcClient
from src.services.token_ring_service import TokenRingService

logger = logging.getLogger("FileService")

class FileManagementService:
    # Regras de negocio para calculo de hash, gravacao com Token Ring e leitura
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

    def compute_chunk_sha256(self, part_number: int, chunk_filename: str, content: bytes) -> dict:
        # Worker calcula o hash SHA-256 da metade recebida
        worker_name = threading.current_thread().name
        chunk_hash = hashlib.sha256(content).hexdigest()
        logger.info(
            f"[{self.server_id} | Worker: {worker_name}] Calculou SHA-256 da parte {part_number} "
            f"('{chunk_filename}'): {chunk_hash[:16]}..."
        )
        return {
            "part_number": part_number,
            "chunk_sha256": chunk_hash,
            "calculated_by_server": self.server_id,
            "worker_thread": worker_name
        }

    def save_chunk(
        self,
        original_filename: str,
        part_number: int,
        total_parts: int,
        chunk_filename: str,
        content: bytes,
        original_size: int,
        client_id: str,
        chunk_sha256: str,
        combined_file_sha256: str
    ) -> dict:
        op_desc = f"Parte {part_number}/{total_parts} ('{chunk_filename}')"
        self.token_ring.enter_critical_section(op_desc)
        try:
            if not chunk_sha256:
                chunk_sha256 = hashlib.sha256(content).hexdigest()

            # Verifica se a soma dos hashes ja existe no banco
            existing_file = self.repository.find_duplicate_by_combined_hash(combined_file_sha256)
            if existing_file is not None:
                logger.warning(
                    f"[{self.server_id}] Upload de '{original_filename}' bloqueado por duplicidade. "
                    f"Hash composto ja existe em '{existing_file}'"
                )
                return {
                    "success": False,
                    "is_duplicate": True,
                    "duplicate_of_filename": existing_file,
                    "chunk_path": "",
                    "backup_path": "",
                    "replicated": False,
                    "chunk_sha256": chunk_sha256,
                    "combined_file_sha256": combined_file_sha256,
                    "message": (
                        f"Duplicidade detectada via SHA-256. O arquivo enviado e identico "
                        f"ao arquivo '{existing_file}' ja armazenado."
                    )
                }

            time.sleep(0.6)

            # Envia copia para o servidor de backup
            backup_res = self.backup_client.replicate_chunk(
                original_filename=original_filename,
                part_number=part_number,
                total_parts=total_parts,
                chunk_filename=chunk_filename,
                content=content
            )

            # Salva localmente e atualiza o banco SQLite
            saved_path = self.repository.save_chunk_and_register(
                original_filename=original_filename,
                part_number=part_number,
                total_parts=total_parts,
                chunk_filename=chunk_filename,
                content=content,
                original_size=original_size,
                client_id=client_id,
                backup_server_address=backup_res["backup_server_address"],
                backup_saved_path=backup_res["backup_saved_path"],
                chunk_sha256=chunk_sha256,
                combined_file_sha256=combined_file_sha256
            )
            logger.info(
                f"[{self.server_id}] Parte {part_number}/{total_parts} salva em '{saved_path}' "
                f"e replicada em '{backup_res['backup_saved_path']}'"
            )
            return {
                "success": True,
                "is_duplicate": False,
                "duplicate_of_filename": "",
                "chunk_path": saved_path,
                "backup_path": backup_res["backup_saved_path"],
                "replicated": backup_res["replicated"],
                "chunk_sha256": chunk_sha256,
                "combined_file_sha256": combined_file_sha256,
                "message": f"Parte {part_number}/{total_parts} salva e replicada com sucesso."
            }
        finally:
            self.token_ring.exit_critical_section(op_desc)

    def get_chunk(self, chunk_filename: str) -> Optional[bytes]:
        logger.info(f"[{self.server_id}] Lendo fatia local '{chunk_filename}'")
        return self.repository.read_local_chunk(chunk_filename)

    def get_file_map(self, original_filename: str) -> Optional[FileRecord]:
        logger.info(f"[{self.server_id}] Consultando mapa de chunks para '{original_filename}'")
        return self.repository.get_file_map(original_filename)

    def list_files(self) -> List[FileRecord]:
        logger.info(f"[{self.server_id}] Listando catalogo de arquivos")
        return self.repository.list_all_files()
