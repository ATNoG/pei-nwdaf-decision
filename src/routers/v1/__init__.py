from .config_router import router as config_router
from .decisions_router import router as decisions_router
from fastapi import APIRouter

router = APIRouter()
router.include_router(config_router, prefix="/config")
router.include_router(decisions_router)
