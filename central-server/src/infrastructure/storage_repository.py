import os
import json
from datetime import datetime
from typing import List, Optional, Tuple
from src.config.settings import Config
from src.domain.models import FileRecord

class StorageRepository:
    """
    Camada de Infraestrutura: Gerencia a leitura e escrita física de arquivos
    e a atualização do catálogo compartilhado (Região Crítica).
    """
    def __init__(self):
        os.makedirs(Config.STORAGE_DIR, exist_ok=True)
        if not os.path.exists(Config.CATALOG_FILE):
            self._save_catalog([])

    def _load_catalog(self) -> List[dict]:
        if not os.path.exists(Config.CATALOG_FILE):
            return []
        try:
            with open(Config.CATALOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _save_catalog(self, catalog: List[dict]) -> None:
        with open(Config.CATALOG_FILE, "w", encoding="utf-8") as f:
            json.dump(catalog, f, indent=2, ensure_ascii=False)

    def save_file(self, filename: str, content: bytes, client_id: str, server_id: str) -> FileRecord:
        """
        RExecutado DENTRO da Região Crítica (somente quando o servidor possui o Token).
        Salva o arquivo físico e atualiza o catálogo JSON compartilhado.
        """
        file_path = os.path.join(Config.STORAGE_DIR, filename)
        with open(file_path, "wb") as f:
            f.write(content)

        record = FileRecord(
            filename=filename,
            size=len(content),
            uploaded_by=client_id,
            handled_by_server=server_id,
            timestamp=datetime.now().isoformat(timespec="seconds")
        )

        catalog = self._load_catalog()
        # Atualiza se já existir, senão adiciona
        catalog = [item for item in catalog if item.get("filename") != filename]
        catalog.append(record.__dict__)
        self._save_catalog(catalog)

        return record

    def read_file(self, filename: str) -> Optional[bytes]:
        """
        Leitura livre: Não exige Token pois não altera estado na Região Crítica.
        """
        file_path = os.path.join(Config.STORAGE_DIR, filename)
        if not os.path.exists(file_path):
            return None
        with open(file_path, "rb") as f:
            return f.read()

    def list_files(self) -> List[FileRecord]:
        catalog = self._load_catalog()
        return [FileRecord(**item) for item in catalog]
