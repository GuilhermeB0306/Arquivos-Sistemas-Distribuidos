import os

class Config:
    """Configurações do Servidor de Borda (API Gateway Stateless + Load Balancer + Sharding + Failover)."""
    EDGE_ID = os.getenv("EDGE_ID", "edge-server")
    REST_PORT = int(os.getenv("REST_PORT", "8080"))

    # Configurações de Autenticação Stateless (JWT)
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "chave-secreta-sistemas-distribuidos-2026")
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRATION_MINUTES = int(os.getenv("JWT_EXPIRATION_MINUTES", "120"))

    # Lista de Servidores Centrais para Balanceamento de Carga e Fatiamento
    CENTRAL_SERVERS = [
        s.strip()
        for s in os.getenv("CENTRAL_SERVERS", "central-1:50051,central-2:50052").split(",")
        if s.strip()
    ]

    # Endereço do Container de Redundância (usado em caso de Failover se um Servidor Central cair)
    BACKUP_SERVER_ADDRESS = os.getenv("BACKUP_SERVER_ADDRESS", "server-backup:50053")
