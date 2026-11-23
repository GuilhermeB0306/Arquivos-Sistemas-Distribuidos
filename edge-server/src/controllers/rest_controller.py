import io
import grpc
from fastapi import UploadFile, HTTPException
from fastapi.responses import StreamingResponse
from src.schemas.file_schemas import UploadTextRequest, UploadResponseSchema, FileListResponseSchema
from src.services.edge_gateway_service import EdgeGatewayService

class FileRestController:
    """
    Camada Controller:
    Recebe as requisições já autenticadas via JWT Stateless, repassa para o EdgeGatewayService
    fatiar/remontar os arquivos via gRPC e retorna os schemas do FastAPI.
    """
    def __init__(self, gateway_service: EdgeGatewayService):
        self.gateway_service = gateway_service

    async def upload_multipart_file(self, file: UploadFile, current_user: str) -> UploadResponseSchema:
        if not file.filename:
            raise HTTPException(status_code=400, detail="O nome do arquivo é obrigatório.")
        try:
            content = await file.read()
            result = self.gateway_service.handle_upload(
                filename=file.filename,
                content=content,
                client_id=current_user
            )
            return UploadResponseSchema(**result)
        except grpc.RpcError as e:
            raise HTTPException(status_code=502, detail=f"Erro gRPC com Servidor Central: {e.details()}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    def upload_json_text(self, payload: UploadTextRequest, current_user: str) -> UploadResponseSchema:
        try:
            content_bytes = payload.content.encode("utf-8")
            result = self.gateway_service.handle_upload(
                filename=payload.filename,
                content=content_bytes,
                client_id=current_user
            )
            return UploadResponseSchema(**result)
        except grpc.RpcError as e:
            raise HTTPException(status_code=502, detail=f"Erro gRPC com Servidor Central: {e.details()}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    def list_files(self) -> FileListResponseSchema:
        try:
            result = self.gateway_service.handle_list_files()
            return FileListResponseSchema(**result)
        except grpc.RpcError as e:
            raise HTTPException(status_code=502, detail=f"Erro gRPC com Servidor Central: {e.details()}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    def download_file(self, filename: str) -> StreamingResponse:
        try:
            result = self.gateway_service.handle_download(filename=filename)
            if not result["found"]:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "message": result["message"],
                        "handled_by_central": result["handled_by_central"]
                    }
                )

            headers = {
                "Content-Disposition": f'attachment; filename="{result["filename"]}"',
                "X-Reassembled-From": result["handled_by_central"]
            }
            return StreamingResponse(
                io.BytesIO(result["content"]),
                media_type="application/octet-stream",
                headers=headers
            )
        except HTTPException:
            raise
        except grpc.RpcError as e:
            raise HTTPException(status_code=502, detail=f"Erro gRPC com Servidor Central: {e.details()}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
