from fastapi import APIRouter

router = APIRouter(prefix="/api/faults", tags=["faults"])

# Fault listing is under /api/equipment/{id}/faults
