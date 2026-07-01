<script lang="ts">
  import { api } from '../lib/api'
  import { showToast } from '../lib/stores'
  import { money, formatDate } from '../lib/format'
  import Chart from '../lib/components/Chart.svelte'

  interface Period {
    yearIndex: number // 2, 3, 4... (year 1 is the base `rate` field)
    rate: number
  }

  let loaded = $state(false)
  let initialLump = $state(0)
  let startDate = $state(`${new Date().getFullYear()}-01-01`)
  let termMonths = $state(12)
  let rate = $state(17.5)
  let periods = $state<Period[]>([])
  let monthlyContribution = $state(0)
  let saving = $state(false)
  let calc = $state<any>(null)

  function monthsBetween(a: string, b: string): number {
    const da = new Date(a), db = new Date(b)
    return (db.getFullYear() - da.getFullYear()) * 12 + (db.getMonth() - da.getMonth())
  }
  function addMonthsISO(iso: string, months: number): string {
    const d = new Date(iso)
    d.setMonth(d.getMonth() + months)
    return d.toISOString().slice(0, 10)
  }

  $effect(() => {
    api.deposit().then((d) => {
      startDate = d.start_date || startDate
      termMonths = d.term_months
      initialLump = d.initial_lump
      monthlyContribution = d.monthly_contribution
      rate = d.rate
      try {
        const sched: { from: string; rate: number }[] = JSON.parse(d.rate_schedule || '[]')
        if (sched.length) {
          rate = sched[0].rate
          periods = sched.slice(1).map((s) => ({
            yearIndex: Math.round(monthsBetween(startDate, s.from) / 12) + 1,
            rate: s.rate,
          }))
        }
      } catch {}
      loaded = true
    })
  })

  function addPeriod() {
    const last = periods[periods.length - 1]
    periods = [...periods, { yearIndex: (last?.yearIndex ?? 1) + 1, rate: last?.rate ?? rate }]
  }
  function removePeriod(i: number) {
    periods = periods.filter((_, idx) => idx !== i)
  }

  function buildScheduleJson(): string {
    const sched = [{ from: startDate, rate }]
    for (const p of periods) {
      sched.push({ from: addMonthsISO(startDate, (p.yearIndex - 1) * 12), rate: p.rate })
    }
    return JSON.stringify(sched)
  }

  async function calculate() {
    saving = true
    await api.updateDeposit({
      rate,
      start_date: startDate,
      term_months: termMonths,
      initial_lump: initialLump,
      monthly_contribution: monthlyContribution,
      rate_schedule: buildScheduleJson(),
    })
    calc = await api.depositCalc()
    saving = false
    showToast('Рассчитано и сохранено')
  }

  function numFromInput(e: Event): number {
    return parseFloat((e.target as HTMLInputElement).value) || 0
  }
</script>

<div class="page-header"><h1>Вклад</h1></div>

{#if !loaded}
  <div class="spinner-wrap">Загрузка…</div>
{:else}
  <div class="page">
    <p class="muted hint">
      Это калькулятор-справка: считает капитализацию по вкладу, но не влияет на бюджет и 50/30/20.
    </p>

    <div class="card stack">
      <div class="field">
        <label for="lump">Первый взнос</label>
        <input id="lump" class="input num" inputmode="numeric" value={initialLump || ''} oninput={(e) => (initialLump = numFromInput(e))} />
      </div>
      <div class="field">
        <label for="sd">Дата открытия</label>
        <input id="sd" class="input" type="date" bind:value={startDate} />
      </div>
      <div class="field">
        <label for="term">Срок, месяцев</label>
        <input id="term" class="input num" inputmode="numeric" value={termMonths || ''} oninput={(e) => (termMonths = Math.round(numFromInput(e)))} />
      </div>
    </div>

    <div class="card stack">
      <div class="section-label">Процентная ставка по годам</div>
      <div class="rate-row">
        <span class="rate-label">Год 1</span>
        <input class="input num rate-input" inputmode="decimal" value={rate} oninput={(e) => (rate = numFromInput(e))} />
        <span class="pct">%</span>
      </div>
      {#each periods as p, i}
        <div class="rate-row">
          <span class="rate-label">Год {p.yearIndex}</span>
          <input class="input num rate-input" inputmode="decimal" value={p.rate} oninput={(e) => (p.rate = numFromInput(e))} />
          <span class="pct">%</span>
          <button class="del-x" onclick={() => removePeriod(i)} aria-label="Удалить период"><i class="ti ti-x"></i></button>
        </div>
      {/each}
      <button class="btn btn-ghost btn-sm" onclick={addPeriod}><i class="ti ti-plus"></i> Добавить период</button>
    </div>

    <div class="card stack">
      <div class="field">
        <label for="mc">Плановое пополнение в месяц</label>
        <input id="mc" class="input num" inputmode="numeric" value={monthlyContribution || ''} oninput={(e) => (monthlyContribution = numFromInput(e))} />
      </div>
      <button class="btn btn-primary" onclick={calculate} disabled={saving}>
        <i class="ti ti-calculator"></i> {saving ? 'Считаю…' : 'Рассчитать'}
      </button>
    </div>

    {#if calc}
      <div class="card stack">
        <div class="result num">Итог на дату закрытия: {money(calc.final_balance)} ₽</div>
        {#if calc.rows.length > 1}
          <Chart
            type="line"
            labels={calc.rows.map((r: any) => formatDate(r.date))}
            datasets={[{
              label: 'Баланс',
              data: calc.rows.map((r: any) => r.balance_after),
              borderColor: '#C9943A',
              backgroundColor: 'rgba(201,148,58,0.12)',
              tension: 0.3,
              fill: true,
              pointRadius: 0,
            }]}
            height={200}
          />
        {/if}
        <div class="rows">
          {#each calc.rows as r}
            <div class="row small">
              <span class="muted">{formatDate(r.date)}</span>
              <span class="num muted">+{money(r.contribution)}</span>
              <span class="num muted">%{money(r.interest)}</span>
              <span class="num">{money(r.balance_after)} ₽</span>
            </div>
          {/each}
        </div>
      </div>
    {/if}
  </div>
{/if}

<style>
  .hint { font-size: var(--text-sm); }
  .result { font-size: var(--text-xl); color: var(--gold); }
  .rows { display: flex; flex-direction: column; gap: 6px; max-height: 320px; overflow-y: auto; }
  .row.small { display: grid; grid-template-columns: 1fr auto auto auto; gap: var(--space-2); font-size: var(--text-sm); }
  .rate-row { display: flex; align-items: center; gap: var(--space-2); }
  .rate-label { flex: 1; font-size: var(--text-sm); }
  .rate-input { width: 90px; text-align: right; }
  .pct { color: var(--text-muted); font-size: var(--text-sm); }
  .del-x { background: none; border: none; color: var(--text-muted); padding: 0 0 0 4px; }
</style>
