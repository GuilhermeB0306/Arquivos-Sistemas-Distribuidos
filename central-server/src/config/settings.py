import os

class Config:
    """Configurações carregadas via variáveis de ambiente do Docker."""
    SERVER_ID = os.getenv("SERVER_ID", "central-1")
    GRPC_PORT = int(os.getenv("GRPC_PORT", "50051"))
    
    # Configurações do Anel (Token Ring)
    NEXT_NODE_ADDRESS = os.getenv("NEXT_NODE_ADDRESS", "central-2:50052")
    INITIAL_TOKEN_HOLDER = os.getenv("INITIAL_TOKEN_HOLDER", "false").lower() == "true"
    TOKEN_HOLD_TIME_SEC = float(os.getenv("TOKEN_HOLD_TIME_SEC", "2.0"))
    
    # Diretório compartilhado (Região Crítica)
    STORAGE_DIR = os.getenv("STORAGE_DIR", "/app/storage_data")
    CATALOG_FILE = os.path.join(STORAGE_DIR, "catalog.json")
