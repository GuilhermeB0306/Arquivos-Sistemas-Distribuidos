from typing import List
from pydantic import BaseModel, Field

class LoginRequestSchema(BaseModel):
    username: str = Field(default="guilherme", example="guilherme", description="Nome do usuário")
    password: str = Field(default="123456", example="123456", description="Senha para gerar o Token JWT Stateless")

class TokenResponseSchema(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in_minutes: int
    username: str
    stateless_note: str

class UploadTextRequest(BaseModel):
    filename: str = Field(..., example="relatorio_sd.txt", description="Nome do arquivo a ser fatiado e salvo")
    content: str = Field(
        ...,
        example="PRIMEIRA_METADE_NO_SERVIDOR_1___SEGUNDA_METADE_NO_SERVIDOR_2",
        description="Conteúdo em texto (será dividido ao meio entre central-1 e central-2 e replicado no server-backup)"
    )

class ChunkResultSchema(BaseModel):
    part_number: int = Field(..., example=1)
    chunk_filename: str = Field(..., example="relatorio_sd.txt.part1")
    chunk_size: int = Field(..., example=30)
    handled_by_central: str = Field(..., example="central-1")
    routed_to: str = Field(..., example="central-1:50051")
    saved_path: str = Field(..., example="storage_data/central-1/relatorio_sd.txt.part1")
    backup_saved_path: str = Field(..., example="storage_data/server-backup/relatorio_sd.txt.part1")
    replicated: bool = Field(..., example=True)
    message: str

class UploadResponseSchema(BaseModel):
    success: bool = Field(..., example=True)
    filename: str = Field(..., example="relatorio_sd.txt")
    original_size: int = Field(..., example=60)
    total_parts: int = Field(..., example=2)
    uploaded_by: str = Field(..., example="guilherme")
    message: str
    chunks: List[ChunkResultSchema]

class ChunkLocationSchema(BaseModel):
    part_number: int
    chunk_filename: str
    server_id: str
    server_grpc_address: str
    chunk_size: int
    saved_path: str
    backup_server_address: str
    backup_saved_path: str

class FileMetadataSchema(BaseModel):
    filename: str
    original_size: int
    total_parts: int
    uploaded_by: str
    timestamp: str
    chunks: List[ChunkLocationSchema]

class FileListResponseSchema(BaseModel):
    handled_by_central: str
    total_files: int
    files: List[FileMetadataSchema]
