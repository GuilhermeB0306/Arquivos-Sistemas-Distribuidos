from fastapi import APIRouter, UploadFile, File, Depends
from src.schemas.file_schemas import UploadTextRequest, UploadResponseSchema, FileListResponseSchema
from src.controllers.rest_controller import FileRestController
from src.services.auth_service import JwtAuthService

def create_file_routes(controller: FileRestController) -> APIRouter:
    """
    Camada Routes (Roteamento FastAPI protegido por JWT Stateless):
    Todas as rotas exigem um Token JWT válido no header Authorization: Bearer <token>.
    """
    router = APIRouter(prefix="/api", tags=["2. Arquivos Distribuídos (Sharding + Load Balancer + gRPC)"])

    @router.post(
        "/upload",
        response_model=UploadResponseSchema,
        status_code=201,
        summary="Upload de Arquivo Real (Divide ao meio entre Central-1 e Central-2)",
        description=(
            "**Requer Token JWT Stateless.**\n\n"
            "Recebe o arquivo, **divide seus bytes exatamente ao meio (`part1` e `part2`)**, "
            "usa o **Load Balancer (Round-Robin)** para distribuir uma metade para cada Servidor Central via **gRPC**, "
            "e cada Servidor Central aguarda o **Token Ring** para salvar sua parte e registrar no **Banco de Metadados SQLite**!"
        )
    )
    async def upload_file(
        file: UploadFile = File(..., description="Selecione qualquer arquivo para ser fatiado ao meio"),
        jwt_payload: dict = Depends(JwtAuthService.verify_token)
    ):
        current_user = jwt_payload.get("sub", "usuario-jwt")
        return await controller.upload_multipart_file(file=file, current_user=current_user)

    @router.post(
        "/upload/json",
        response_model=UploadResponseSchema,
        status_code=201,
        summary="Upload Rápido via JSON (Divide o texto ao meio entre Central-1 e Central-2)",
        description=(
            "**Requer Token JWT Stateless.**\n\n"
            "Divide o texto enviado ao meio: a 1ª metade vai para um Servidor Central e a 2ª metade para o outro."
        )
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
        summary="Listar Banco de Metadados (Mapa de Chunks)",
        description=(
            "**Requer Token JWT Stateless.**\n\n"
            "Consulta o Banco de Metadados mostrando todos os arquivos e em qual Servidor Central "
            "está salva a **Parte 1** e a **Parte 2** de cada arquivo."
        )
    )
    def list_files(jwt_payload: dict = Depends(JwtAuthService.verify_token)):
        return controller.list_files()

    @router.get(
        "/download/{filename}",
        summary="Download de Arquivo (Busca as 2 metades via gRPC e remonta o original)",
        description=(
            "**Requer Token JWT Stateless.**\n\n"
            "Consulta o Banco de Metadados para saber onde estão as partes do arquivo, "
            "busca a **Parte 1** e a **Parte 2** nos respectivos Servidores Centrais via gRPC, "
            "**remonta o arquivo completo** e faz o download!"
        )
    )
    def download_file(
        filename: str,
        jwt_payload: dict = Depends(JwtAuthService.verify_token)
    ):
        return controller.download_file(filename=filename)

    return router
