# -*- coding: utf-8 -*-
"""
API Authentication Middleware - Middleware FastAPI para autenticacao
Integra sistema de API keys com FastAPI
"""

from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import logging

from services.api_auth import get_api_key_manager, AccessLevel, APIKey

logger = logging.getLogger(__name__)

# Security scheme para Swagger UI
security = HTTPBearer(auto_error=False)


class AuthenticationMiddleware:
    """Middleware para autenticacao de requests"""

    def __init__(self, enabled: bool = False, require_auth_by_default: bool = False):
        """
        Args:
            enabled: Se True, autenticacao esta ativa
            require_auth_by_default: Se True, todos os endpoints requerem auth por padrao
        """
        self.enabled = enabled
        self.require_auth_by_default = require_auth_by_default
        self.api_key_manager = get_api_key_manager() if enabled else None

        # Endpoints publicos (sem autenticacao)
        self.public_endpoints = {
            "/health",
            "/version",
            "/docs",
            "/openapi.json",
            "/redoc"
        }

    def is_public_endpoint(self, path: str) -> bool:
        """Verifica se endpoint e publico"""
        return path in self.public_endpoints or path.startswith("/static")

    def extract_api_key(self, request: Request) -> Optional[str]:
        """
        Extrai API key do request

        Suporta:
        - Header: Authorization: Bearer nsp_xxxx
        - Header: X-API-Key: nsp_xxxx
        - Query param: ?api_key=nsp_xxxx
        """
        # 1. Authorization header (Bearer)
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:]  # Remove "Bearer "

        # 2. X-API-Key header
        api_key_header = request.headers.get("X-API-Key")
        if api_key_header:
            return api_key_header

        # 3. Query parameter
        api_key_query = request.query_params.get("api_key")
        if api_key_query:
            return api_key_query

        return None


# Instancia global
_auth_middleware: Optional[AuthenticationMiddleware] = None


def get_auth_middleware(enabled: bool = None) -> AuthenticationMiddleware:
    """Obtem instancia global do middleware"""
    global _auth_middleware

    if _auth_middleware is None:
        # Ler config para ver se auth esta ativa
        try:
            from config_loader import config
            auth_enabled = config.get('security.api_auth_enabled', False) if enabled is None else enabled
        except:
            auth_enabled = enabled if enabled is not None else False

        _auth_middleware = AuthenticationMiddleware(enabled=auth_enabled)
        if auth_enabled:
            logger.info("✅ Autenticacao API ativada")
        else:
            logger.info("⚠️  Autenticacao API desativada (modo desenvolvimento)")

    return _auth_middleware


async def get_current_api_key(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[APIKey]:
    """
    Dependency para obter API key atual

    Uso:
        @app.get("/protected")
        async def protected(api_key: APIKey = Depends(get_current_api_key)):
            return {"user": api_key.name}
    """
    middleware = get_auth_middleware()

    # Se autenticacao desativada, retornar None (acesso permitido)
    if not middleware.enabled:
        return None

    # Endpoint publico? Permitir sem auth
    if middleware.is_public_endpoint(request.url.path):
        return None

    # Extrair API key
    key_str = None

    if credentials:
        key_str = credentials.credentials
    else:
        key_str = middleware.extract_api_key(request)

    if not key_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key necessaria. Forneca via header Authorization: Bearer <key> ou X-API-Key: <key>",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Validar key
    api_key = middleware.api_key_manager.validate_key(key_str)

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key invalida ou expirada",
            headers={"WWW-Authenticate": "Bearer"}
        )

    logger.debug(f"Request autenticado: {api_key.name} ({api_key.access_level.value})")

    return api_key


async def require_access_level(
    required_level: AccessLevel,
    api_key: Optional[APIKey] = Depends(get_current_api_key)
) -> APIKey:
    """
    Dependency para requerer nivel de acesso minimo

    Uso:
        @app.post("/admin/train")
        async def train(api_key: APIKey = Depends(lambda: require_access_level(AccessLevel.ADMIN))):
            return {"message": "Training started"}
    """
    middleware = get_auth_middleware()

    # Se auth desativada, permitir
    if not middleware.enabled:
        return api_key

    # Se nao tem key, negar (nao deveria chegar aqui se get_current_api_key funcionou)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticacao necessaria"
        )

    # Verificar nivel de acesso
    manager = middleware.api_key_manager
    if not manager.has_permission(api_key.key, required_level):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Nivel de acesso insuficiente. Requerido: {required_level.value}, atual: {api_key.access_level.value}"
        )

    return api_key


# Funcoes helper para criar dependencies facilmente
def require_standard_access():
    """Dependency para endpoints standard"""
    async def _check(api_key: Optional[APIKey] = Depends(get_current_api_key)):
        return await require_access_level(AccessLevel.STANDARD, api_key)
    return Depends(_check)


def require_admin_access():
    """Dependency para endpoints admin"""
    async def _check(api_key: Optional[APIKey] = Depends(get_current_api_key)):
        return await require_access_level(AccessLevel.ADMIN, api_key)
    return Depends(_check)


def require_full_access():
    """Dependency para endpoints full"""
    async def _check(api_key: Optional[APIKey] = Depends(get_current_api_key)):
        return await require_access_level(AccessLevel.FULL, api_key)
    return Depends(_check)


# Funcao opcional para adicionar middleware de request
async def auth_middleware_func(request: Request, call_next):
    """
    Middleware function para adicionar ao FastAPI

    Uso:
        app.middleware("http")(auth_middleware_func)
    """
    middleware = get_auth_middleware()

    # Se desativado ou endpoint publico, passar
    if not middleware.enabled or middleware.is_public_endpoint(request.url.path):
        return await call_next(request)

    # Extrair e validar key
    key_str = middleware.extract_api_key(request)

    if not key_str:
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key necessaria"
        )

    api_key = middleware.api_key_manager.validate_key(key_str)

    if not api_key:
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key invalida"
        )

    # Adicionar info da key ao request state
    request.state.api_key = api_key

    return await call_next(request)
