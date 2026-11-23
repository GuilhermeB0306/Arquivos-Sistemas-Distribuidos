from fastapi import APIRouter, UploadFile, File, Form
from src.schemas.file_schemas import UploadTextRequest, UploadResponseSchema, FileListResponseSchema
from src.controllers.rest_controller import FileRestController

def create_file_routes(controller: FileRestController) -> APIRouter:
    """
    Camada Routes (Roteamento FastAPI + Documentação Swagger):
    Define todos os endpoints HTTP REST e suas tags no Swagger UI (/docs).
    """
    router = APIRouter(prefix="/api", tags=["Arquivos (Load Balancer REST -> gRPC)"])

    @router.post(
        "/upload",
        response_model=UploadResponseSchema,
        status_code=201,
        summary="Upload de Arquivo Real (Multipart/Form-Data)",
        description=(
            "Recebe um arquivo real (PDF, Imagem, TXT, etc.), seleciona um Servidor Central via "
            "**Round-Robin** e encaminha via **gRPC**. O Servidor Central aguardará o **Token** "
            "(Token Ring) para gravar na Região Crítica."
        )
    )
    async def upload_file(
        file: UploadFile = File(..., description="Selecione o arquivo para enviar"),
        client_id: str = Form(default="cliente-swagger", description="ID do Cliente que está enviando")
    ):
        return await controller.upload_multipart_file(file=file, client_id=client_id)

    @router.post(
        "/upload/json",
        response_model=UploadResponseSchema,
        status_code=201,
        summary="Upload Rápido via JSON (Texto)",
        description=(
            "Endpoint prático para testes rápidos pelo Swagger ou scripts de automação: "
            "cria um arquivo a partir de um JSON com `filename` e `content`."
        )
    )
    def upload_json(payload: UploadTextRequest):
        return controller.upload_json_text(payload=payload)

    @router.get(
        "/files",
        response_model=FileListResponseSchema,
        summary="Listar Catálogo de Arquivos",
        description=(
            "Consulta a lista de arquivos disponíveis através do Load Balancer (Round-Robin). "
            "Operação de leitura: **não exige espera do Token Ring**."
        )
    )
    def list_files():
        return controller.list_files()

    @router.get(
        "/download/{filename}",
        summary="Download de Arquivo",
        description=(
            "Baixa o arquivo solicitado de um dos Servidores Centrais via gRPC (Round-Robin). "
            "Operação de leitura livre de Token. Verifique o header `X-Handled-By-Central` na resposta!"
        )
    )
    def download_file(filename: str):
        return controller.download_file(filename=filename)

    return router
