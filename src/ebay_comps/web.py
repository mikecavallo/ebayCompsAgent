"""Minimal web UI: `uvicorn ebay_comps.web:app` (needs the `web` extra)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

from ebay_comps.agent import run_comps
from ebay_comps.config import ConfigError, make_advisor, make_source
from ebay_comps.llm.base import AdvisorError
from ebay_comps.models import CompsReport
from ebay_comps.providers.base import ProviderError

app = FastAPI(title="eBay Comps Agent", version="0.2.0")


@app.get("/api/comps", response_model=CompsReport)
def comps(
    q: str = Query(..., min_length=2, max_length=200),
    condition: Literal["any", "new", "used"] = "any",
    limit: int = Query(100, ge=1, le=200),
    source: Literal["auto", "ebay", "fixture"] = "auto",
    llm: Literal["auto", "anthropic", "openai", "mock"] = "auto",
) -> CompsReport:
    try:
        return run_comps(
            q, make_source(source), make_advisor(llm), condition=condition, limit=limit
        )
    except (ConfigError, ProviderError, AdvisorError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


PAGE = (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return PAGE
