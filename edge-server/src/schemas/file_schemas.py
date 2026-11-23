from typing import List
from pydantic import BaseModel, Field

class UploadTextRequest(BaseModel):
    filename: str = Field(..., example="relatorio_sd.txt", description="Nome do arquivo a ser salvo")
    content: str = Field(..., example="Conteúdo do arquivo de teste de Sistemas Distribuídos", description="Conteúdo em texto do arquivo")
    client_id: str = Field(default="cliente-swagger", example="cliente-1", description="Identificador do cliente que enviou")

class UploadResponseSchema(BaseModel):
    success: bool = Field(..., example=True)
    message: str = Field(..., example="Arquivo 'relatorio_sd.txt' salvo na Região Crítica com uso do Token!")
    handled_by_central: str = Field(..., example="central-1", description="Qual Servidor Central gravou o arquivo")
    routed_to: str = Field(..., example="central-1:50051", description="Endereço gRPC escolhido pelo Load Balancer")

class FileMetadataSchema(BaseModel):
    filename: str = Field(..., example="relatorio_sd.txt")
    size: int = Field(..., example=54)
    uploaded_by: str = Field(..., example="cliente-1")
    handled_by_server: str = Field(..., example="central-1")
    timestamp: str = Field(..., example="2026-11-22T18:30:00")

class FileListResponseSchema(BaseModel):
    handled_by_central: str = Field(..., example="central-2", description="Qual Servidor Central atendeu a listagem")
    total_files: int = Field(..., example=1)
    files: List[FileMetadataSchema]
