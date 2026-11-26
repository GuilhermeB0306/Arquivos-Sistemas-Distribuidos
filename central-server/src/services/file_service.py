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
    """
    Camada de Serviço (Regras de Negócio dos Servidores Centrais):
    1. compute_chunk_sha256: Um Worker (Thread) deste Servidor Central calcula o hash SHA-256
       dos 50% do arquivo que recebeu.
    2. save_chunk: Exige posse do TOKEN (Token Ring) para:
       - Verificar no Banco SQLite se a SOMA dos hashes (Parte 1 + Parte 2 -> combined_file_sha256)
         já está cadastrada em um arquivo completo (Deduplicação Distribuída por Soma SHA-256);
       - Se for duplicado (100% igual), rejeita a gravação sem duplicar no disco;
       - Se for novo (ou se apenas 50% era igual), grava localmente, replica no Backup e salva no SQLite!
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

    def compute_chunk_sha256(self, part_number: int, chunk_filename: str, content: bytes) -> dict:
        """Worker Thread do Servidor Central que calcula o SHA-256 da sua metade (50%)."""
        worker_name = threading.current_thread().name
        chunk_hash = hashlib.sha256(content).hexdigest()
        logger.info(
            f"🔐 [{self.server_id} | Worker: {worker_name}] Calculou SHA-256 da Parte {part_number} "
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
        op_desc = f"Validar SHA-256 + Gravar Parte {part_number}/{total_parts} ('{chunk_filename}')"
        self.token_ring.enter_critical_section(op_desc)
        try:
            # Se o hash individual não veio preenchido, o worker calcula na hora
            if not chunk_sha256:
                chunk_sha256 = hashlib.sha256(content).hexdigest()

            # 1. VALIDAÇÃO DE DUPLICIDADE PELA SOMA DOS HASHES (Parte 1 + Parte 2) DENTRO DA REGIÃO CRÍTICA
            existing_file = self.repository.find_duplicate_by_combined_hash(combined_file_sha256)
            if existing_file is not None:
                logger.warning(
                    f"🚫 [{self.server_id} | Deduplicação SHA-256] Upload de '{original_filename}' BLOQUEADO! "
                    f"A soma dos hashes das 2 partes ({combined_file_sha256[:16]}...) já existe no arquivo '{existing_file}'!"
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
                        f"Duplicidade detectada via SHA-256! A soma das partes deste arquivo é idêntica "
                        f"ao arquivo '{existing_file}' já armazenado."
                    )
                }

            time.sleep(0.6)

            # 2. Replica a fatia via gRPC para o Container de Redundância (server-backup)
            backup_res = self.backup_client.replicate_chunk(
                original_filename=original_filename,
                part_number=part_number,
                total_parts=total_parts,
                chunk_filename=chunk_filename,
                content=content
            )

            # 3. Salva na pasta local deste Servidor Central e registra no Banco SQLite
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
                f"✅ [{self.server_id}] Parte {part_number}/{total_parts} validada (SHA-256 OK), "
                f"salva em '{saved_path}' e replicada em '{backup_res['backup_saved_path']}'!"
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
                "message": f"Parte {part_number}/{total_parts} validada via SHA-256, salva e replicada com posse do Token!"
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
