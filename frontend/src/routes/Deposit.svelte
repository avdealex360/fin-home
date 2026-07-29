<script lang="ts">
  import { api } from '../lib/api'
  import { showToast, showHelp } from '../lib/stores'
  import { money, formatDate } from '../lib/format'
  import Chart from '../lib/components/Chart.svelte'
  import Loader from '../lib/components/Loader.svelte'

  interface Period { yearIndex: number; rate: number }

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
  function removePeriod(i: number) { periods = periods.filter((_, idx) => idx !== i) }

  function buildScheduleJson(): string {
    const sched = [{ from: startDate, rate }]
    for (const p of periods) sched.push({ from: addMonthsISO(startDate, (p.yearIndex - 1) * 12), rate: p.rate })
    return JSON.stringify(sched)
  }

  async function calculate() {
    saving = true
    await api.updateDeposit({
      rate, start_date: startDate, term_months: termMonths,
      initial_lump: initialLump, monthly_contribution: monthlyContribution,
      rate_schedule: buildScheduleJson(),
    })
    calc = await api.depositCalc()
    saving = false
    showToast('Рассчитано и сохранено')
  }

  function numFromInput(e: Event): number {
    return parseFloat((e.target as HTMLInputElement).value) || 0
  }

  let contributed = $derived(initialLump + monthlyContribution * termMonths)
  let interest = $derived(calc ? calc.final_balance - contributed : 0)
</script>

