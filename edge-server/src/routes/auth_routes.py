from fastapi import APIRouter, HTTPException
from src.schemas.file_schemas import LoginRequestSchema, TokenResponseSchema
from src.services.auth_service import JwtAuthService

def create_auth_routes() -> APIRouter:
    router = APIRouter(prefix="/api/auth", tags=["1. Autenticacao (JWT)"])

    @router.post(
        "/login",
        response_model=TokenResponseSchema,
        summary="Gerar Token JWT",
        description="Gera um token JWT para autenticar nas rotas de upload e download."
    )
    def login(payload: LoginRequestSchema):
        if not payload.username or not payload.password:
            raise HTTPException(status_code=400, detail="Informe username e password.")
        return JwtAuthService.create_access_token(username=payload.username)

    return router
