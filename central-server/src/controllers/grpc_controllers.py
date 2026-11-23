import storage_pb2
import storage_pb2_grpc
from src.config.settings import Config
from src.services.file_service import FileManagementService
from src.services.token_ring_service import TokenRingService

class FileGrpcController(storage_pb2_grpc.FileServiceServicer):
    """
    Camada Controller (Entrada gRPC):
    Recebe as chamadas RPC vindas do Servidor de Borda e delega para a camada de Serviço.
    """
    def __init__(self, file_service: FileManagementService):
        self.file_service = file_service
        self.server_id = Config.SERVER_ID

    def UploadFile(self, request, context):
        record = self.file_service.upload_file(
            filename=request.filename,
            content=request.content,
            client_id=request.client_id or "anonimo"
        )
        return storage_pb2.UploadResponse(
            success=True,
            message=f"Arquivo '{record.filename}' salvo na Região Crítica com uso do Token!",
            handled_by=self.server_id
        )

    def DownloadFile(self, request, context):
        content = self.file_service.download_file(request.filename)
        if content is None:
            return storage_pb2.DownloadResponse(
                found=False,
                filename=request.filename,
                content=b"",
                handled_by=self.server_id,
                message=f"Arquivo '{request.filename}' não encontrado."
            )
        return storage_pb2.DownloadResponse(
            found=True,
            filename=request.filename,
            content=content,
            handled_by=self.server_id,
            message="Download concluído com sucesso."
        )

    def ListFiles(self, request, context):
        records = self.file_service.list_files()
        files_proto = [
            storage_pb2.FileMetadata(
                filename=r.filename,
                size=r.size,
                uploaded_by=r.uploaded_by,
                handled_by_server=r.handled_by_server,
                timestamp=r.timestamp
            )
            for r in records
        ]
        return storage_pb2.FileListResponse(
            files=files_proto,
            handled_by=self.server_id
        )


class TokenRingGrpcController(storage_pb2_grpc.TokenRingServiceServicer):
    """
    Camada Controller (Entrada gRPC do Anel):
    Recebe o Token enviado pelo servidor central vizinho no anel lógico.
    """
    def __init__(self, token_ring_service: TokenRingService):
        self.token_ring_service = token_ring_service

    def PassToken(self, request, context):
        self.token_ring_service.receive_token(
            sequence_number=request.sequence_number,
            from_server=request.from_server
        )
        return storage_pb2.TokenAck(received=True)
