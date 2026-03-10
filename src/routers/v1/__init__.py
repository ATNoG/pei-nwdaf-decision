from fastapi import APIRouter

from .config_router import router as config_router
from .risk_router import router as risk_router

router = APIRouter()
router.include_router(config_router, prefix="/config")
router.include_router(risk_router, prefix="/config")
