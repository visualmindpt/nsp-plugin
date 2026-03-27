"""
Compat layer para código antigo que importava `services.api`.
O FastAPI principal vive agora em `services.server`.
"""
from .server import app

__all__ = ["app"]
