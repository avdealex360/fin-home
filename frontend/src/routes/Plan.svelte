<script lang="ts">
  import { api, type Category, type DebtSummary } from '../lib/api'
  import { period, dataVersion, invalidate, showToast } from '../lib/stores'
  import { money, monthName, shiftMonth } from '../lib/format'
  import ProgressBar from '../lib/components/ProgressBar.svelte'
  import Loader from '../lib/components/Loader.svelte'

  let plan = $state<any>(null)
  let categories = $state<Category[]>([])
  let debts = $state<DebtSummary[]>([])
  let income = $state(0)
  let limits = $state<Record<number, number>>({})
  let saving = $state(false)
  let meter = $state<Record<string, { allocated: number; target: number }>>({})

  let newExp = $state({ description: '', amount: 0 })
  let newDebt = $state({ debt_id: 0, amount: 0 })

  $effect(() => {
    const { year, month } = $period
    void $dataVersion
    load(year, month)
  })

  async function load(year: number, month: number) {
    const [p, cats, ds, m] = await Promise.all([
      api.plan(year, month),
      api.categories(),
      api.debts(),
      api.planMeter(year, month),
    ])
    plan = p
    categories = cats.filter((c) => c.group !== 'income')
    debts = ds
    income = p.expected_income
    meter = m
    const lm: Record<number, number> = {}
    for (const c of categories) {
      const l = p.limits?.find((x: any) => x.category_id === c.id)
      lm[c.id] = l ? l.limit_amount + (l.carried_over || 0) : 0
    }
    limits = lm
  }

  async function loadMeter() {
    meter = await api.planMeter($period.year, $period.month)
  }

  function changeMonth(delta: number) {
    const [y, m] = shiftMonth($period.year, $period.month, delta)
    period.set({ year: y, month: m })
  }

  async function saveIncome() {
    if (income === plan.expected_income) return
    saving = true
    await api.savePlan({ expected_income: income }, $period.year, $period.month)
    saving = false
    plan.expected_income = income
    invalidate()
    await loadMeter()
    showToast('Доход сохранён')
  }

  async function saveLimits() {
    await api.saveLimits(limits, $period.year, $period.month)
    invalidate()
    showToast('Лимиты сохранены')
  }

  async function addExpense() {
    if (!newExp.description || newExp.amount <= 0) return
    await api.addPlannedExpense(newExp, $period.year, $period.month)
    newExp = { description: '', amount: 0 }
    invalidate()
  }
  async function delExpense(id: number) {
    await api.deletePlannedExpense(id)
    invalidate()
  }
  async function addDebt() {
    if (!newDebt.debt_id || newDebt.amount <= 0) return
    await api.addPlannedDebt(newDebt, $period.year, $period.month)
    newDebt = { debt_id: 0, amount: 0 }
    invalidate()
  }
  async function delDebt(id: number) {
    await api.deletePlannedDebt(id)
    invalidate()
  }

  let closing = $state(false)

  async function closeMonth() {
    const msg =
      `Закрыть ${monthName($period.month)} ${$period.year}?\n\n` +
      'Неизрасходованный остаток по каждому лимиту (лимит минус траты) ' +
      'прибавится к лимиту той же категории в следующем месяце — так неистраченные ' +
      'деньги не «сгорают». Действие необратимо.'
    if (!confirm(msg)) return
    closing = true
    try {
      await api.closeMonth($period.year, $period.month)
      invalidate()
      await load($period.year, $period.month)
      showToast('Месяц закрыт, остатки перенесены на следующий')
    } catch (e) {
      showToast((e as Error).message || 'Не удалось закрыть месяц')
    } finally {
      closing = false
    }
  }

  const groupLabel: Record<string, string> = { needs: 'Нужды', wants: 'Желания', savings: 'Сбережения' }
  const groupPct: Record<string, number> = { needs: 50, wants: 30, savings: 20 }

  function numFromInput(e: Event): number {
    return parseFloat((e.target as HTMLInputElement).value) || 0
  }

  // Live-derived allocated sums for needs/wants (editable on this screen)
  let needsAllocated = $derived(
    categories.filter((c) => c.group === 'needs').reduce((s, c) => s + Number(limits[c.id] ?? 0), 0),
  )
  let wantsAllocated = $derived(
    categories.filter((c) => c.group === 'wants').reduce((s, c) => s + Number(limits[c.id] ?? 0), 0),
  )
  // savings allocated comes from meter (includes funds + deposit target)
  let savingsAllocated = $derived(meter['savings']?.allocated ?? 0)

  function meterAllocated(grp: string): number {
    if (grp === 'needs') return needsAllocated
    if (grp === 'wants') return wantsAllocated
    return savingsAllocated
  }
  function meterTarget(grp: string): number {
    return income * (groupPct[grp] ?? 0) / 100
  }
</script>

<div class="page-header">
  <button class="btn-ghost btn-sm" onclick={() => changeMonth(-1)} aria-label="Прошлый месяц"><i class="ti ti-chevron-left"></i></button>
  <h1>{monthName($period.month)} {$period.year}</h1>
  <button class="btn-ghost btn-sm" onclick={() => changeMonth(1)} aria-label="Следующий месяц"><i class="ti ti-chevron-right"></i></button>
</div>

