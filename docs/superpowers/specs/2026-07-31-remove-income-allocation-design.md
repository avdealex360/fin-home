# Remove income allocation feature

Date: 2026-07-31. Status: approved (subproject 1 of 4: allocation removal → multi-tenancy → landing → analytics revision).

## Behavior change

Income is recorded as a plain transaction and immediately counts toward the month balance
(`income_fact`). No post-save "distribute across buckets" step — income gets the same
toast+undo flow as expenses. Sinking funds are topped up only via explicit operations.

## Backend

Delete outright:
- `app/api/allocation.py`, `app/services/allocation.py`
- `IncomeAllocation` model, `Transaction.is_fully_allocated`, `Category.allocation_level`
- Dead code: `forecast.py` `cash_flow_forecast` (only external consumer of allocation
  buckets; `cash_flow` payload unused by the UI), unreachable `debt_forecast` /
  `debt_payments` / `category_history` + its `/api/analytics/category/{id}` endpoint.

Edit:
- `main.py` — drop allocation router.
- `api/transactions.py` — drop `unallocated` from income-create response.
- `api/meta.py` — category delete check reduced to `Transaction` only; drop
  `allocation_level` from `CategoryBody`.
- `serializers.py` — drop `allocation_level`, `is_fully_allocated`.
- `services/dashboard.py` — drop `MonthSummary.unallocated` / `.is_fully_allocated`.
- `seed.py` — demo categories without levels; `ensure_savings_category` without level.
- Tests: delete/rewrite allocation tests in `test_redesign.py`, `test_v2.py`.

Migration: new Alembic revision on top of `c3e4f5g6h7i8` — `drop_table("income_allocations")`,
drop the two columns. Historical allocations are lost; `SinkingFund.current_amount` is NOT
recalculated (money already moved by the wizard is real).

## Frontend

- Delete `AllocationSheet.svelte`.
- `App.svelte`: sheet state `'closed' | 'form'`; income submits like expense; drop
  `onAllocated`, `allocTxId`, the allocation BottomSheet, `onAllocate` prop.
- `Dashboard.svelte`: remove «К распределению» CTA card + styles + `pendingIncome`.
- `api.ts`: remove allocation interfaces/methods and the dropped fields.

## Verification

`make test` (pytest), `npm run build`, manual: add income → in balance immediately, toast with undo.
