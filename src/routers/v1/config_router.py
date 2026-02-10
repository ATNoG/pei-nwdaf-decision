from fastapi import APIRouter, Depends, Request, HTTPException
from src.core.runtime import DecisionRuntime
from src.core.config import DecisionEntry, BlacklistEntry

router = APIRouter(prefix="/api/v1", tags=["Decision", "Configuration"])

def get_runtime(request: Request) -> DecisionRuntime:
    return request.app.state.decision_runtime


@router.get("/decisions")
async def list_decisions(runtime: DecisionRuntime = Depends(get_runtime)):
    """Returns the list of available decisions."""
    return {
        "decisions": [d.model_dump() for d in runtime.decisions],
        "count": len(runtime.decisions)
    }


@router.get("/blacklist")
async def get_blacklist(runtime: DecisionRuntime = Depends(get_runtime)):
    """Returns the current blacklist."""
    return {"blacklist": [b.model_dump() for b in runtime.blacklist]}


@router.post("/decisions")
async def add_decision(entry: DecisionEntry, runtime: DecisionRuntime = Depends(get_runtime)):
    """Adds a decision to the runtime."""
    if entry.name in runtime.decision_names():
        raise HTTPException(status_code=400, detail="Decision already exists")

    runtime.decisions.append(entry)
    return {
        "message": "Decision added",
        "decision": entry.model_dump(),
        "decisions": [d.model_dump() for d in runtime.decisions]
    }


@router.post("/blacklist")
async def add_to_blacklist(entry: BlacklistEntry, runtime: DecisionRuntime = Depends(get_runtime)):
    """Adds a decision to the blacklist."""
    if entry.name not in runtime.decision_names():
        raise HTTPException(status_code=400, detail="Decision does not exist")

    if entry.name in runtime.blacklist_names():
        raise HTTPException(status_code=400, detail="Decision already blacklisted")

    runtime.blacklist.append(entry)
    return {
        "message": "Decision added to blacklist",
        "entry": entry.model_dump(),
        "blacklist": [b.model_dump() for b in runtime.blacklist]
    }


@router.delete("/decisions/{name}")
async def remove_decision(name: str, runtime: DecisionRuntime = Depends(get_runtime)):
    """Removes a decision from the runtime."""
    if name not in runtime.decision_names():
        raise HTTPException(status_code=404, detail="Decision not found")

    # Also remove from blacklist if present
    runtime.blacklist = [b for b in runtime.blacklist if b.name != name]
    runtime.decisions = [d for d in runtime.decisions if d.name != name]

    return {
        "message": "Decision removed",
        "decisions": [d.model_dump() for d in runtime.decisions],
        "blacklist": [b.model_dump() for b in runtime.blacklist]
    }


@router.delete("/blacklist/{name}")
async def remove_from_blacklist(name: str, runtime: DecisionRuntime = Depends(get_runtime)):
    """Removes a decision from the blacklist."""
    if name not in runtime.blacklist_names():
        raise HTTPException(status_code=404, detail="Decision not in blacklist")

    runtime.blacklist = [b for b in runtime.blacklist if b.name != name]

    return {
        "message": "Decision removed from blacklist",
        "blacklist": [b.model_dump() for b in runtime.blacklist]
    }
