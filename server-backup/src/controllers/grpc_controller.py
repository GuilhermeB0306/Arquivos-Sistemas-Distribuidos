import storage_pb2
import storage_pb2_grpc
from src.config.settings import Config
from src.domain.models import BackupFileRecord
from src.services.backup_service import BackupReplicationService

class BackupGrpcController(storage_pb2_grpc.FileServiceServicer):
    # Controller gRPC do servidor de backup
    def __init__(self, backup_service: BackupReplicationService):
        self.backup_service = backup_service
        self.server_id = Config.SERVER_ID

    def _to_proto_metadata(self, record: BackupFileRecord) -> storage_pb2.FileMetadata:
        chunks_proto = [
            storage_pb2.ChunkLocation(
                part_number=c.part_number,
                chunk_filename=c.chunk_filename,
                server_id=c.server_id,
                server_grpc_address=c.server_grpc_address,
                chunk_size=c.chunk_size,
                saved_path=c.saved_path,
                backup_server_address=c.backup_server_address,
                backup_saved_path=c.backup_saved_path,
                chunk_sha256=c.chunk_sha256
            )
            for c in record.chunks
        ]
        return storage_pb2.FileMetadata(
            filename=record.filename,
            original_size=record.original_size,
            total_parts=record.total_parts,
            uploaded_by=record.uploaded_by,
            timestamp=record.timestamp,
            combined_file_sha256=record.combined_file_sha256,
            chunks=chunks_proto
        )

    def ReplicateChunk(self, request, context):
        backup_path = self.backup_service.replicate_chunk(
            original_filename=request.original_filename,
            part_number=request.part_number,
            total_parts=request.total_parts,
            chunk_filename=request.chunk_filename,
            content=request.content,
            primary_server_id=request.primary_server_id
        )
        return storage_pb2.ChunkReplicationResponse(
            success=True,
            backup_server_id=self.server_id,
            backup_saved_path=backup_path,
            message=f"Copia salva em {self.server_id}"
        )

    def GetChunk(self, request, context):
        content = self.backup_service.get_chunk_failover(request.chunk_filename)
        if content is None:
            return storage_pb2.ChunkDownloadResponse(
                found=False,
                chunk_filename=request.chunk_filename,
                content=b"",
                handled_by=self.server_id,
                message=f"Fatia '{request.chunk_filename}' nao encontrada no backup."
            )
        return storage_pb2.ChunkDownloadResponse(
            found=True,
            chunk_filename=request.chunk_filename,
            content=content,
            handled_by=f"{self.server_id} (FAILOVER)",
            message="Fatia recuperada do servidor de backup."
        )

    def GetFileMap(self, request, context):
        record = self.backup_service.get_file_map_failover(request.original_filename)
        if record is None:
            return storage_pb2.FileMapResponse(found=False, handled_by=self.server_id)
        return storage_pb2.FileMapResponse(
            found=True,
            file=self._to_proto_metadata(record),
            handled_by=self.server_id
        )

    def ListFiles(self, request, context):
        records = self.backup_service.list_files_failover()
        files_proto = [self._to_proto_metadata(r) for r in records]
        return storage_pb2.FileListResponse(
            files=files_proto,
            handled_by=self.server_id
        )
