import storage_pb2
import storage_pb2_grpc
from src.config.settings import Config
from src.domain.models import FileRecord
from src.services.file_service import FileManagementService
from src.services.token_ring_service import TokenRingService

class FileGrpcController(storage_pb2_grpc.FileServiceServicer):
    """
    Camada Controller (Entrada gRPC nos Servidores Centrais):
    Atende pedidos de gravação/leitura de fatias (Chunks) e consultas ao Banco de Metadados.
    """
    def __init__(self, file_service: FileManagementService):
        self.file_service = file_service
        self.server_id = Config.SERVER_ID

    def _to_proto_metadata(self, record: FileRecord) -> storage_pb2.FileMetadata:
        chunks_proto = [
            storage_pb2.ChunkLocation(
                part_number=c.part_number,
                chunk_filename=c.chunk_filename,
                server_id=c.server_id,
                server_grpc_address=c.server_grpc_address,
                chunk_size=c.chunk_size,
                saved_path=c.saved_path,
                backup_server_address=c.backup_server_address,
                backup_saved_path=c.backup_saved_path
            )
            for c in record.chunks
        ]
        return storage_pb2.FileMetadata(
            filename=record.filename,
            original_size=record.original_size,
            total_parts=record.total_parts,
            uploaded_by=record.uploaded_by,
            timestamp=record.timestamp,
            chunks=chunks_proto
        )

    def SaveChunk(self, request, context):
        res = self.file_service.save_chunk(
            original_filename=request.original_filename,
            part_number=request.part_number,
            total_parts=request.total_parts,
            chunk_filename=request.chunk_filename,
            content=request.content,
            original_size=request.original_size,
            client_id=request.client_id or "anonimo"
        )
        return storage_pb2.ChunkUploadResponse(
            success=True,
            message=f"Parte {request.part_number}/{request.total_parts} salva e replicada no Backup com posse do Token!",
            handled_by=self.server_id,
            chunk_path=res["chunk_path"],
            backup_path=res["backup_path"],
            replicated=res["replicated"]
        )

    def GetChunk(self, request, context):
        content = self.file_service.get_chunk(request.chunk_filename)
        if content is None:
            return storage_pb2.ChunkDownloadResponse(
                found=False,
                chunk_filename=request.chunk_filename,
                content=b"",
                handled_by=self.server_id,
                message=f"Fatia '{request.chunk_filename}' não encontrada em {self.server_id}."
            )
        return storage_pb2.ChunkDownloadResponse(
            found=True,
            chunk_filename=request.chunk_filename,
            content=content,
            handled_by=self.server_id,
            message="Fatia lida com sucesso."
        )

    def GetFileMap(self, request, context):
        record = self.file_service.get_file_map(request.original_filename)
        if record is None:
            return storage_pb2.FileMapResponse(
                found=False,
                handled_by=self.server_id
            )
        return storage_pb2.FileMapResponse(
            found=True,
            file=self._to_proto_metadata(record),
            handled_by=self.server_id
        )

    def ListFiles(self, request, context):
        records = self.file_service.list_files()
        files_proto = [self._to_proto_metadata(r) for r in records]
        return storage_pb2.FileListResponse(
            files=files_proto,
            handled_by=self.server_id
        )


class TokenRingGrpcController(storage_pb2_grpc.TokenRingServiceServicer):
    """Recebe o Token enviado pelo servidor central vizinho no anel lógico."""
    def __init__(self, token_ring_service: TokenRingService):
        self.token_ring_service = token_ring_service

    def PassToken(self, request, context):
        self.token_ring_service.receive_token(
            sequence_number=request.sequence_number,
            from_server=request.from_server
        )
        return storage_pb2.TokenAck(received=True)
