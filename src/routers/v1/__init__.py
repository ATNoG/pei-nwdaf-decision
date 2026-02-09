from .config_router import router as config_router
from fastapi import APIRouter

router = APIRouter()
router.include_router(config_router, prefix="/config")
