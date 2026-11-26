import logging
import grpc
import storage_pb2
import storage_pb2_grpc
from src.config.settings import Config

logger = logging.getLogger("BackupClient")

class BackupGrpcClient:
    """
    Camada de Infraestrutura do Servidor Central:
    Envia uma cópia redundante da fatia (chunk) via gRPC para o container 'server-backup'
    enquanto o Servidor Central está dentro da Região Crítica (com o Token).
    """
    def __init__(self):
        self.backup_address = Config.BACKUP_SERVER_ADDRESS
        self.server_id = Config.SERVER_ID
        self.grpc_options = [
            ("grpc.max_send_message_length", 200 * 1024 * 1024),
            ("grpc.max_receive_message_length", 200 * 1024 * 1024),
        ]

    def replicate_chunk(
        self,
        original_filename: str,
        part_number: int,
        total_parts: int,
        chunk_filename: str,
        content: bytes
    ) -> dict:
        try:
            with grpc.insecure_channel(self.backup_address, options=self.grpc_options) as channel:
                stub = storage_pb2_grpc.FileServiceStub(channel)
                response = stub.ReplicateChunk(
                    storage_pb2.ChunkReplicationRequest(
                        original_filename=original_filename,
                        part_number=part_number,
                        total_parts=total_parts,
                        chunk_filename=chunk_filename,
                        content=content,
                        primary_server_id=self.server_id
                    ),
                    timeout=15.0
                )
                logger.info(
                    f"🛡️ [{self.server_id} -> {self.backup_address}] Cópia de redundância da Parte {part_number} "
                    f"('{chunk_filename}') replicada em '{response.backup_saved_path}'!"
                )
                return {
                    "replicated": response.success,
                    "backup_server_address": self.backup_address,
                    "backup_saved_path": response.backup_saved_path
                }
        except grpc.RpcError as e:
            logger.warning(
                f"⚠️ [{self.server_id}] Não foi possível replicar '{chunk_filename}' para {self.backup_address}: {e.details()}"
            )
            return {
                "replicated": False,
                "backup_server_address": self.backup_address,
                "backup_saved_path": "indisponivel"
            }
