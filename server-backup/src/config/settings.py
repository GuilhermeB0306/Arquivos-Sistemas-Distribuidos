import os

class Config:
    # Configuracoes do servidor de backup
    SERVER_ID = os.getenv("SERVER_ID", "server-backup")
    GRPC_PORT = int(os.getenv("GRPC_PORT", "50053"))
    STORAGE_DIR = os.getenv("STORAGE_DIR", "/app/storage_data")
    BACKUP_STORAGE_DIR = os.path.join(STORAGE_DIR, SERVER_ID)
    METADATA_DB_PATH = os.path.join(STORAGE_DIR, "metadata_chunks.db")
