"""Explicit ORM -> dict serializers.

We avoid returning ORM objects directly so relationship lazy-loads never leak
into responses. Domain dataclasses (MonthSummary, FundSummary, ...) are returned
as-is and encoded by FastAPI's jsonable_encoder (Decimal -> float, date -> str).
"""

from app.category_icons import get_category_icon
from app.models import (
    AppUser,
    Category,
    Debt,
    DebtPayment,
    MonthlyPlan,
    PlannedDebtPayment,
    PlannedExpense,
    SinkingFund,
    Transaction,
)


def user_dict(u: AppUser) -> dict:
    return {"id": u.id, "name": u.name, "is_active": u.is_active, "telegram_id": u.telegram_id}


def category_dict(c: Category) -> dict:
    icon = get_category_icon(c.name, c.group)
    return {
        "id": c.id,
        "name": c.name,
        "group": c.group,
        "is_hidden": c.is_hidden,
        "sort_order": c.sort_order,
        "icon": c.icon or icon["icon"],
        "color": icon["color"],
    }


def transaction_dict(t: Transaction) -> dict:
    return {
        "id": t.id,
        "type": t.type,
        "amount": float(t.amount),
        "date": t.date.isoformat() if t.date else None,
        "category_id": t.category_id,
        "category_name": t.category.name if t.category else None,
        "user_id": t.user_id,
        "user_name": t.user.name if t.user else None,
        "comment": t.comment,
        "is_sinking_fund_spend": t.is_sinking_fund_spend,
        "fund_id": t.fund_id,
    }


def fund_dict(f: SinkingFund) -> dict:
    progress = float(f.current_amount / f.target_amount * 100) if f.target_amount > 0 else 0.0
    return {
        "id": f.id,
        "name": f.name,
        "target_amount": float(f.target_amount),
        "current_amount": float(f.current_amount),
        "monthly_contribution": float(f.monthly_contribution),
        "target_date": f.target_date.isoformat() if f.target_date else None,
        "group": f.group,  # renamed from category_group in two-pots redesign
        "is_rolling": f.is_rolling,
        "is_active": f.is_active,
        "progress_percent": min(progress, 100.0),
    }


def deposit_dict(s: dict) -> dict:
    return {
        "balance": float(s["balance"]),
        "rate": float(s["rate"]),
        "cap_day": s["cap_day"],
        "start_date": s["start_date"].isoformat() if s["start_date"] else None,
        "monthly_target": float(s["monthly_target"]),
    }


def debt_dict(d: Debt) -> dict:
    progress = (
        float((d.total_amount - d.remaining) / d.total_amount * 100)
        if d.total_amount > 0
        else 0.0
    )
    return {
        "id": d.id,
        "name": d.name,
        "total_amount": float(d.total_amount),
        "remaining": float(d.remaining),
        "monthly_payment": float(d.monthly_payment),
        "interest_rate": float(d.interest_rate),
        "type": d.type,
        "start_date": d.start_date.isoformat() if d.start_date else None,
        "target_close_date": d.target_close_date.isoformat() if d.target_close_date else None,
        "grace_period_end": d.grace_period_end.isoformat() if d.grace_period_end else None,
        "next_payment_date": d.next_payment_date.isoformat() if d.next_payment_date else None,
        "is_closed": d.is_closed,
        "priority_rank": d.priority_rank,
        "progress_percent": progress,
    }


def debt_payment_dict(p: DebtPayment) -> dict:
    return {
        "id": p.id,
        "debt_id": p.debt_id,
        "amount": float(p.amount),
        "date": p.date.isoformat() if p.date else None,
        "comment": p.comment,
    }


def planned_expense_dict(e: PlannedExpense) -> dict:
    return {
        "id": e.id,
        "plan_id": e.plan_id,
        "description": e.description,
        "amount": float(e.amount),
        "category_id": e.category_id,
        "category_name": e.category.name if e.category else None,
        "expected_date": e.expected_date.isoformat() if e.expected_date else None,
    }


def planned_debt_dict(p: PlannedDebtPayment) -> dict:
    return {
        "id": p.id,
        "plan_id": p.plan_id,
        "debt_id": p.debt_id,
        "debt_name": p.debt.name if p.debt else None,
        "amount": float(p.amount),
    }


def plan_dict(p: MonthlyPlan, spent: dict | None = None) -> dict:
    spent = spent or {}
    return {
        "id": p.id,
        "year": p.year,
        "month": p.month,
        "expected_income": float(p.expected_income),
        "limits": [
            {
                "id": l.id,
                "category_id": l.category_id,
                "limit_amount": float(l.limit_amount),
                "carried_over": float(l.carried_over or 0),
                "spent": float(spent.get(l.category_id, 0)),
            }
            for l in p.limits
        ],
        "planned_expenses": [planned_expense_dict(e) for e in p.planned_expenses],
        "planned_debt_payments": [planned_debt_dict(d) for d in p.planned_debt_payments],
    }
