import logging
from concurrent import futures
import grpc

import storage_pb2_grpc
from src.config.settings import Config
from src.infrastructure.storage_repository import StorageRepository
from src.infrastructure.backup_grpc_client import BackupGrpcClient
from src.services.token_ring_service import TokenRingService
from src.services.file_service import FileManagementService
from src.controllers.grpc_controllers import FileGrpcController, TokenRingGrpcController

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("Main")

def serve():
    repository = StorageRepository()
    backup_client = BackupGrpcClient()

    token_ring_service = TokenRingService()
    file_service = FileManagementService(
        repository=repository,
        token_ring=token_ring_service,
        backup_client=backup_client
    )

    # Servidor gRPC com 10 threads e limite de 200MB por mensagem
    MAX_MESSAGE_LENGTH = 200 * 1024 * 1024
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=10),
        options=[
            ("grpc.max_send_message_length", MAX_MESSAGE_LENGTH),
            ("grpc.max_receive_message_length", MAX_MESSAGE_LENGTH),
        ],
    )

    storage_pb2_grpc.add_FileServiceServicer_to_server(
        FileGrpcController(file_service), server
    )
    storage_pb2_grpc.add_TokenRingServiceServicer_to_server(
        TokenRingGrpcController(token_ring_service), server
    )

    address = f"[::]:{Config.GRPC_PORT}"
    server.add_insecure_port(address)
    server.start()

    logger.info("----------------------------------------------------------")
    logger.info(f"Servidor Central [{Config.SERVER_ID}] iniciado na porta {Config.GRPC_PORT}")
    logger.info(f"Proximo no do anel: {Config.NEXT_NODE_ADDRESS}")
    logger.info(f"Servidor de backup: {Config.BACKUP_SERVER_ADDRESS}")
    logger.info(f"Pasta local: {Config.NODE_STORAGE_DIR}")
    logger.info("----------------------------------------------------------")

    token_ring_service.start_background_worker()
    server.wait_for_termination()

if __name__ == "__main__":
    serve()
