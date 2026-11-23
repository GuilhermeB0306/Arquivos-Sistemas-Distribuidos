import os

class Config:
    """Configurações do Servidor de Redundância / Backup."""
    SERVER_ID = os.getenv("SERVER_ID", "server-backup")
    GRPC_PORT = int(os.getenv("GRPC_PORT", "50053"))

    # Diretório base compartilhado
    STORAGE_DIR = os.getenv("STORAGE_DIR", "/app/storage_data")

    # Pasta exclusiva do Servidor de Backup (guarda cópias redundantes da Parte 1 e Parte 2)
    BACKUP_STORAGE_DIR = os.path.join(STORAGE_DIR, SERVER_ID)

    # Banco de Metadados SQLite (para consultas de Failover quando um Central estiver offline)
    METADATA_DB_PATH = os.path.join(STORAGE_DIR, "metadata_chunks.db")
