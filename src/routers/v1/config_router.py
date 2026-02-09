from fastapi import APIRouter, Depends, Request
from src.core.runtime import DecisionRuntime

router = APIRouter(prefix="/api/v1", tags=["Decision", "Configuration"])

def get_runtime(request: Request) -> DecisionRuntime:
    return request.app.state.decision_runtime


@router.get("/decisions")
async def list_decisions(runtime: DecisionRuntime = Depends(get_runtime)):
    """Returns the list of available decisions."""

    return {
        "decisions": runtime.decisions,
        "count": len(runtime.decisions)
    }

@router.get("/blacklist")
async def get_blacklist(runtime: DecisionRuntime = Depends(get_runtime)):
    """Returns the current blacklist."""

    return {"blacklist": runtime.blacklist}

@router.post("/decisions/add/{item}")
async def add_to_decisions(item: str, runtime: DecisionRuntime = Depends(get_runtime)):
    """Adds an item to the runtime blacklist."""

    runtime.decisions.append(item)
    return {
        "message": "Item added to decisions",
        "decisions": runtime.decisions
    }

@router.post("/blacklist/add/{item}")
async def add_to_blacklist(item: str, runtime: DecisionRuntime = Depends(get_runtime)):
    """Adds an item to the runtime blacklist."""

    runtime.blacklist.append(item)
    return {
        "message": "Item added to blacklist",
        "blacklist": runtime.blacklist
    }
