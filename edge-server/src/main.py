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
        title="Servidor de Borda - API Gateway Stateless (JWT) & File Sharding",
        description=(
            "**Trabalho de Sistemas Distribuídos**\n\n"
            "1. **Autenticação Stateless (JWT):** Gere seu token em `POST /api/auth/login` e clique no botão **Authorize**.\n"
            "2. **File Sharding (Fatiamento):** No upload, o Servidor de Borda divide o arquivo ao meio (`part1` e `part2`).\n"
            "3. **Load Balancing (Round-Robin) + gRPC:** Envia uma metade para `central-1` e a outra para `central-2` em paralelo.\n"
            "4. **Token Ring + Banco de Metadados (SQLite):** Os Servidores Centrais usam o Token para gravar sua metade e atualizar o banco de ponteiros sem condição de corrida."
        ),
        version="2.0.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )

    # 1. Camada de Infraestrutura (Cliente gRPC)
    grpc_client = CentralGrpcClient()

    # 2. Camada de Serviços (Load Balancer Round-Robin + Gateway de Sharding)
    load_balancer = RoundRobinLoadBalancer(servers=Config.CENTRAL_SERVERS)
    gateway_service = EdgeGatewayService(load_balancer=load_balancer, grpc_client=grpc_client)

    # 3. Camada Controller
    file_controller = FileRestController(gateway_service=gateway_service)

    # 4. Camada de Rotas (Auth JWT, Arquivos e Healthcheck)
    app.include_router(create_auth_routes())
    app.include_router(create_file_routes(controller=file_controller))
    app.include_router(create_health_routes())

    @app.get("/", include_in_schema=False)
    def root_redirect():
        return RedirectResponse(url="/docs")

    return app

app = create_app()

if __name__ == "__main__":
    logger.info("==========================================================")
    logger.info(f"🌐 Servidor de Borda [{Config.EDGE_ID}] iniciado na porta REST {Config.REST_PORT}")
    logger.info(f"🔐 Autenticação Stateless JWT ativada!")
    logger.info(f"📑 Swagger UI disponível em: http://localhost:{Config.REST_PORT}/docs")
    logger.info(f"⚖️ Fatiando arquivos e balanceando carga para: {Config.CENTRAL_SERVERS}")
    logger.info("==========================================================")
    uvicorn.run(app, host="0.0.0.0", port=Config.REST_PORT)
