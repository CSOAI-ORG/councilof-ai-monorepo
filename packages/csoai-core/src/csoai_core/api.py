"""SOVOS Evaluator HTTP API.

Deployable FastAPI service exposing the GSPC scoring engine and the
ETSI EN 304 223 compliance matrix over HTTP. Deterministic, auditable,
cloud-agnostic - runs anywhere (Mac, Oracle EU SC, edge, air-gapped).
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .gspc import GSPCScore, compliance_matrix, score_gspc

app = FastAPI(
    title="SOVOS Evaluator",
    version="0.1.0",
    description="Sovereign Operating System for AI Governance - GSPC scoring over ETSI EN 304 223.",
)


class ScoreRequest(BaseModel):
    record: Dict[str, Any]


class ScoreResponse(BaseModel):
    G: float
    S: float
    P: float
    C: float
    composite: float
    grade: str
    passed_principles: list[str]
    failed_principles: list[str]


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "sovos-evaluator"}


@app.get("/matrix")
def matrix() -> list[dict]:
    """Return the 13-principle ETSI EN 304 223 compliance matrix."""
    return compliance_matrix()


@app.post("/score", response_model=ScoreResponse)
def score(req: ScoreRequest) -> GSPCScore:
    if not isinstance(req.record, dict):
        raise HTTPException(status_code=422, detail="record must be a JSON object")
    return score_gspc(req.record)
