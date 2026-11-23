import os

class Config:
    """Configurações do Servidor de Borda (API Gateway + Load Balancer)."""
    EDGE_ID = os.getenv("EDGE_ID", "edge-server")
    REST_PORT = int(os.getenv("REST_PORT", "8080"))
    
    # Lista de Servidores Centrais para Balanceamento de Carga (separados por vírgula)
    CENTRAL_SERVERS = [
        s.strip()
        for s in os.getenv("CENTRAL_SERVERS", "central-1:50051,central-2:50052").split(",")
        if s.strip()
    ]
