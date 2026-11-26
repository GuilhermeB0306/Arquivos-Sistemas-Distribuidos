import os

class Config:
    # Configuracoes do servidor carregadas via variaveis de ambiente
    SERVER_ID = os.getenv("SERVER_ID", "central-1")
    GRPC_PORT = int(os.getenv("GRPC_PORT", "50051"))
    SELF_GRPC_ADDRESS = os.getenv("SELF_GRPC_ADDRESS", f"{SERVER_ID}:{GRPC_PORT}")

    # Configuracoes do Token Ring
    NEXT_NODE_ADDRESS = os.getenv("NEXT_NODE_ADDRESS", "central-2:50052")
    INITIAL_TOKEN_HOLDER = os.getenv("INITIAL_TOKEN_HOLDER", "false").lower() == "true"
    TOKEN_HOLD_TIME_SEC = float(os.getenv("TOKEN_HOLD_TIME_SEC", "1.5"))

    # Endereco do servidor de backup
    BACKUP_SERVER_ADDRESS = os.getenv("BACKUP_SERVER_ADDRESS", "server-backup:50053")

    # Pastas de armazenamento e banco SQLite
    STORAGE_DIR = os.getenv("STORAGE_DIR", "/app/storage_data")
    NODE_STORAGE_DIR = os.path.join(STORAGE_DIR, SERVER_ID)
    METADATA_DB_PATH = os.path.join(STORAGE_DIR, "metadata_chunks.db")
    CATALOG_JSON_PATH = os.path.join(STORAGE_DIR, "catalog.json")