{#if !loaded}
  <Loader />
{:else}
  <div class="page">
    <div class="cols">
      <!-- Parameters -->
      <aside class="col stack">
        <div class="card">
          <h2 class="card-title">Параметры вклада</h2>
          {#if $showHelp}
            <p class="explain">
              Это калькулятор-справка: считает капитализацию по вкладу, но не влияет
              на бюджет месяца и на 50/30/20.
            </p>
          {/if}
          <div class="stack" style="margin-top: 14px">
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
            <div class="field">
              <label for="mc">Пополнение в месяц</label>
              <input id="mc" class="input num" inputmode="numeric" value={monthlyContribution || ''} oninput={(e) => (monthlyContribution = numFromInput(e))} />
            </div>
          </div>
        </div>

        <div class="card">
          <h2 class="card-title">Ставка по годам</h2>
          {#if $showHelp}
            <p class="explain">Если банк меняет ставку после первого года — добавьте период.</p>
          {/if}
          <div class="stack" style="margin-top: 12px; gap: 10px">
            <div class="rate-row">
              <span class="rate-label">Год 1</span>
              <input class="input num rate-input" inputmode="decimal" aria-label="Ставка, год 1" value={rate} oninput={(e) => (rate = numFromInput(e))} />
              <span class="pct">%</span>
            </div>
            {#each periods as p, i}
              <div class="rate-row">
                <span class="rate-label">Год {p.yearIndex}</span>
                <input class="input num rate-input" inputmode="decimal" aria-label="Ставка, год {p.yearIndex}" value={p.rate} oninput={(e) => (p.rate = numFromInput(e))} />
                <span class="pct">%</span>
                <button class="del-x" onclick={() => removePeriod(i)} aria-label="Удалить период"><i class="ti ti-x"></i></button>
              </div>
            {/each}
          </div>
          <button class="btn btn-ghost btn-sm" style="margin-top: 12px" onclick={addPeriod}>
            <i class="ti ti-plus"></i> Добавить период
          </button>
        </div>

        <button class="btn btn-primary" onclick={calculate} disabled={saving}>
          <i class="ti ti-calculator"></i> {saving ? 'Считаю…' : 'Рассчитать'}
        </button>
      </aside>

      <!-- Result -->
      <section class="col-wide stack">
        {#if !calc}
          <div class="card empty">
            <i class="ti ti-chart-line"></i>
            <div>
              <div class="empty-title">Результат появится здесь</div>
              <div class="muted small">Заполните параметры слева и нажмите «Рассчитать».</div>
            </div>
          </div>
        {:else}
          <div class="card hero">
            <span class="section-label">Итог на дату закрытия</span>
            <div class="num hero-amount">{money(calc.final_balance)} ₽</div>
            {#if $showHelp}
              <p class="explain">Сколько будет на вкладе в конце срока: ваши взносы плюс начисленные проценты.</p>
            {/if}
            <div class="split">
              <div>
                <div class="k">Вы внесёте</div>
                <div class="num v">{money(contributed)} ₽</div>
              </div>
              <div>
                <div class="k">Начислят процентами</div>
                <div class="num v gold">+ {money(interest)} ₽</div>
              </div>
              <div>
                <div class="k">Доходность за срок</div>
                <div class="num v green">{contributed > 0 ? ((interest / contributed) * 100).toFixed(1) : 0}%</div>
              </div>
            </div>
          </div>

          {#if calc.rows.length > 1}
            <div class="card">
              <h2 class="card-title">Как растёт баланс</h2>
              <div style="margin-top: 12px">
                <Chart
                  type="line"
                  labels={calc.rows.map((r: any) => formatDate(r.date))}
                  datasets={[{
                    label: 'Баланс',
                    data: calc.rows.map((r: any) => r.balance_after),
                    borderColor: '#d8a24a',
                    backgroundColor: 'rgba(216,162,74,0.14)',
                    tension: 0.3, fill: true, pointRadius: 0,
                  }]}
                  height={240}
                />
              </div>
            </div>
          {/if}

          <div class="card">
            <h2 class="card-title">По месяцам</h2>
            <div class="table-scroll">
              <div class="table">
                <div class="thead">
                  <span>Дата</span><span class="r">Пополнение</span><span class="r">Проценты</span><span class="r">Баланс</span>
                </div>
                {#each calc.rows as r}
                  <div class="trow">
                    <span class="dim">{formatDate(r.date)}</span>
                    <span class="num r dim">+ {money(r.contribution)}</span>
                    <span class="num r gold">+ {money(r.interest)}</span>
                    <span class="num r">{money(r.balance_after)} ₽</span>
                  </div>
                {/each}
              </div>
            </div>
          </div>
        {/if}
      </section>
    </div>
  </div>
{/if}

<style>
  .hero {
    background: linear-gradient(155deg, #2a2010 0%, var(--bg-surface) 62%);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: var(--radius-xl);
  }
  .hero-amount { font-size: clamp(34px, 4vw, 46px); font-weight: 600; letter-spacing: -0.02em; margin: 8px 0 2px; }
  .split { display: flex; flex-wrap: wrap; gap: var(--space-4); margin-top: var(--space-5); padding-top: var(--space-4); border-top: 1px solid rgba(255, 255, 255, 0.07); }
  .split > div { flex: 1 1 150px; }
  .k { font-size: 11.5px; color: var(--text-secondary); }
  .v { font-size: 19px; font-weight: 600; margin-top: 2px; }
  .gold { color: var(--gold); }
  .green { color: var(--green); }

  .rate-row { display: flex; align-items: center; gap: var(--space-2); }
  .rate-label { flex: 1; font-size: var(--text-sm); }
  .rate-input { width: 96px; text-align: right; padding: 9px 10px; }
  .pct { color: var(--text-muted); font-size: var(--text-sm); }
  .del-x { background: none; border: none; color: var(--text-muted); padding: 0 0 0 4px; }
  .del-x:hover { color: var(--red); }

  .table-scroll { overflow-x: auto; margin-top: var(--space-3); max-height: 420px; overflow-y: auto; }
  .table { min-width: 440px; }
  .thead, .trow { display: grid; grid-template-columns: minmax(0, 1.2fr) 110px 110px 120px; gap: var(--space-3); align-items: center; }
  .thead {
    position: sticky; top: 0; background: var(--bg-surface); padding: 6px 0 8px;
    font-size: 11px; font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase; color: var(--text-muted);
  }
  .trow { padding: 8px 0; border-top: 1px solid var(--line); font-size: 13px; }
  .r { text-align: right; }

  .empty { display: flex; align-items: center; gap: var(--space-4); }
  .empty i { font-size: 28px; color: var(--text-muted); }
  .empty-title { font-size: 14px; font-weight: 600; }
  .small { font-size: var(--text-sm); }
</style>
