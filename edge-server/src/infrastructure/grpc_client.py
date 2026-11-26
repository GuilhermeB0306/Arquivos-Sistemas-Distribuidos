import logging
import grpc
import storage_pb2
import storage_pb2_grpc

logger = logging.getLogger("GrpcClient")

class CentralGrpcClient:
    """
    Camada de Infraestrutura do Servidor de Borda:
    Realiza chamadas gRPC aos Servidores Centrais (cálculo distribuído de SHA-256 nos workers,
    gravação/leitura de chunks) e ao Servidor de Redundância (server-backup).
    """
    GRPC_OPTIONS = [
        ("grpc.max_send_message_length", 200 * 1024 * 1024),
        ("grpc.max_receive_message_length", 200 * 1024 * 1024),
    ]

    def compute_chunk_hash(
        self,
        target_server: str,
        part_number: int,
        chunk_filename: str,
        content: bytes
    ) -> dict:
        logger.info(
            f"🔐 [gRPC -> {target_server}] Solicitando a um Worker o cálculo SHA-256 da Parte {part_number} ('{chunk_filename}')"
        )
        with grpc.insecure_channel(target_server, options=self.GRPC_OPTIONS) as channel:
            stub = storage_pb2_grpc.FileServiceStub(channel)
            response = stub.ComputeChunkHash(
                storage_pb2.ChunkHashRequest(
                    part_number=part_number,
                    chunk_filename=chunk_filename,
                    content=content
                ),
                timeout=15.0
            )
            return {
                "part_number": response.part_number,
                "chunk_sha256": response.chunk_sha256,
                "calculated_by_server": response.calculated_by_server,
                "worker_thread": response.worker_thread,
                "target_server": target_server
            }

    def save_chunk(
        self,
        target_server: str,
        original_filename: str,
        part_number: int,
        total_parts: int,
        chunk_filename: str,
        content: bytes,
        original_size: int,
        client_id: str,
        chunk_sha256: str,
        combined_file_sha256: str
    ) -> dict:
        logger.info(
            f"📤 [gRPC -> {target_server}] Enviando Parte {part_number}/{total_parts} "
            f"('{chunk_filename}', {len(content)} bytes) do usuário '{client_id}'"
        )
        with grpc.insecure_channel(target_server, options=self.GRPC_OPTIONS) as channel:
            stub = storage_pb2_grpc.FileServiceStub(channel)
            response = stub.SaveChunk(
                storage_pb2.ChunkUploadRequest(
                    original_filename=original_filename,
                    part_number=part_number,
                    total_parts=total_parts,
                    chunk_filename=chunk_filename,
                    content=content,
                    original_size=original_size,
                    client_id=client_id,
                    chunk_sha256=chunk_sha256,
                    combined_file_sha256=combined_file_sha256
                ),
                timeout=30.0
            )
            return {
                "success": response.success,
                "is_duplicate": response.is_duplicate,
                "duplicate_of_filename": response.duplicate_of_filename,
                "part_number": part_number,
                "chunk_filename": chunk_filename,
                "chunk_size": len(content),
                "chunk_sha256": response.chunk_sha256,
                "combined_file_sha256": response.combined_file_sha256,
                "handled_by_central": response.handled_by,
                "routed_to": target_server,
                "saved_path": response.chunk_path,
                "backup_saved_path": response.backup_path,
                "replicated": response.replicated,
                "message": response.message
            }

    def get_chunk(self, target_server: str, chunk_filename: str) -> dict:
        logger.info(f"📥 [gRPC -> {target_server}] Buscando fatia '{chunk_filename}'")
        with grpc.insecure_channel(target_server, options=self.GRPC_OPTIONS) as channel:
            stub = storage_pb2_grpc.FileServiceStub(channel)
            response = stub.GetChunk(
                storage_pb2.ChunkDownloadRequest(chunk_filename=chunk_filename),
                timeout=8.0
            )
            return {
                "found": response.found,
                "chunk_filename": response.chunk_filename,
                "content": response.content,
                "handled_by_central": response.handled_by,
                "message": response.message
            }

    def get_file_map(self, target_server: str, original_filename: str) -> dict:
        logger.info(f"🗺️ [gRPC -> {target_server}] Consultando Banco de Metadados para '{original_filename}'")
        with grpc.insecure_channel(target_server, options=self.GRPC_OPTIONS) as channel:
            stub = storage_pb2_grpc.FileServiceStub(channel)
            response = stub.GetFileMap(
                storage_pb2.FileMapRequest(original_filename=original_filename),
                timeout=8.0
            )
            if not response.found:
                return {"found": False, "handled_by_central": response.handled_by}

            f = response.file
            return {
                "found": True,
                "handled_by_central": response.handled_by,
                "filename": f.filename,
                "original_size": f.original_size,
                "total_parts": f.total_parts,
                "uploaded_by": f.uploaded_by,
                "timestamp": f.timestamp,
                "combined_file_sha256": f.combined_file_sha256,
                "chunks": [
                    {
                        "part_number": c.part_number,
                        "chunk_filename": c.chunk_filename,
                        "server_id": c.server_id,
                        "server_grpc_address": c.server_grpc_address,
                        "chunk_size": c.chunk_size,
                        "saved_path": c.saved_path,
                        "backup_server_address": c.backup_server_address,
                        "backup_saved_path": c.backup_saved_path,
                        "chunk_sha256": c.chunk_sha256
                    }
                    for c in f.chunks
                ]
            }

    def list_files(self, target_server: str) -> dict:
        logger.info(f"📋 [gRPC -> {target_server}] Consultando catálogo de arquivos e chunks")
        with grpc.insecure_channel(target_server, options=self.GRPC_OPTIONS) as channel:
            stub = storage_pb2_grpc.FileServiceStub(channel)
            response = stub.ListFiles(storage_pb2.Empty(), timeout=8.0)
            files = [
                {
                    "filename": f.filename,
                    "original_size": f.original_size,
                    "total_parts": f.total_parts,
                    "uploaded_by": f.uploaded_by,
                    "timestamp": f.timestamp,
                    "combined_file_sha256": f.combined_file_sha256,
                    "chunks": [
                        {
                            "part_number": c.part_number,
                            "chunk_filename": c.chunk_filename,
                            "server_id": c.server_id,
                            "server_grpc_address": c.server_grpc_address,
                            "chunk_size": c.chunk_size,
                            "saved_path": c.saved_path,
                            "backup_server_address": c.backup_server_address,
                            "backup_saved_path": c.backup_saved_path,
                            "chunk_sha256": c.chunk_sha256
                        }
                        for c in f.chunks
                    ]
                }
                for f in response.files
            ]
            return {
                "handled_by_central": response.handled_by,
                "total_files": len(files),
                "files": files
            }
