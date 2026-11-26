import logging
from concurrent import futures
import grpc

import storage_pb2_grpc
from src.config.settings import Config
from src.infrastructure.backup_repository import BackupRepository
from src.services.backup_service import BackupReplicationService
from src.controllers.grpc_controller import BackupGrpcController

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("BackupMain")

def serve():
    repository = BackupRepository()
    backup_service = BackupReplicationService(repository=repository)

    MAX_MESSAGE_LENGTH = 200 * 1024 * 1024
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=10),
        options=[
            ("grpc.max_send_message_length", MAX_MESSAGE_LENGTH),
            ("grpc.max_receive_message_length", MAX_MESSAGE_LENGTH),
        ],
    )
    storage_pb2_grpc.add_FileServiceServicer_to_server(
        BackupGrpcController(backup_service), server
    )

    address = f"[::]:{Config.GRPC_PORT}"
    server.add_insecure_port(address)
    server.start()

    logger.info("----------------------------------------------------------")
    logger.info(f"Servidor de Backup [{Config.SERVER_ID}] iniciado na porta {Config.GRPC_PORT}")
    logger.info(f"Pasta de backup: {Config.BACKUP_STORAGE_DIR}")
    logger.info("----------------------------------------------------------")

    server.wait_for_termination()

if __name__ == "__main__":
    serve()
