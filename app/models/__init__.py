from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class AppUser(Base):
    __tablename__ = "app_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="user")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    group: Mapped[str] = mapped_column(String(20), nullable=False)  # needs, wants, savings
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="category")
    limits: Mapped[list["CategoryLimit"]] = relationship(back_populates="category")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # income, expense, transfer
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("app_users.id"), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_amount_eur: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    category: Mapped["Category | None"] = relationship(back_populates="transactions")
    user: Mapped["AppUser | None"] = relationship(back_populates="transactions")


class MonthlyPlan(Base):
    __tablename__ = "monthly_plans"
    __table_args__ = (UniqueConstraint("year", "month", name="uq_plan_year_month"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_income: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))

    limits: Mapped[list["CategoryLimit"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )


class CategoryLimit(Base):
    __tablename__ = "category_limits"
    __table_args__ = (UniqueConstraint("plan_id", "category_id", name="uq_plan_category"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("monthly_plans.id"), nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    limit_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))

    plan: Mapped["MonthlyPlan"] = relationship(back_populates="limits")
    category: Mapped["Category"] = relationship(back_populates="limits")


class Debt(Base):
    __tablename__ = "debts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    remaining: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    monthly_payment: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    interest_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # credit_card, split, loan
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    target_close_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    grace_period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_payment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False)

    payments: Mapped[list["DebtPayment"]] = relationship(
        back_populates="debt", cascade="all, delete-orphan"
    )


class DebtPayment(Base):
    __tablename__ = "debt_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    debt_id: Mapped[int] = mapped_column(ForeignKey("debts.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    debt: Mapped["Debt"] = relationship(back_populates="payments")


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    target_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    current_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    monthly_contribution: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    linked_account_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    contributions: Mapped[list["GoalContribution"]] = relationship(
        back_populates="goal", cascade="all, delete-orphan"
    )


class GoalContribution(Base):
    __tablename__ = "goal_contributions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goals.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    goal: Mapped["Goal"] = relationship(back_populates="contributions")


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class DepositSnapshot(Base):
    __tablename__ = "deposit_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
