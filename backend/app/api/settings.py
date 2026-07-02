"""App settings (currency), data export."""

import csv
import io
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Setting, Transaction
from app.serializers import (
    category_dict,
    debt_dict,
    fund_dict,
    transaction_dict,
)
from app.services.settings_store import get_setting, set_setting

router = APIRouter(prefix="/api/settings", tags=["settings"])


class GeneralBody(BaseModel):
    currency: str | None = None


@router.get("")
def get_settings(db: Session = Depends(get_db)):
    keys = ["currency", "onboarded"]
    return {k: get_setting(db, k, "") for k in keys}


@router.post("/general")
def update_general(body: GeneralBody, db: Session = Depends(get_db)):
    for key, value in body.model_dump(exclude_none=True).items():
        set_setting(db, key, value)
    return {"ok": True}


@router.get("/export/json")
def export_json(db: Session = Depends(get_db)):
    from app.models import AppUser, Category, Debt, SinkingFund

    data = {
        "categories": [category_dict(c) for c in db.query(Category).all()],
        "transactions": [transaction_dict(t) for t in db.query(Transaction).all()],
        "debts": [debt_dict(d) for d in db.query(Debt).all()],
        "funds": [fund_dict(f) for f in db.query(SinkingFund).all()],
        "users": [{"id": u.id, "name": u.name} for u in db.query(AppUser).all()],
        "settings": {
            s.key: s.value
            for s in db.query(Setting).all()
            if not s.key.startswith("secret.")
        },
    }
    buf = io.BytesIO(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))
    return StreamingResponse(
        buf,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=fin-home-export.json"},
    )


@router.get("/export/csv")
def export_csv(db: Session = Depends(get_db)):
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["date", "type", "amount", "category", "user", "comment"])
    rows = db.query(Transaction).order_by(Transaction.date).all()
    for t in rows:
        writer.writerow(
            [
                t.date.isoformat() if t.date else "",
                t.type,
                float(t.amount),
                t.category.name if t.category else "",
                t.user.name if t.user else "",
                t.comment or "",
            ]
        )
    buf = io.BytesIO(out.getvalue().encode("utf-8-sig"))
    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=fin-home-transactions.csv"},
    )
