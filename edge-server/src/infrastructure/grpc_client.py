import logging
import grpc
import storage_pb2
import storage_pb2_grpc

logger = logging.getLogger("GrpcClient")

class CentralGrpcClient:
    """
    Camada de Infraestrutura:
    Comunica-se via gRPC (HTTP/2 + Protobuf) com um Servidor Central específico
    escolhido pelo Balanceador de Carga.
    """
    def upload_file(self, target_server: str, filename: str, content: bytes, client_id: str) -> dict:
        logger.info(f"📤 [gRPC -> {target_server}] Encaminhando Upload de '{filename}' ({len(content)} bytes) do cliente '{client_id}'")
        with grpc.insecure_channel(target_server) as channel:
            stub = storage_pb2_grpc.FileServiceStub(channel)
            response = stub.UploadFile(
                storage_pb2.UploadRequest(
                    filename=filename,
                    content=content,
                    client_id=client_id
                ),
                timeout=30.0
            )
            return {
                "success": response.success,
                "message": response.message,
                "handled_by_central": response.handled_by,
                "routed_to": target_server
            }

    def download_file(self, target_server: str, filename: str) -> dict:
        logger.info(f"📥 [gRPC -> {target_server}] Encaminhando Download de '{filename}'")
        with grpc.insecure_channel(target_server) as channel:
            stub = storage_pb2_grpc.FileServiceStub(channel)
            response = stub.DownloadFile(
                storage_pb2.DownloadRequest(filename=filename),
                timeout=15.0
            )
            return {
                "found": response.found,
                "filename": response.filename,
                "content": response.content,
                "handled_by_central": response.handled_by,
                "message": response.message
            }

    def list_files(self, target_server: str) -> dict:
        logger.info(f"📋 [gRPC -> {target_server}] Consultando lista de arquivos")
        with grpc.insecure_channel(target_server) as channel:
            stub = storage_pb2_grpc.FileServiceStub(channel)
            response = stub.ListFiles(storage_pb2.Empty(), timeout=10.0)
            files = [
                {
                    "filename": f.filename,
                    "size": f.size,
                    "uploaded_by": f.uploaded_by,
                    "handled_by_server": f.handled_by_server,
                    "timestamp": f.timestamp
                }
                for f in response.files
            ]
            return {
                "handled_by_central": response.handled_by,
                "total_files": len(files),
                "files": files
            }
