# TOCHECK: i don't think this is the objective :( -- vcnt
from fastapi import APIRouter, Depends, HTTPException, Request

from src.core.runtime import DecisionRuntime
from src.models import RiskLevelEntry

router = APIRouter(tags=["Risk Levels", "Configuration"])


def get_runtime(request: Request) -> DecisionRuntime:
    return request.app.state.decision_runtime


@router.get("/risk-levels")
async def list_risk_levels(runtime: DecisionRuntime = Depends(get_runtime)):
    """Returns the list of available risk levels."""
    return {
        "risk_levels": [r.model_dump() for r in runtime.risk_levels],
        "count": len(runtime.risk_levels),
    }


@router.post("/risk-levels")
async def add_risk_level(
    entry: RiskLevelEntry, runtime: DecisionRuntime = Depends(get_runtime)
):
    """Adds a risk level to the runtime and persists to database."""
    if entry.name in runtime.risk_level_names():
        raise HTTPException(status_code=400, detail="Risk level already exists")

    persisted = runtime.persist_risk_level(entry)
    runtime.risk_levels.append(entry)

    return {
        "message": "Risk level added",
        "risk_level": entry.model_dump(),
        "id": persisted.id,
        "risk_levels": [r.model_dump() for r in runtime.risk_levels],
    }


@router.delete("/risk-levels/{name}")
async def remove_risk_level(name: str, runtime: DecisionRuntime = Depends(get_runtime)):
    """Removes a risk level from the runtime and database."""
    if name not in runtime.risk_level_names():
        raise HTTPException(status_code=404, detail="Risk level not found")

    runtime.delete_risk_level(name)
    runtime.risk_levels = [r for r in runtime.risk_levels if r.name != name]

    return {
        "message": "Risk level removed",
        "risk_levels": [r.model_dump() for r in runtime.risk_levels],
    }
