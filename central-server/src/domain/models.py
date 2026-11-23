from dataclasses import dataclass

@dataclass
class FileRecord:
    filename: str
    size: int
    uploaded_by: str
    handled_by_server: str
    timestamp: str
