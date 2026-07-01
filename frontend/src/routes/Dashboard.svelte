<script lang="ts">
  import { api, type MonthSummary, type Transaction } from '../lib/api'
  import { period, dataVersion, showToast, invalidate } from '../lib/stores'
  import { money, monthName, formatDate } from '../lib/format'
  import ProgressBar from '../lib/components/ProgressBar.svelte'
  import Loader from '../lib/components/Loader.svelte'

  interface Props {
    onAllocate: (txId: number) => void
  }
  let { onAllocate }: Props = $props()

  let summary = $state<MonthSummary | null>(null)
  let recent = $state<Transaction[]>([])
  let plannedExpenses = $state<any[]>([])
  let revealed = $state<number | null>(null)

  $effect(() => {
    // Re-run whenever period or dataVersion changes.
    const { year, month } = $period
    void $dataVersion
    load(year, month)
  })

  async function load(year: number, month: number) {
    const [s, r, p] = await Promise.all([
      api.dashboard(year, month),
      api.transactions(10, year, month),
      api.plan(year, month),
    ])
    summary = s
    recent = r
    plannedExpenses = p.planned_expenses
  }

  let pendingIncome = $derived(recent.find((t) => t.type === 'income' && !t.is_fully_allocated))

  async function del(tx: Transaction) {
    revealed = null
    recent = recent.filter((t) => t.id !== tx.id)
    await api.deleteTransaction(tx.id)
    invalidate()
    showToast('Операция удалена', async () => {
      await api.createTransaction({
        type: tx.type,
        amount: tx.amount,
        category_id: tx.category_id,
        user_id: tx.user_id,
        date: tx.date,
        comment: tx.comment,
      })
      invalidate()
    })
  }

</script>

