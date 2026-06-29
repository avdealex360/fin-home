from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import SinkingFund, SinkingFundContribution, Transaction


@dataclass
class FundSummary:
    id: int
    name: str
    target_amount: Decimal
    current_amount: Decimal
    monthly_contribution: Decimal
    target_date: date | None
    progress_percent: float
    is_rolling: bool
    linked_category_id: int | None


class SinkingFundService:
    @staticmethod
    def list_active(db: Session) -> list[SinkingFund]:
        return (
            db.query(SinkingFund)
            .filter(SinkingFund.is_active.is_(True))
            .order_by(SinkingFund.id)
            .all()
        )

    @staticmethod
    def get_summaries(db: Session) -> list[FundSummary]:
        funds = SinkingFundService.list_active(db)
        result = []
        for fund in funds:
            progress = (
                float(fund.current_amount / fund.target_amount * 100)
                if fund.target_amount > 0
                else 0.0
            )
            result.append(
                FundSummary(
                    id=fund.id,
                    name=fund.name,
                    target_amount=fund.target_amount,
                    current_amount=fund.current_amount,
                    monthly_contribution=fund.monthly_contribution,
                    target_date=fund.target_date,
                    progress_percent=min(progress, 100.0),
                    is_rolling=fund.is_rolling,
                    linked_category_id=fund.linked_category_id,
                )
            )
        return result

    @staticmethod
    def contribute(
        db: Session,
        fund_id: int,
        amount: Decimal,
        contrib_date: date,
        note: str | None = None,
    ) -> SinkingFund:
        fund = db.query(SinkingFund).filter(SinkingFund.id == fund_id).first()
        if not fund:
            raise ValueError("Fund not found")
        fund.current_amount += amount
        db.add(
            SinkingFundContribution(
                fund_id=fund_id,
                amount=amount,
                date=contrib_date,
                note=note,
            )
        )
        SinkingFundService._check_rolling(fund)
        db.commit()
        db.refresh(fund)
        return fund

    @staticmethod
    def spend_from_fund(
        db: Session,
        fund_id: int,
        amount: Decimal,
        spend_date: date,
        category_id: int | None,
        user_id: int | None,
        comment: str | None,
    ) -> Transaction:
        fund = db.query(SinkingFund).filter(SinkingFund.id == fund_id).first()
        if not fund:
            raise ValueError("Fund not found")
        fund.current_amount -= amount
        if fund.current_amount < 0:
            fund.current_amount = Decimal("0")
        tx = Transaction(
            type="expense",
            amount=amount,
            date=spend_date,
            category_id=category_id or fund.linked_category_id,
            user_id=user_id,
            comment=comment,
            is_sinking_fund_spend=True,
            fund_id=fund_id,
        )
        db.add(tx)
        SinkingFundService._check_rolling(fund)
        db.commit()
        db.refresh(tx)
        return tx

    @staticmethod
    def _check_rolling(fund: SinkingFund) -> None:
        if fund.is_rolling and fund.target_amount > 0 and fund.current_amount >= fund.target_amount:
            fund.current_amount = Decimal("0")

    @staticmethod
    def create(
        db: Session,
        name: str,
        target_amount: Decimal,
        monthly_contribution: Decimal,
        category_group: str = "needs",
        target_date: date | None = None,
        is_rolling: bool = False,
        linked_category_id: int | None = None,
    ) -> SinkingFund:
        fund = SinkingFund(
            name=name,
            target_amount=target_amount,
            current_amount=Decimal("0"),
            monthly_contribution=monthly_contribution,
            target_date=target_date,
            category_group=category_group,
            is_rolling=is_rolling,
            linked_category_id=linked_category_id,
        )
        db.add(fund)
        db.commit()
        db.refresh(fund)
        return fund

    @staticmethod
    def update(
        db: Session,
        fund_id: int,
        name: str,
        target_amount: Decimal,
        monthly_contribution: Decimal,
        target_date: date | None = None,
        is_rolling: bool = False,
    ) -> SinkingFund:
        fund = db.query(SinkingFund).filter(SinkingFund.id == fund_id).first()
        if not fund:
            raise ValueError("Fund not found")
        fund.name = name
        fund.target_amount = target_amount
        fund.monthly_contribution = monthly_contribution
        fund.target_date = target_date
        fund.is_rolling = is_rolling
        db.commit()
        db.refresh(fund)
        return fund

    @staticmethod
    def delete(db: Session, fund_id: int) -> None:
        fund = db.query(SinkingFund).filter(SinkingFund.id == fund_id).first()
        if fund:
            fund.is_active = False
            db.commit()

    @staticmethod
    def last_contribution_date(db: Session, fund_id: int) -> date | None:
        from sqlalchemy import func

        return (
            db.query(func.max(SinkingFundContribution.date))
            .filter(SinkingFundContribution.fund_id == fund_id)
            .scalar()
        )
