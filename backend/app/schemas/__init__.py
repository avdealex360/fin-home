from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class TransactionCreate(BaseModel):
    type: str
    amount: Decimal = Field(gt=0)
    date: date
    category_id: int | None = None
    user_id: int | None = None
    comment: str | None = None
    base_amount_eur: Decimal | None = None


class TransactionUpdate(BaseModel):
    type: str | None = None
    amount: Decimal | None = None
    date: date | None = None
    category_id: int | None = None
    user_id: int | None = None
    comment: str | None = None


class PlanCreate(BaseModel):
    expected_income: Decimal = Field(ge=0)
    category_limits: dict[int, Decimal] = {}


class GoalCreate(BaseModel):
    name: str
    target_amount: Decimal = Field(gt=0)
    current_amount: Decimal = Field(ge=0, default=Decimal("0"))
    deadline: date | None = None
    monthly_contribution: Decimal = Field(ge=0, default=Decimal("0"))
    linked_account_name: str | None = None


class DebtCreate(BaseModel):
    name: str
    total_amount: Decimal = Field(gt=0)
    remaining: Decimal = Field(ge=0)
    monthly_payment: Decimal = Field(ge=0, default=Decimal("0"))
    interest_rate: Decimal = Field(ge=0, default=Decimal("0"))
    type: str
    grace_period_end: date | None = None
    next_payment_date: date | None = None
    target_close_date: date | None = None
