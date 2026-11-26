import logging
import uvicorn
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from src.config.settings import Config
from src.infrastructure.grpc_client import CentralGrpcClient
from src.services.load_balancer_service import RoundRobinLoadBalancer
from src.services.edge_gateway_service import EdgeGatewayService
from src.controllers.rest_controller import FileRestController
from src.routes.auth_routes import create_auth_routes
from src.routes.file_routes import create_file_routes
from src.routes.health_routes import create_health_routes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("EdgeMain")

def create_app() -> FastAPI:
    app = FastAPI(
        title="Servidor de Borda - Gateway REST/gRPC",
        description="Gateway com autenticacao JWT, fatiamento de arquivos e balanceamento Round-Robin.",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )

    grpc_client = CentralGrpcClient()
    load_balancer = RoundRobinLoadBalancer(servers=Config.CENTRAL_SERVERS)
    gateway_service = EdgeGatewayService(load_balancer=load_balancer, grpc_client=grpc_client)
    file_controller = FileRestController(gateway_service=gateway_service)

    app.include_router(create_auth_routes())
    app.include_router(create_file_routes(controller=file_controller))
    app.include_router(create_health_routes())

    @app.get("/", include_in_schema=False)
    def root_redirect():
        return RedirectResponse(url="/docs")

    return app

app = create_app()

if __name__ == "__main__":
    logger.info("----------------------------------------------------------")
    logger.info(f"Servidor de Borda [{Config.EDGE_ID}] iniciado na porta {Config.REST_PORT}")
    logger.info(f"Swagger UI: http://localhost:{Config.REST_PORT}/docs")
    logger.info(f"Servidores centrais: {Config.CENTRAL_SERVERS}")
    logger.info("----------------------------------------------------------")
    uvicorn.run(app, host="0.0.0.0", port=Config.REST_PORT)
