import io
import grpc
from fastapi import UploadFile, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from src.schemas.file_schemas import UploadTextRequest, UploadResponseSchema, FileListResponseSchema
from src.services.edge_gateway_service import EdgeGatewayService

class FileRestController:
    # Controller REST para upload, listagem e download de arquivos
    def __init__(self, gateway_service: EdgeGatewayService):
        self.gateway_service = gateway_service

    async def upload_multipart_file(self, file: UploadFile, current_user: str):
        if not file.filename:
            raise HTTPException(status_code=400, detail="O nome do arquivo e obrigatorio.")
        try:
            content = await file.read()
            result = self.gateway_service.handle_upload(
                filename=file.filename,
                content=content,
                client_id=current_user
            )
            schema = UploadResponseSchema(**result)
            if schema.is_duplicate:
                return JSONResponse(status_code=409, content=schema.model_dump())
            return schema
        except grpc.RpcError as e:
            raise HTTPException(status_code=502, detail=f"Erro gRPC: {e.details()}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    def upload_json_text(self, payload: UploadTextRequest, current_user: str):
        try:
            content_bytes = payload.content.encode("utf-8")
            result = self.gateway_service.handle_upload(
                filename=payload.filename,
                content=content_bytes,
                client_id=current_user
            )
            schema = UploadResponseSchema(**result)
            if schema.is_duplicate:
                return JSONResponse(status_code=409, content=schema.model_dump())
            return schema
        except grpc.RpcError as e:
            raise HTTPException(status_code=502, detail=f"Erro gRPC: {e.details()}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    def list_files(self) -> FileListResponseSchema:
        try:
            result = self.gateway_service.handle_list_files()
            return FileListResponseSchema(**result)
        except grpc.RpcError as e:
            raise HTTPException(status_code=502, detail=f"Erro gRPC: {e.details()}")
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
            raise HTTPException(status_code=502, detail=f"Erro gRPC: {e.details()}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
