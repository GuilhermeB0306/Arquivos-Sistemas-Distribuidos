from fastapi import APIRouter
from src.config.settings import Config

def create_health_routes() -> APIRouter:
    router = APIRouter(tags=["Status & Saúde do Gateway"])

    @router.get("/health", summary="Healthcheck do Servidor de Borda")
    def health():
        return {
            "status": "UP",
            "service": Config.EDGE_ID,
            "load_balancer_algorithm": "Round-Robin",
            "central_servers_grpc": Config.CENTRAL_SERVERS
        }

    return router
