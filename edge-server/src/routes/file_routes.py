from fastapi import APIRouter, UploadFile, File, Depends
from src.schemas.file_schemas import UploadTextRequest, UploadResponseSchema, FileListResponseSchema
from src.controllers.rest_controller import FileRestController
from src.services.auth_service import JwtAuthService

def create_file_routes(controller: FileRestController) -> APIRouter:
    # Rotas de upload, listagem e download protegidas por JWT
    router = APIRouter(prefix="/api", tags=["2. Arquivos Distribuidos"])

    @router.post(
        "/upload",
        response_model=UploadResponseSchema,
        status_code=201,
        summary="Upload de arquivo",
        description="Divide o arquivo ao meio, valida duplicidade via SHA-256 e salva nos servidores centrais."
    )
    async def upload_file(
        file: UploadFile = File(..., description="Selecione o arquivo"),
        jwt_payload: dict = Depends(JwtAuthService.verify_token)
    ):
        current_user = jwt_payload.get("sub", "usuario-jwt")
        return await controller.upload_multipart_file(file=file, current_user=current_user)

    @router.post(
        "/upload/json",
        response_model=UploadResponseSchema,
        status_code=201,
        summary="Upload via JSON",
        description="Divide o texto enviado ao meio entre os dois servidores centrais."
    )
    def upload_json(
        payload: UploadTextRequest,
        jwt_payload: dict = Depends(JwtAuthService.verify_token)
    ):
        current_user = jwt_payload.get("sub", "usuario-jwt")
        return controller.upload_json_text(payload=payload, current_user=current_user)

    @router.get(
        "/files",
        response_model=FileListResponseSchema,
        summary="Listar arquivos",
        description="Lista os arquivos cadastrados e onde esta cada parte."
    )
    def list_files(jwt_payload: dict = Depends(JwtAuthService.verify_token)):
        return controller.list_files()

    @router.get(
        "/download/{filename}",
        summary="Download de arquivo",
        description="Busca as duas partes via gRPC e remonta o arquivo original."
    )
    def download_file(
        filename: str,
        jwt_payload: dict = Depends(JwtAuthService.verify_token)
    ):
        return controller.download_file(filename=filename)

    return router
