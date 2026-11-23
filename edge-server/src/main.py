import logging
import uvicorn
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from src.config.settings import Config
from src.infrastructure.grpc_client import CentralGrpcClient
from src.services.load_balancer_service import RoundRobinLoadBalancer
from src.services.edge_gateway_service import EdgeGatewayService
from src.controllers.rest_controller import FileRestController
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
        title="Servidor de Borda - API Gateway & Load Balancer",
        description=(
            "**Trabalho de Sistemas Distribuídos**\n\n"
            "Este Servidor de Borda recebe requisições **HTTP REST** dos clientes, "
            "aplica **Balanceamento de Carga (Round-Robin)** e traduz as chamadas para **gRPC (Protobuf)** "
            "rumo aos Servidores Centrais (`central-1` e `central-2`), que coordenam a escrita na "
            "Região Crítica utilizando o algoritmo **Token Ring**."
        ),
        version="1.0.0",
        docs_url="/docs",       # Swagger UI
        redoc_url="/redoc"      # ReDoc
    )

    # 1. Camada de Infraestrutura (Cliente gRPC)
    grpc_client = CentralGrpcClient()

    # 2. Camada de Serviços (Load Balancer Round-Robin + Gateway)
    load_balancer = RoundRobinLoadBalancer(servers=Config.CENTRAL_SERVERS)
    gateway_service = EdgeGatewayService(load_balancer=load_balancer, grpc_client=grpc_client)

    # 3. Camada Controller
    file_controller = FileRestController(gateway_service=gateway_service)

    # 4. Camada de Rotas (Routes)
    app.include_router(create_health_routes())
    app.include_router(create_file_routes(controller=file_controller))

    @app.get("/", include_in_schema=False)
    def root_redirect():
        """Redireciona a raiz / diretamente para o Swagger UI (/docs)"""
        return RedirectResponse(url="/docs")

    return app

app = create_app()

if __name__ == "__main__":
    logger.info("==========================================================")
    logger.info(f"🌐 Servidor de Borda [{Config.EDGE_ID}] iniciado na porta REST {Config.REST_PORT}")
    logger.info(f"📑 Swagger UI disponível em: http://localhost:{Config.REST_PORT}/docs")
    logger.info(f"⚖️ Balanceando carga (Round-Robin) para: {Config.CENTRAL_SERVERS}")
    logger.info("==========================================================")
    uvicorn.run(app, host="0.0.0.0", port=Config.REST_PORT)
