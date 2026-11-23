import os
import json
import sqlite3
from datetime import datetime
from typing import List, Optional
from src.config.settings import Config
from src.domain.models import FileRecord, ChunkRecord

class StorageRepository:
    """
    Camada de Infraestrutura:
    1. Salva a metade (chunk) do arquivo na pasta EXCLUSIVA deste Servidor Central
       (ex: storage_data/central-1/arquivo.txt.part1 ou storage_data/central-2/arquivo.txt.part2).
    2. Registra no Banco de Dados SQLite compartilhado onde está a parte primária E onde está
       a cópia de redundância no 'server-backup' (Região Crítica protegida pelo Token Ring).
    """
    def __init__(self):
        os.makedirs(Config.STORAGE_DIR, exist_ok=True)
        os.makedirs(Config.NODE_STORAGE_DIR, exist_ok=True)
        self._init_sqlite_db()

    def _get_connection(self):
        return sqlite3.connect(Config.METADATA_DB_PATH, timeout=15.0)

    def _init_sqlite_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    filename TEXT PRIMARY KEY,
                    original_size INTEGER,
                    total_parts INTEGER,
                    uploaded_by TEXT,
                    timestamp TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS file_chunks (
                    filename TEXT,
                    part_number INTEGER,
                    chunk_filename TEXT,
                    server_id TEXT,
                    server_grpc_address TEXT,
                    chunk_size INTEGER,
                    saved_path TEXT,
                    backup_server_address TEXT,
                    backup_saved_path TEXT,
                    PRIMARY KEY (filename, part_number)
                )
            """)
            # Garante migração suave caso a tabela antiga não tivesse as colunas de backup
            cursor.execute("PRAGMA table_info(file_chunks)")
            existing_cols = {row[1] for row in cursor.fetchall()}
            if "backup_server_address" not in existing_cols:
                cursor.execute("ALTER TABLE file_chunks ADD COLUMN backup_server_address TEXT")
            if "backup_saved_path" not in existing_cols:
                cursor.execute("ALTER TABLE file_chunks ADD COLUMN backup_saved_path TEXT")
            conn.commit()

    def save_chunk_and_register(
        self,
        original_filename: str,
        part_number: int,
        total_parts: int,
        chunk_filename: str,
        content: bytes,
        original_size: int,
        client_id: str,
        backup_server_address: str,
        backup_saved_path: str
    ) -> str:
        # 1. Salva a fatia física na pasta exclusiva deste nó primário
        local_chunk_path = os.path.join(Config.NODE_STORAGE_DIR, chunk_filename)
        with open(local_chunk_path, "wb") as f:
            f.write(content)

        relative_visual_path = f"storage_data/{Config.SERVER_ID}/{chunk_filename}"
        now_str = datetime.now().isoformat(timespec="seconds")

        # 2. Registra no Banco SQLite o endereço do Servidor Central Primário E do Servidor de Backup
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO files (filename, original_size, total_parts, uploaded_by, timestamp)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(filename) DO UPDATE SET
                    original_size=excluded.original_size,
                    total_parts=excluded.total_parts,
                    uploaded_by=excluded.uploaded_by,
                    timestamp=excluded.timestamp
            """, (original_filename, original_size, total_parts, client_id, now_str))

            cursor.execute("""
                INSERT INTO file_chunks (
                    filename, part_number, chunk_filename, server_id,
                    server_grpc_address, chunk_size, saved_path,
                    backup_server_address, backup_saved_path
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(filename, part_number) DO UPDATE SET
                    chunk_filename=excluded.chunk_filename,
                    server_id=excluded.server_id,
                    server_grpc_address=excluded.server_grpc_address,
                    chunk_size=excluded.chunk_size,
                    saved_path=excluded.saved_path,
                    backup_server_address=excluded.backup_server_address,
                    backup_saved_path=excluded.backup_saved_path
            """, (
                original_filename,
                part_number,
                chunk_filename,
                Config.SERVER_ID,
                Config.SELF_GRPC_ADDRESS,
                len(content),
                relative_visual_path,
                backup_server_address,
                backup_saved_path
            ))
            conn.commit()

        self._export_catalog_json()
        return relative_visual_path

    def read_local_chunk(self, chunk_filename: str) -> Optional[bytes]:
        local_chunk_path = os.path.join(Config.NODE_STORAGE_DIR, chunk_filename)
        if not os.path.exists(local_chunk_path):
            return None
        with open(local_chunk_path, "rb") as f:
            return f.read()

    def get_file_map(self, original_filename: str) -> Optional[FileRecord]:
        with self._get_connection() as conn:
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
                ChunkRecord(
                    part_number=c[0],
                    chunk_filename=c[1],
                    server_id=c[2],
                    server_grpc_address=c[3],
                    chunk_size=c[4],
                    saved_path=c[5],
                    backup_server_address=c[6] or Config.BACKUP_SERVER_ADDRESS,
                    backup_saved_path=c[7] or f"storage_data/server-backup/{c[1]}"
                )
                for c in cursor.fetchall()
            ]
            return FileRecord(
                filename=row[0],
                original_size=row[1],
                total_parts=row[2],
                uploaded_by=row[3],
                timestamp=row[4],
                chunks=chunks
            )

    def list_all_files(self) -> List[FileRecord]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT filename FROM files ORDER BY timestamp DESC")
            filenames = [r[0] for r in cursor.fetchall()]

        return [record for name in filenames if (record := self.get_file_map(name)) is not None]

    def _export_catalog_json(self):
        records = self.list_all_files()
        data = [
            {
                "filename": r.filename,
                "original_size": r.original_size,
                "total_parts": r.total_parts,
                "uploaded_by": r.uploaded_by,
                "timestamp": r.timestamp,
                "chunks": [c.__dict__ for c in r.chunks]
            }
            for r in records
        ]
        with open(Config.CATALOG_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
