"""Small FastAPI adapter for the isolated inventory-ledger laboratory."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.lab_db_extension import adjust_stock, create_order


class AdjustmentRequest(BaseModel):
    sku: str
    quantity: int
    reason: str


class OrderRequest(BaseModel):
    idempotency_key: str
    items: dict[str, int]


def create_app(db_path: str | Path) -> FastAPI:
    app = FastAPI(title="REA inventory ledger laboratory")

    @app.post("/inventory/adjust")
    def adjust(request: AdjustmentRequest) -> dict:
        try:
            return adjust_stock(
                db_path, request.sku, request.quantity, request.reason
            )
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/orders")
    def sell(request: OrderRequest) -> dict:
        try:
            return create_order(db_path, request.idempotency_key, request.items)
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app
