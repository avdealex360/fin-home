from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session, joinedload

from app.models import Debt, MonthlyPlan, SinkingFund
from app.services.allocation import get_allocation_levels
from app.services.plan import PlanService
from app.templates_config import _shift_month


@dataclass
class ForecastMonth:
    year: int
    month: int
    label: str
    income: Decimal
    planned_expenses: Decimal
    debt_payments: Decimal
    fund_spends: Decimal
    net: Decimal
    events: list[str] = field(default_factory=list)


@dataclass
class CascadeScenario:
    debt_name: str
    freed_monthly: Decimal
    suggestion: str
    months_to_close_target: int | None


class ForecastService:
    @staticmethod
    def cash_flow_forecast(db: Session, months_ahead: int = 3) -> list[ForecastMonth]:
        today = date.today()
        year, month = today.year, today.month
        results: list[ForecastMonth] = []

        debts = db.query(Debt).filter(Debt.is_closed.is_(False)).all()
        funds = db.query(SinkingFund).filter(SinkingFund.is_active.is_(True)).all()
        closed_in_forecast: set[int] = set()

        for _ in range(months_ahead):
            plan = (
                db.query(MonthlyPlan)
                .options(joinedload(MonthlyPlan.limits))
                .filter(MonthlyPlan.year == year, MonthlyPlan.month == month)
                .first()
            )
            income = plan.expected_income if plan else Decimal("0")
            if income <= 0:
                _, categories = PlanService.get_plan_with_limits(db, year, month)
                # fallback: use current month plan
                cur_plan = (
                    db.query(MonthlyPlan)
                    .filter(MonthlyPlan.year == today.year, MonthlyPlan.month == today.month)
                    .first()
                )
                income = cur_plan.expected_income if cur_plan else Decimal("110000")

            levels = get_allocation_levels(db, year, month, income)
            planned = sum(l.total_suggested for l in levels)

            debt_pay = Decimal("0")
            events: list[str] = []
            for debt in debts:
                if debt.id in closed_in_forecast or debt.is_closed:
                    continue
                if debt.target_close_date:
                    if (
                        debt.target_close_date.year == year
                        and debt.target_close_date.month == month
                    ):
                        events.append(
                            f"{debt.name} закрыт — +{debt.monthly_payment:,.0f} ₽/мес".replace(",", " ")
                        )
                        closed_in_forecast.add(debt.id)
                    elif (
                        debt.target_close_date.year > year
                        or (
                            debt.target_close_date.year == year
                            and debt.target_close_date.month >= month
                        )
                    ):
                        debt_pay += debt.monthly_payment
                else:
                    debt_pay += debt.monthly_payment

            fund_spend = Decimal("0")
            for fund in funds:
                if fund.target_date and fund.target_date.year == year and fund.target_date.month == month:
                    spend = min(fund.current_amount, fund.target_amount)
                    if spend > 0:
                        fund_spend += spend
                        events.append(f"{fund.name}: −{spend:,.0f} ₽ (из копилки)".replace(",", " "))

            net = income - planned - debt_pay - fund_spend
            results.append(
                ForecastMonth(
                    year=year,
                    month=month,
                    label=f"{year}-{month:02d}",
                    income=income,
                    planned_expenses=planned,
                    debt_payments=debt_pay,
                    fund_spends=fund_spend,
                    net=net,
                    events=events,
                )
            )
            year, month = _shift_month(year, month, 1)

        return results

    @staticmethod
    def cascade_after_debt_close(db: Session) -> list[CascadeScenario]:
        scenarios: list[CascadeScenario] = []
        split = db.query(Debt).filter(Debt.name == "Яндекс Сплит").first()
        credit = db.query(Debt).filter(Debt.name == "Кредитка Тинькофф").first()

        if split and not split.is_closed and split.monthly_payment > 0:
            freed = split.monthly_payment
            months = None
            if credit and not credit.is_closed and credit.remaining > 0:
                months = int(
                    (credit.remaining / freed).to_integral_value()
                    if freed > 0
                    else 0
                )
            scenarios.append(
                CascadeScenario(
                    debt_name=split.name,
                    freed_monthly=freed,
                    suggestion=(
                        f"Направить {freed:,.0f} ₽/мес на досрочное погашение кредитки?".replace(",", " ")
                        if credit and not credit.is_closed
                        else f"После закрытия Сплита высвободится {freed:,.0f} ₽/мес".replace(",", " ")
                    ),
                    months_to_close_target=months,
                )
            )

        return scenarios
