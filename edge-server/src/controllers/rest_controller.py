import io
import grpc
from fastapi import UploadFile, HTTPException
from fastapi.responses import StreamingResponse
from src.schemas.file_schemas import UploadTextRequest, UploadResponseSchema, FileListResponseSchema
from src.services.edge_gateway_service import EdgeGatewayService

class FileRestController:
    """
    Camada Controller:
    Trata a entrada HTTP (validação, conversão de arquivos/bytes e tratamento de erros gRPC)
    e chama o EdgeGatewayService.
    """
    def __init__(self, gateway_service: EdgeGatewayService):
        self.gateway_service = gateway_service

    async def upload_multipart_file(self, file: UploadFile, client_id: str) -> UploadResponseSchema:
        if not file.filename:
            raise HTTPException(status_code=400, detail="O nome do arquivo é obrigatório.")
        try:
            content = await file.read()
            result = self.gateway_service.handle_upload(
                filename=file.filename,
                content=content,
                client_id=client_id
            )
            return UploadResponseSchema(**result)
        except grpc.RpcError as e:
            raise HTTPException(status_code=502, detail=f"Erro na comunicação gRPC com Servidor Central: {e.details()}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    def upload_json_text(self, payload: UploadTextRequest) -> UploadResponseSchema:
        try:
            content_bytes = payload.content.encode("utf-8")
            result = self.gateway_service.handle_upload(
                filename=payload.filename,
                content=content_bytes,
                client_id=payload.client_id
            )
            return UploadResponseSchema(**result)
        except grpc.RpcError as e:
            raise HTTPException(status_code=502, detail=f"Erro na comunicação gRPC com Servidor Central: {e.details()}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    def list_files(self) -> FileListResponseSchema:
        try:
            result = self.gateway_service.handle_list_files()
            return FileListResponseSchema(**result)
        except grpc.RpcError as e:
            raise HTTPException(status_code=502, detail=f"Erro na comunicação gRPC com Servidor Central: {e.details()}")
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
                "X-Handled-By-Central": result["handled_by_central"]
            }
            return StreamingResponse(
                io.BytesIO(result["content"]),
                media_type="application/octet-stream",
                headers=headers
            )
        except HTTPException:
            raise
        except grpc.RpcError as e:
            raise HTTPException(status_code=502, detail=f"Erro na comunicação gRPC com Servidor Central: {e.details()}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