{#if !plan}
  <Loader />
{:else}
  <div class="page">
    <div class="card field">
      <label for="inc">Ожидаемый доход</label>
      <input
        id="inc"
        class="input num"
        inputmode="numeric"
        value={income || ''}
        oninput={(e) => (income = numFromInput(e))}
        onblur={saveIncome}
        disabled={saving}
      />
    </div>

    <div class="card stack meter-card">
      {#each ['needs', 'wants', 'savings'] as grp}
        {@const allocated = meterAllocated(grp)}
        {@const target = meterTarget(grp)}
        <div class="meter-row">
          <div class="meter-labels">
            <span class="meter-name">{groupLabel[grp]}</span>
            <span class="meter-nums"><span class="num">{money(allocated)}</span> / <span class="num">{money(target)}</span> ₽</span>
          </div>
          <ProgressBar spent={allocated} limit={target} />
        </div>
      {/each}
    </div>

    <div>
      <div class="section-label">Лимиты по категориям</div>
      <div class="card stack">
        {#each ['needs', 'wants', 'savings'] as grp}
          {@const cats = categories.filter((c) => c.group === grp)}
          {#if cats.length}
            <div class="grp">{groupLabel[grp]}</div>
            {#each cats as c}
              <div class="limit-row">
                <span class="limit-name"><i class="ti {c.icon}" style="color:{c.color}"></i> {c.name}</span>
                <input
                  class="input num limit-input"
                  inputmode="numeric"
                  value={limits[c.id] || ''}
                  oninput={(e) => (limits[c.id] = numFromInput(e))}
                />
              </div>
            {/each}
          {/if}
        {/each}
        <button class="btn btn-secondary" onclick={saveLimits}>Сохранить лимиты</button>
      </div>
    </div>

    <div>
      <div class="section-label">Плановые крупные расходы</div>
      <div class="card stack">
        {#each plan.planned_expenses as e}
          <div class="limit-row">
            <span>{e.description}</span>
            <span class="num">{money(e.amount)} ₽
              <button class="del-x" onclick={() => delExpense(e.id)} aria-label="Удалить"><i class="ti ti-x"></i></button>
            </span>
          </div>
        {/each}
        <div class="add-row">
          <input class="input" placeholder="Описание" bind:value={newExp.description} />
          <input
            class="input num add-amt"
            inputmode="numeric"
            placeholder="₽"
            value={newExp.amount || ''}
            oninput={(e) => (newExp.amount = numFromInput(e))}
          />
          <button class="btn-add" onclick={addExpense} aria-label="Добавить"><i class="ti ti-plus"></i></button>
        </div>
      </div>
    </div>

    {#if debts.length}
      <div>
        <div class="section-label">Плановые взносы по долгам</div>
        <div class="card stack">
          {#each plan.planned_debt_payments as p}
            <div class="limit-row">
              <span>{p.debt_name}</span>
              <span class="num">{money(p.amount)} ₽
                <button class="del-x" onclick={() => delDebt(p.id)} aria-label="Удалить"><i class="ti ti-x"></i></button>
              </span>
            </div>
          {/each}
          <div class="add-row">
            <select class="input" bind:value={newDebt.debt_id}>
              <option value={0}>Долг…</option>
              {#each debts as d}<option value={d.id}>{d.name}</option>{/each}
            </select>
            <input
              class="input num add-amt"
              inputmode="numeric"
              placeholder="₽"
              value={newDebt.amount || ''}
              oninput={(e) => (newDebt.amount = numFromInput(e))}
            />
            <button class="btn-add" onclick={addDebt} aria-label="Добавить"><i class="ti ti-plus"></i></button>
          </div>
        </div>
      </div>
    {/if}

    {#if !plan.is_closed}
      <div class="close-block">
        <button class="btn btn-secondary" onclick={closeMonth} disabled={closing}>
          <i class="ti ti-lock"></i> {closing ? 'Закрываю…' : 'Закрыть месяц'}
        </button>
        <p class="muted close-hint">
          Неизрасходованные остатки лимитов перенесутся на следующий месяц. Действие необратимо.
        </p>
      </div>
    {:else}
      <p class="muted"><i class="ti ti-lock"></i> Месяц закрыт, остатки перенесены на следующий.</p>
    {/if}
  </div>
{/if}

<style>
  .grp { font-size: var(--text-sm); color: var(--blue); font-weight: 600; margin-top: var(--space-2); }
  .limit-row { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); }
  .limit-name { font-size: var(--text-sm); display: flex; align-items: center; gap: 6px; }
  .limit-name i { font-size: 18px; flex-shrink: 0; line-height: 1; }
  .limit-input { width: 110px; text-align: right; }
  .add-row { display: flex; gap: var(--space-2); align-items: center; margin-top: var(--space-2); }
  .add-row .input { flex: 1; }
  .add-amt { flex: 0 0 90px; text-align: right; }
  .btn-add { background: var(--blue); color: #fff; border: none; border-radius: var(--radius-sm); width: 44px; height: 44px; flex-shrink: 0; }
  .del-x { background: none; border: none; color: var(--text-muted); padding: 0 0 0 8px; }

  .meter-card { gap: var(--space-3); }
  .meter-row { display: flex; flex-direction: column; gap: var(--space-1); }
  .meter-labels { display: flex; justify-content: space-between; align-items: baseline; }
  .meter-name { font-size: var(--text-sm); font-weight: 600; color: var(--text); }
  .meter-nums { font-size: var(--text-xs); color: var(--text-muted); }
  .close-block { display: flex; flex-direction: column; gap: var(--space-2); }
  .close-hint { font-size: var(--text-xs); text-align: center; margin: 0; }
</style>
