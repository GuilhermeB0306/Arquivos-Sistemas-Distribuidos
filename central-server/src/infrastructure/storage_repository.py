import os
import json
import sqlite3
from datetime import datetime
from typing import List, Optional
from src.config.settings import Config
from src.domain.models import FileRecord, ChunkRecord

class StorageRepository:
    # Gerencia a gravacao das fatias em disco e os registros no banco SQLite
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
                    timestamp TEXT,
                    combined_file_sha256 TEXT
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
                    chunk_sha256 TEXT,
                    PRIMARY KEY (filename, part_number)
                )
            """)
            cursor.execute("PRAGMA table_info(files)")
            file_cols = {row[1] for row in cursor.fetchall()}
            if "combined_file_sha256" not in file_cols:
                cursor.execute("ALTER TABLE files ADD COLUMN combined_file_sha256 TEXT")

            cursor.execute("PRAGMA table_info(file_chunks)")
            chunk_cols = {row[1] for row in cursor.fetchall()}
            if "backup_server_address" not in chunk_cols:
                cursor.execute("ALTER TABLE file_chunks ADD COLUMN backup_server_address TEXT")
            if "backup_saved_path" not in chunk_cols:
                cursor.execute("ALTER TABLE file_chunks ADD COLUMN backup_saved_path TEXT")
            if "chunk_sha256" not in chunk_cols:
                cursor.execute("ALTER TABLE file_chunks ADD COLUMN chunk_sha256 TEXT")
            conn.commit()

    def find_duplicate_by_combined_hash(self, combined_file_sha256: str) -> Optional[str]:
        # Verifica se a soma dos hashes SHA-256 das duas partes ja existe no banco
        if not combined_file_sha256:
            return None
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT f.filename
                FROM files f
                WHERE f.combined_file_sha256 = ?
                  AND (SELECT COUNT(*) FROM file_chunks fc WHERE fc.filename = f.filename) >= f.total_parts
                LIMIT 1
            """, (combined_file_sha256,))
            row = cursor.fetchone()
            return row[0] if row else None

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
        backup_saved_path: str,
        chunk_sha256: str,
        combined_file_sha256: str
    ) -> str:
        # Salva a fatia na pasta deste servidor
        local_chunk_path = os.path.join(Config.NODE_STORAGE_DIR, chunk_filename)
        with open(local_chunk_path, "wb") as f:
            f.write(content)

        relative_visual_path = f"storage_data/{Config.SERVER_ID}/{chunk_filename}"
        now_str = datetime.now().isoformat(timespec="seconds")

        # Registra os dados da fatia no SQLite
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO files (filename, original_size, total_parts, uploaded_by, timestamp, combined_file_sha256)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(filename) DO UPDATE SET
                    original_size=excluded.original_size,
                    total_parts=excluded.total_parts,
                    uploaded_by=excluded.uploaded_by,
                    timestamp=excluded.timestamp,
                    combined_file_sha256=excluded.combined_file_sha256
            """, (original_filename, original_size, total_parts, client_id, now_str, combined_file_sha256))

            cursor.execute("""
                INSERT INTO file_chunks (
                    filename, part_number, chunk_filename, server_id,
                    server_grpc_address, chunk_size, saved_path,
                    backup_server_address, backup_saved_path, chunk_sha256
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(filename, part_number) DO UPDATE SET
                    chunk_filename=excluded.chunk_filename,
                    server_id=excluded.server_id,
                    server_grpc_address=excluded.server_grpc_address,
                    chunk_size=excluded.chunk_size,
                    saved_path=excluded.saved_path,
                    backup_server_address=excluded.backup_server_address,
                    backup_saved_path=excluded.backup_saved_path,
                    chunk_sha256=excluded.chunk_sha256
            """, (
                original_filename,
                part_number,
                chunk_filename,
                Config.SERVER_ID,
                Config.SELF_GRPC_ADDRESS,
                len(content),
                relative_visual_path,
                backup_server_address,
                backup_saved_path,
                chunk_sha256
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
                "SELECT filename, original_size, total_parts, uploaded_by, timestamp, combined_file_sha256 FROM files WHERE filename = ?",
                (original_filename,)
            )
            row = cursor.fetchone()
            if not row:
                return None

            cursor.execute("""
                SELECT part_number, chunk_filename, server_id, server_grpc_address,
                       chunk_size, saved_path, backup_server_address, backup_saved_path, chunk_sha256
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
                    backup_saved_path=c[7] or f"storage_data/server-backup/{c[1]}",
                    chunk_sha256=c[8] or ""
                )
                for c in cursor.fetchall()
            ]
            return FileRecord(
                filename=row[0],
                original_size=row[1],
                total_parts=row[2],
                uploaded_by=row[3],
                timestamp=row[4],
                combined_file_sha256=row[5] or "",
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
                "combined_file_sha256": r.combined_file_sha256,
                "chunks": [c.__dict__ for c in r.chunks]
            }
            for r in records
        ]
        with open(Config.CATALOG_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
