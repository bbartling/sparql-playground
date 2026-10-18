from bldgts.api.deps import AppState, get_app_state
from bldgts.api.schemas import HealthResponse
from fastapi import APIRouter, Depends

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health / wake (Render free tier)",
    description=(
        'Ping after the free instance has slept. Retry until status is "ok" and ready is true.'
    ),
)
def health(state: AppState = Depends(get_app_state)) -> HealthResponse:
    ready = getattr(state, "ready", True)
    err = getattr(state, "bootstrap_error", None)
    status = "ok" if ready and not err else ("starting" if not err else "error")
    return HealthResponse(status=status, ready=ready, bootstrap_error=err)
