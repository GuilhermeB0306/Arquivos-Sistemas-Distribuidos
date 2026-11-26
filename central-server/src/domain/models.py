from dataclasses import dataclass, field
from typing import List

@dataclass
class ChunkRecord:
    part_number: int
    chunk_filename: str
    server_id: str
    server_grpc_address: str
    chunk_size: int
    saved_path: str
    backup_server_address: str = "server-backup:50053"
    backup_saved_path: str = ""
    chunk_sha256: str = ""

@dataclass
class FileRecord:
    filename: str
    original_size: int
    total_parts: int
    uploaded_by: str
    timestamp: str
    combined_file_sha256: str = ""
    chunks: List[ChunkRecord] = field(default_factory=list)
