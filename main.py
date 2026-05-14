from fastapi import FastAPI
from src.auth_middleware import AuthMiddleware
from src.core.runtime import lifespan
from src.routers.v1 import router as v1_router
from src.core.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    lifespan=lifespan
)

app.add_middleware(AuthMiddleware)
app.include_router(v1_router, prefix="/api/v1")


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}
