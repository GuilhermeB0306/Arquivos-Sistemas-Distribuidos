from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from src.config.settings import Config

security_scheme = HTTPBearer(
    scheme_name="JWT Stateless Auth",
    description="Cole aqui o Token JWT gerado na rota **/api/auth/login**"
)

class JwtAuthService:
    """
    Camada de Serviço (Autenticação Stateless):
    Gera e valida tokens JWT assinados criptograficamente sem armazenar sessão em memória.
    """
    @staticmethod
    def create_access_token(username: str, role: str = "aluno_sd") -> dict:
        now = datetime.now(timezone.utc)
        expire = now + timedelta(minutes=Config.JWT_EXPIRATION_MINUTES)
        payload = {
            "sub": username,
            "role": role,
            "iss": Config.EDGE_ID,
            "iat": int(now.timestamp()),
            "exp": int(expire.timestamp())
        }
        token = jwt.encode(payload, Config.JWT_SECRET_KEY, algorithm=Config.JWT_ALGORITHM)
        return {
            "access_token": token,
            "token_type": "Bearer",
            "expires_in_minutes": Config.JWT_EXPIRATION_MINUTES,
            "username": username,
            "stateless_note": "O servidor não guarda sessão! Sua identidade viaja assinada dentro deste JWT."
        }

    @staticmethod
    def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security_scheme)) -> dict:
        token = credentials.credentials
        try:
            payload = jwt.decode(
                token,
                Config.JWT_SECRET_KEY,
                algorithms=[Config.JWT_ALGORITHM]
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token JWT expirado. Faça login novamente em /api/auth/login."
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token JWT inválido."
            )
