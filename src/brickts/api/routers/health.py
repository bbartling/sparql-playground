from fastapi import APIRouter, Depends, Request

from brickts.api.deps import AppState, get_app_state
from brickts.api.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(request: Request, state: AppState = Depends(get_app_state)) -> HealthResponse:
    ready = getattr(state, "ready", True)
    err = getattr(state, "bootstrap_error", None)
    status = "ok" if ready and not err else ("starting" if not err else "error")
    return HealthResponse(status=status, ready=ready, bootstrap_error=err)
