from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, desc
from src.core.database import get_session
from src.models.db import DecisionResult
from src.models.schemas import DecisionResultResponse

router = APIRouter(tags=["Decisions"])


@router.get("/decisions", response_model=list[DecisionResultResponse])
async def list_decision_results(
    decision_name: str | None = Query(default=None, description="Filter by decision name"),
    skip: int = Query(default=0, ge=0, description="Number of results to skip"),
    limit: int = Query(default=20, ge=1, le=100, description="Maximum number of results to return"),
    session: Session = Depends(get_session),
):
    """Returns decision results, ordered by most recent first."""
    query = select(DecisionResult).order_by(desc(DecisionResult.created_at))
    if decision_name:
        query = query.where(DecisionResult.decision_name == decision_name)
    results = session.exec(query.offset(skip).limit(limit)).all()
    return results


# NOTE: /decisions/latest must be declared before /decisions/{decision_id}
# so that FastAPI matches it as a fixed path, not as a path parameter.
@router.get("/decisions/latest", response_model=DecisionResultResponse)
async def get_latest_decision_result(session: Session = Depends(get_session)):
    """Returns the most recent decision result."""
    result = session.exec(
        select(DecisionResult).order_by(desc(DecisionResult.created_at))
    ).first()
    if not result:
        raise HTTPException(status_code=404, detail="No decision results found")
    return result


@router.get("/decisions/{decision_id}", response_model=DecisionResultResponse)
async def get_decision_result(decision_id: int, session: Session = Depends(get_session)):
    """Returns a specific decision result by ID."""
    result = session.get(DecisionResult, decision_id)
    if not result:
        raise HTTPException(status_code=404, detail="Decision result not found")
    return result
