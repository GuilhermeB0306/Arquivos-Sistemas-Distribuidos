from fastapi import APIRouter, HTTPException
from src.schemas.file_schemas import LoginRequestSchema, TokenResponseSchema
from src.services.auth_service import JwtAuthService

def create_auth_routes() -> APIRouter:
    router = APIRouter(prefix="/api/auth", tags=["1. Autenticação Stateless (JWT)"])

    @router.post(
        "/login",
        response_model=TokenResponseSchema,
        summary="Gerar Token JWT Stateless",
        description=(
            "Autentica o usuário e devolve um **Token JWT (JSON Web Token)** assinado. "
            "Copie o `access_token` gerado, clique no botão **Authorize (Cadeado)** no topo do Swagger "
            "e cole o token para liberar as rotas de Upload e Download!"
        )
    )
    def login(payload: LoginRequestSchema):
        if not payload.username or not payload.password:
            raise HTTPException(status_code=400, detail="Informe username e password.")
        return JwtAuthService.create_access_token(username=payload.username)

    return router