{#if !summary}
  <Loader />
{:else}
  <div class="page">
    <!-- Hero -->
    <div class="hero card">
      <span class="section-label">Остаток · {monthName($period.month)}</span>
      <div class="hero-amount num">{money(summary.remaining)} ₽</div>
      <div class="hero-sub muted">
        Доход <span class="num">{money(summary.income_fact)}</span> · Потрачено
        <span class="num">{money(summary.total_spent)}</span>
      </div>
      <div class="hero-chips">
        <span class="chip {summary.savings_rate >= summary.savings_target_rate ? 'green' : 'yellow'}">
          Сбережения {summary.savings_rate.toFixed(0)}%
        </span>
      </div>
    </div>

    <!-- Unallocated -->
    {#if summary.unallocated > 0 && pendingIncome}
      <button class="unalloc card" onclick={() => onAllocate(pendingIncome!.id)}>
        <div>
          <span class="section-label">К распределению</span>
          <div class="num unalloc-amt">{money(summary.unallocated)} ₽</div>
        </div>
        <span class="chip blue">Распределить <i class="ti ti-arrow-right"></i></span>
      </button>
    {/if}

    <!-- 50/30/20 -->
    <div class="card stack">
      {#each summary.groups as g}
        <div>
          <div class="row grp-row">
            <span class="grp-label">{g.label}</span>
            <span class="muted num grp-amt">
              {#if g.name === 'savings'}
                <span class="aside-label">отложено</span>
              {/if}
              {money(g.spent)} / {money(g.limit)}
            </span>
          </div>
          <ProgressBar spent={g.spent} limit={g.limit} color={g.color} showPace={true} />
        </div>
      {/each}
    </div>

    <!-- Debts -->
    {#if summary.debts.length}
      <div>
        <div class="section-label">Долги</div>
        <div class="stack">
          {#each summary.debts as d}
            <div class="card debt" class:priority={d.priority_label === 'Приоритет'}>
              <div class="row">
                <strong>{d.name}</strong>
                <span class="num">{money(d.remaining)} ₽</span>
              </div>
              <div class="row muted small">
                <span>{d.interest_rate > 0 ? `${d.interest_rate}%` : 'Без %'}</span>
                {#if d.priority_label}<span>{d.priority_label}</span>{/if}
              </div>
              <ProgressBar spent={d.total_amount - d.remaining} limit={d.total_amount} color="blue" />
            </div>
          {/each}
        </div>
      </div>
    {/if}

    <!-- Planned big expenses -->
    {#if plannedExpenses.length}
      <div>
        <div class="section-label">Ожидаемые крупные расходы</div>
        <div class="card stack">
          {#each plannedExpenses as e}
            <div class="row">
              <span>{e.description}{#if e.expected_date}<span class="muted small-inline"> · {formatDate(e.expected_date)}</span>{/if}</span>
              <span class="num">{money(e.amount)} ₽</span>
            </div>
          {/each}
        </div>
      </div>
    {/if}

    <!-- Recent -->
    <div>
      <a class="section-label recent-link" href="#/transactions">
        Последние операции <i class="ti ti-chevron-right"></i>
      </a>
      {#if recent.length === 0}
        <p class="muted">Пока нет операций. Нажмите + чтобы добавить.</p>
      {:else}
        <div class="stack">
          {#each recent as t (t.id)}
            <div class="tx-wrap">
              <button class="tx" onclick={() => (revealed = revealed === t.id ? null : t.id)}>
                <span class="tx-cat">{t.category_name ?? (t.type === 'income' ? 'Доход' : '—')}</span>
                <span class="tx-meta muted">{formatDate(t.date)}{t.user_name ? ` · ${t.user_name}` : ''}</span>
                <span class="tx-amt num" class:income={t.type === 'income'}>
                  {t.type === 'income' ? '+' : '−'}{money(t.amount)} ₽
                </span>
              </button>
              {#if revealed === t.id}
                <button class="tx-del" onclick={() => del(t)} aria-label="Удалить">
                  <i class="ti ti-trash"></i>
                </button>
              {/if}
            </div>
          {/each}
        </div>
      {/if}
    </div>
  </div>
{/if}

<style>
  .recent-link { display: flex; align-items: center; gap: 2px; width: fit-content; }
  .recent-link i { font-size: 14px; }
  .hero-amount { font-size: var(--text-3xl); font-weight: 500; margin: 4px 0; }
  .hero-sub { font-size: var(--text-sm); }
  .hero-chips { display: flex; gap: var(--space-2); margin-top: var(--space-3); }
  .unalloc { display: flex; align-items: center; justify-content: space-between; width: 100%; border: 1px solid var(--blue-border); background: var(--blue-bg); text-align: left; }
  .unalloc-amt { font-size: var(--text-xl); }
  .debt.priority { border-left: 3px solid var(--red); }
  .small { font-size: var(--text-xs); margin: 4px 0 8px; }
  .small-inline { font-size: var(--text-xs); }
  .tx-wrap { display: flex; gap: var(--space-2); align-items: stretch; }
  .tx { flex: 1; display: grid; grid-template-columns: 1fr auto; grid-template-rows: auto auto; gap: 2px 0; background: var(--bg-surface); border: none; border-radius: var(--radius-md); padding: var(--space-3); text-align: left; }
  .tx-cat { font-size: var(--text-base); }
  .tx-meta { font-size: var(--text-xs); }
  .tx-amt { grid-row: 1 / 3; grid-column: 2; align-self: center; }
  .tx-amt.income { color: var(--green); }
  .tx-del { background: var(--red-bg); color: var(--red); border: none; border-radius: var(--radius-md); width: 56px; }
  .aside-label { font-size: var(--text-xs); opacity: 0.7; margin-right: var(--space-1); }
  /* Keep the 50/30/20 label + amounts on one line on narrow phones:
     tighten the monospace digits and shrink the amount a touch. */
  .grp-row { gap: var(--space-2); }
  .grp-label { flex: 0 1 auto; min-width: 0; }
  .grp-amt { flex: 0 0 auto; white-space: nowrap; text-align: right; font-size: var(--text-sm); letter-spacing: -0.03em; }
  .grp-amt .aside-label { letter-spacing: 0; }
</style>
