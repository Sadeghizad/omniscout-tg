"""
OmniScout-TG: Local web GUI (FastAPI).

    python -m src.web.app          # or: bun run gui

Routes
------
GET  /                  single-page dashboard
GET  /api/config        what this deployment can do (keys present, defaults, preset brief)
POST /api/plan          runs the pipeline, streams stage progress as Server-Sent Events
GET  /api/files/{name}  downloads a generated .xlsx / .csv from the output directory
"""

import json
import os
import queue
import sys
import threading
from pathlib import Path

# Add project root to sys.path so `config` and `src` import when launched directly.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from config.settings import get_settings
from src.models.payload import result_payload
from src.models.schemas import CampaignBrief
from src.pipeline.orchestrator import OmniScoutPipeline

STATIC_DIR = Path(__file__).parent / "static"

PRESET_BRIEF = {
    "campaign_name": "Parvaz Capital Wealth Expansion",
    "product_category": "Finance & Capital Markets",
    "target_persona": (
        "Iranian retail investors, day traders, and crypto enthusiasts seeking analytical software"
    ),
    "seed_channels": ["@parvazcapital_tel"],
    "total_budget_usd": 3000.0,
    "target_cac_usd": 50.0,
}

app = FastAPI(title="OmniScout-TG", docs_url=None, redoc_url=None)


class PlanRequest(BaseModel):
    """Campaign brief accepted from the dashboard."""

    campaign_name: str = Field(min_length=1)
    product_category: str = Field(default="Business", min_length=1)
    target_persona: str = Field(min_length=1)
    seed_channels: list[str] = Field(min_length=1)
    total_budget_usd: float = Field(default=1000.0, gt=0)
    target_cac_usd: float = Field(default=50.0, gt=0)
    est_cvr: float = Field(default=0.02, gt=0, le=1.0)
    est_ctr_min: float = Field(default=0.01, gt=0, le=1.0)
    est_ctr_max: float = Field(default=0.025, gt=0, le=1.0)
    risk_buffer: float = Field(default=0.15, ge=0.0, le=0.5)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/config")
def config() -> dict:
    """Reports the live capabilities of this deployment. Never returns secret values."""
    settings = get_settings()
    return {
        "bai_live": settings.is_bai_live_enabled,
        "mtproto_enabled": settings.is_telegram_mtproto_enabled,
        "environment": settings.environment,
        "output_dir": str(settings.output_dir.resolve()),
        "defaults": {
            "est_cvr": settings.default_cvr_est,
            "est_ctr_min": settings.default_ctr_min,
            "est_ctr_max": settings.default_ctr_max,
            "risk_buffer": settings.default_risk_buffer,
            "target_cac_usd": settings.default_target_cac,
        },
        "preset": PRESET_BRIEF,
    }


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/api/plan")
def plan(req: PlanRequest) -> StreamingResponse:
    """Runs the pipeline in a worker thread and streams progress until the result lands."""
    brief = CampaignBrief(**req.model_dump())
    settings = get_settings()
    events: queue.Queue[tuple[str, dict]] = queue.Queue()

    def worker() -> None:
        def on_progress(message: str, step: int, total: int) -> None:
            events.put(("progress", {"message": message, "step": step, "total": total}))

        try:
            result = OmniScoutPipeline(settings=settings).execute(
                brief, progress_callback=on_progress
            )
            events.put(("result", result_payload(result)))
        except Exception as exc:  # noqa: BLE001 - surfaced to the operator as a stream event
            events.put(("error", {"message": f"{type(exc).__name__}: {exc}"}))

    threading.Thread(target=worker, daemon=True).start()

    def stream():
        while True:
            try:
                event, data = events.get(timeout=15)
            except queue.Empty:
                yield ": keep-alive\n\n"  # discovery can run for minutes without a stage change
                continue
            yield _sse(event, data)
            if event in ("result", "error"):
                return

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/files/{name}")
def download(name: str) -> FileResponse:
    """Serves a generated deliverable by file name, confined to the output directory."""
    output_dir = get_settings().output_dir.resolve()
    path = (output_dir / Path(name).name).resolve()
    if path.parent != output_dir or not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, filename=path.name)


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def main() -> None:
    """Starts the dashboard on localhost only."""
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")


if __name__ == "__main__":
    main()
