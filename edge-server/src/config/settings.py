import os

class Config:
    # Configuracoes do servidor de borda
    EDGE_ID = os.getenv("EDGE_ID", "edge-server")
    REST_PORT = int(os.getenv("REST_PORT", "8080"))

    # Configuracoes do JWT
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "chave-secreta-sistemas-distribuidos-2026")
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRATION_MINUTES = int(os.getenv("JWT_EXPIRATION_MINUTES", "120"))

    # Servidores centrais e servidor de backup
    CENTRAL_SERVERS = [
        s.strip()
        for s in os.getenv("CENTRAL_SERVERS", "central-1:50051,central-2:50052").split(",")
        if s.strip()
    ]
    BACKUP_SERVER_ADDRESS = os.getenv("BACKUP_SERVER_ADDRESS", "server-backup:50053")
