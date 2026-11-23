import os
import sqlite3
from typing import List, Optional
from src.config.settings import Config
from src.domain.models import BackupFileRecord, BackupChunkRecord

class BackupRepository:
    """
    Camada de Infraestrutura do Servidor de Backup (Redundância):
    - Armazena fisicamente as cópias redundantes de TODAS as fatias (part1 e part2)
      em storage_data/server-backup/.
    - Permite leitura de emergência (Failover) tanto das fatias quanto do Banco de Metadados
      caso central-1 ou central-2 caiam.
    """
    def __init__(self):
        os.makedirs(Config.STORAGE_DIR, exist_ok=True)
        os.makedirs(Config.BACKUP_STORAGE_DIR, exist_ok=True)

    def save_replicated_chunk(self, chunk_filename: str, content: bytes) -> str:
        backup_path = os.path.join(Config.BACKUP_STORAGE_DIR, chunk_filename)
        with open(backup_path, "wb") as f:
            f.write(content)
        return f"storage_data/{Config.SERVER_ID}/{chunk_filename}"

    def read_replicated_chunk(self, chunk_filename: str) -> Optional[bytes]:
        backup_path = os.path.join(Config.BACKUP_STORAGE_DIR, chunk_filename)
        if not os.path.exists(backup_path):
            return None
        with open(backup_path, "rb") as f:
            return f.read()

    def get_file_map(self, original_filename: str) -> Optional[BackupFileRecord]:
        if not os.path.exists(Config.METADATA_DB_PATH):
            return None
        with sqlite3.connect(Config.METADATA_DB_PATH, timeout=15.0) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT filename, original_size, total_parts, uploaded_by, timestamp FROM files WHERE filename = ?",
                (original_filename,)
            )
            row = cursor.fetchone()
            if not row:
                return None

            cursor.execute("""
                SELECT part_number, chunk_filename, server_id, server_grpc_address,
                       chunk_size, saved_path, backup_server_address, backup_saved_path
                FROM file_chunks
                WHERE filename = ?
                ORDER BY part_number ASC
            """, (original_filename,))
            chunks = [
                BackupChunkRecord(
                    part_number=c[0],
                    chunk_filename=c[1],
                    server_id=c[2],
                    server_grpc_address=c[3],
                    chunk_size=c[4],
                    saved_path=c[5],
                    backup_server_address=c[6] or f"{Config.SERVER_ID}:{Config.GRPC_PORT}",
                    backup_saved_path=c[7] or f"storage_data/{Config.SERVER_ID}/{c[1]}"
                )
                for c in cursor.fetchall()
            ]
            return BackupFileRecord(
                filename=row[0],
                original_size=row[1],
                total_parts=row[2],
                uploaded_by=row[3],
                timestamp=row[4],
                chunks=chunks
            )

    def list_all_files(self) -> List[BackupFileRecord]:
        if not os.path.exists(Config.METADATA_DB_PATH):
            return []
        with sqlite3.connect(Config.METADATA_DB_PATH, timeout=15.0) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT filename FROM files ORDER BY timestamp DESC")
            filenames = [r[0] for r in cursor.fetchall()]

        return [record for name in filenames if (record := self.get_file_map(name)) is not None]
