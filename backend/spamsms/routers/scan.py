"""Bulk CSV inbox scanning. Pro-gated.

CSV is read from the RAW request body (not UploadFile/Form) so we never depend on
python-multipart, which cannot be guaranteed on every install here. Frontend sends
the file bytes directly: fetch(url, {method:'POST', body: file}).
"""

from __future__ import annotations

import csv
import io
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Request

from ..model import predict_message
from ..schemas import ScanResponse, ScanRow, ScanSummary
from ..security import Identity, current_identity

router = APIRouter(prefix="/api", tags=["scan"])


def require_pro(identity: Identity = Depends(current_identity)) -> Identity:
    if not identity.can_bulk_scan:
        raise HTTPException(status_code=403, detail="Bulk inbox scanning is a Pro feature.")
    return identity


@router.post("/scan", response_model=ScanResponse)
async def scan(
    request: Request,
    identity: Identity = Depends(require_pro),
):
    settings = request.app.state.settings
    content_type = (request.headers.get("content-type") or "").lower()
    if "csv" not in content_type and "octet-stream" not in content_type and "text/plain" not in content_type:
        raise HTTPException(status_code=415, detail="Upload a CSV file (text/csv).")

    raw = await request.body()
    if len(raw) > settings.max_scan_bytes:
        raise HTTPException(status_code=413, detail="File exceeds the 2 MiB scan limit.")
    try:
        decoded = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded CSV.") from exc

    reader = csv.DictReader(io.StringIO(decoded))
    fieldnames = reader.fieldnames or []
    message_column = next((c for c in ("message", "text") if c in fieldnames), None)
    if message_column is None:
        raise HTTPException(status_code=400, detail="CSV must contain a 'message' or 'text' column.")

    bundle = request.app.state.bundle
    rows: list[ScanRow] = []
    counts = Counter()
    signal_counts: Counter = Counter()
    truncated = False
    for i, record in enumerate(reader):
        if i >= settings.max_scan_rows:
            truncated = True
            break
        text = (record.get(message_column) or "").strip()
        if not text:
            continue
        result = predict_message(text, bundle)
        counts[result["label"]] += 1
        for sig in result["signals"]:
            signal_counts[sig["title"]] += 1
        rows.append(
            ScanRow(
                index=i,
                message=text[:500],
                label=result["label"],
                spam_probability=result["spam_probability"],
                trigger_words=[d["word"] for d in result["drivers"]],
                safety_signals=[s["title"] for s in result["signals"]],
            )
        )

    summary = ScanSummary(
        scanned=sum(counts.values()),
        spam=counts.get("SPAM", 0),
        ham=counts.get("HAM", 0),
        unsure=counts.get("UNSURE", 0),
        top_signals=signal_counts.most_common(8),
    )
    return ScanResponse(summary=summary, rows=rows[:200], truncated=truncated or len(rows) > 200)
