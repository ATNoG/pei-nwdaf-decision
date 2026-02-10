from .config_router import router as config_router
from .risk_router import router as risk_router
from fastapi import APIRouter

router = APIRouter()
router.include_router(config_router, prefix="/config")
router.include_router(risk_router, prefix="/config")
