from fastapi import APIRouter, Depends

from brickts.api.deps import AppState, get_app_state
from brickts.api.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Health check")
def health(state: AppState = Depends(get_app_state)) -> HealthResponse:
    ready = getattr(state, "ready", True)
    err = getattr(state, "bootstrap_error", None)
    status = "ok" if ready and not err else ("starting" if not err else "error")
    return HealthResponse(status=status, ready=ready, bootstrap_error=err)


@router.get(
    "/hello",
    summary="Wake / ping (Render free tier)",
    description=(
        "Hit this after the free instance has slept. "
        "When ready=true the SPARQL and timeseries routes are usable."
    ),
)
def hello(state: AppState = Depends(get_app_state)) -> dict:
    ready = getattr(state, "ready", True)
    err = getattr(state, "bootstrap_error", None)
    if err:
        return {
            "message": "brickts is up, but bootstrap failed",
            "ready": False,
            "error": err,
        }
    if not ready:
        return {
            "message": "brickts is waking up — retry /hello in a few seconds",
            "ready": False,
        }
    return {
        "message": "hello from brickts",
        "ready": True,
        "docs": "/docs",
        "try_next": "POST /api/sparql/upload with scripts/sparql/02_fc1_points.rq",
    }
