"""Single-message analysis. Consumes one quota credit (anon grace / trial) or
passes for paid users. Runs entirely offline against the local model bundle.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from ..model import predict_message
from ..schemas import AnalyzeRequest, AnalyzeResponse, QuotaStatus
from ..security import Identity, require_analysis_quota

router = APIRouter(prefix="/api", tags=["analyze"])


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(
    body: AnalyzeRequest,
    request: Request,
    identity: Identity = Depends(require_analysis_quota),
):
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Message text is required.")
    try:
        result = predict_message(text, request.app.state.bundle)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    quota = QuotaStatus(
        kind=identity.kind,
        remaining=identity.remaining,
        limit=identity.limit,
        pays_wall=(identity.kind == "anonymous" and (identity.remaining or 0) <= 0),
    )
    return AnalyzeResponse(
        label=result["label"],
        spam_probability=result["spam_probability"],
        matched_vocabulary_terms=result["matched_vocabulary_terms"],
        drivers=result["drivers"],
        signals=result["signals"],
        domains=result["domains"],
        quota=quota,
    )
