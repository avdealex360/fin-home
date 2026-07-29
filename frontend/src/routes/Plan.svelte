<script lang="ts">
  import { api, type Category, type DebtSummary } from '../lib/api'
  import { period, dataVersion, invalidate, showToast, showHelp } from '../lib/stores'
  import { money } from '../lib/format'
  import ProgressBar from '../lib/components/ProgressBar.svelte'
  import Loader from '../lib/components/Loader.svelte'

  let plan = $state<any>(null)
  let categories = $state<Category[]>([])
  let debts = $state<DebtSummary[]>([])
  let income = $state(0)
  let limits = $state<Record<number, number>>({})
  let spent = $state<Record<number, number>>({})
  let saving = $state(false)
  let dirty = $state(false)
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
      api.plan(year, month), api.categories(), api.debts(), api.planMeter(year, month),
    ])
    plan = p
    categories = cats.filter((c) => c.group !== 'income')
    debts = ds
    income = p.expected_income
    meter = m
    const lm: Record<number, number> = {}
    const sp: Record<number, number> = {}
    for (const c of categories) {
      const l = p.limits?.find((x: any) => x.category_id === c.id)
      lm[c.id] = l ? l.limit_amount + (l.carried_over || 0) : 0
      sp[c.id] = l ? l.spent : 0
    }
    limits = lm
    spent = sp
    dirty = false
  }

  async function loadMeter() { meter = await api.planMeter($period.year, $period.month) }

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
    dirty = false
    invalidate()
    showToast('Лимиты сохранены')
  }

  async function addExpense() {
    if (!newExp.description || newExp.amount <= 0) return
    await api.addPlannedExpense(newExp, $period.year, $period.month)
    newExp = { description: '', amount: 0 }
    invalidate()
  }
  async function delExpense(id: number) { await api.deletePlannedExpense(id); invalidate() }
  async function addDebt() {
    if (!newDebt.debt_id || newDebt.amount <= 0) return
    await api.addPlannedDebt(newDebt, $period.year, $period.month)
    newDebt = { debt_id: 0, amount: 0 }
    invalidate()
  }
  async function delDebt(id: number) { await api.deletePlannedDebt(id); invalidate() }

  const groupLabel: Record<string, string> = { needs: 'Нужды', wants: 'Желания', savings: 'Сбережения' }
  const groupPct: Record<string, number> = { needs: 50, wants: 30, savings: 20 }

  function numFromInput(e: Event): number {
    return parseFloat((e.target as HTMLInputElement).value) || 0
  }

  let needsAllocated = $derived(
    categories.filter((c) => c.group === 'needs').reduce((s, c) => s + Number(limits[c.id] ?? 0), 0),
  )
  let wantsAllocated = $derived(
    categories.filter((c) => c.group === 'wants').reduce((s, c) => s + Number(limits[c.id] ?? 0), 0),
  )
  let savingsAllocated = $derived(meter['savings']?.allocated ?? 0)

  function meterAllocated(grp: string): number {
    if (grp === 'needs') return needsAllocated
    if (grp === 'wants') return wantsAllocated
    return savingsAllocated
  }
  function meterTarget(grp: string): number { return (income * (groupPct[grp] ?? 0)) / 100 }

  let allocatedTotal = $derived(needsAllocated + wantsAllocated + savingsAllocated)
  let unallocated = $derived(income - allocatedTotal)
  let plannedTotal = $derived(
    (plan?.planned_expenses ?? []).reduce((s: number, e: any) => s + e.amount, 0) +
    (plan?.planned_debt_payments ?? []).reduce((s: number, d: any) => s + d.amount, 0),
  )
</script>

{#if !plan}
  <Loader />
{:else}
  <div class="page">
    <div class="cols">
      <!-- Limits editor -->
      <section class="col-wide stack">
        <div class="card">
          <div class="row">
            <h2 class="card-title">Лимиты по категориям</h2>
          </div>
          {#if $showHelp}
            <p class="explain">
              Лимит — сколько вы разрешили себе потратить за месяц. Он же становится «планом»
              в аналитике и задаёт цвет шкал на Главной.
            </p>
          {/if}

          <div class="limits">
            <div class="lhead">
              <span>Категория</span><span class="r">Потрачено</span><span class="r">Лимит</span><span class="r">Остаток</span>
            </div>
            {#each ['needs', 'wants', 'savings'] as grp}
              {@const cats = categories.filter((c) => c.group === grp)}
              {#if cats.length}
                <div class="grp">
                  <span>{groupLabel[grp]}</span>
                  <span class="num dim">
                    {money(meterAllocated(grp))} / {money(meterTarget(grp))} ₽ · цель {groupPct[grp]}%
                  </span>
                </div>
                {#each cats as c}
                  {@const lim = Number(limits[c.id] ?? 0)}
                  {@const left = lim - (spent[c.id] ?? 0)}
                  <div class="lrow">
                    <span class="lname">
                      <i class="ti {c.icon}" style="color: {c.color}"></i>
                      <span>{c.name}</span>
                    </span>
                    <span class="num r dim">{money(spent[c.id] ?? 0)}</span>
                    <input
                      class="input num linput"
                      inputmode="numeric"
                      aria-label="Лимит: {c.name}"
                      value={limits[c.id] || ''}
                      oninput={(e) => { limits[c.id] = numFromInput(e); dirty = true }}
                    />
                    <span class="num r" style="color: var(--{left < 0 ? 'red' : left === 0 ? 'text-muted' : 'green'})">
                      {left < 0 ? '−' : ''}{money(Math.abs(left))}
                    </span>
                  </div>
                {/each}
              {/if}
            {/each}
          </div>

          <div class="save-bar" class:dirty>
            <span class="small {unallocated < 0 ? 'red' : 'muted'}">
              {unallocated >= 0
                ? `Не распределено ${money(unallocated)} ₽ из ${money(income)} ₽`
                : `Распределено больше дохода на ${money(-unallocated)} ₽`}
            </span>
            <button class="btn btn-primary btn-sm" onclick={saveLimits} disabled={!dirty}>
              {dirty ? 'Сохранить лимиты' : 'Всё сохранено'}
            </button>
          </div>
        </div>
      </section>

      <!-- Income + meters + planned -->
      <aside class="col stack">
        <div class="card">
          <h2 class="card-title">Ожидаемый доход</h2>
          {#if $showHelp}
            <p class="explain">От этой суммы считаются доли 50/30/20 и «идеальные» лимиты.</p>
          {/if}
          <input
            class="input num income-input"
            inputmode="numeric"
            aria-label="Ожидаемый доход"
            value={income || ''}
            oninput={(e) => (income = numFromInput(e))}
            onblur={saveIncome}
            disabled={saving}
          />
          <div class="stack meters">
            {#each ['needs', 'wants', 'savings'] as grp}
              {@const allocated = meterAllocated(grp)}
              {@const target = meterTarget(grp)}
              <div>
                <div class="row">
                  <span class="small">{groupLabel[grp]} <span class="dim tiny">цель {groupPct[grp]}%</span></span>
                  <span class="num tiny dim">{money(allocated)} / {money(target)} ₽</span>
                </div>
                <ProgressBar spent={allocated} limit={target} />
              </div>
            {/each}
          </div>
        </div>

        <div class="card">
          <div class="row">
            <h2 class="card-title">Крупные расходы</h2>
            {#if plannedTotal > 0}<span class="num tiny dim">всего {money(plannedTotal)} ₽</span>{/if}
          </div>
          {#if $showHelp}
            <p class="explain">Разовые траты, которые уже известны. Учитывайте их до того, как распределите доход.</p>
          {/if}
          <div class="stack" style="margin-top: 12px; gap: 10px">
            {#each plan.planned_expenses as e}
              <div class="row">
                <span class="small">{e.description}</span>
                <span class="num small">
                  {money(e.amount)} ₽
                  <button class="del-x" onclick={() => delExpense(e.id)} aria-label="Удалить"><i class="ti ti-x"></i></button>
                </span>
              </div>
            {/each}
          </div>
          <div class="add-row">
            <input class="input" placeholder="Описание" bind:value={newExp.description} />
            <input class="input num add-amt" inputmode="numeric" placeholder="₽" value={newExp.amount || ''} oninput={(e) => (newExp.amount = numFromInput(e))} />
            <button class="btn-add" onclick={addExpense} aria-label="Добавить"><i class="ti ti-plus"></i></button>
          </div>
        </div>

        {#if debts.length}
          <div class="card">
            <h2 class="card-title">Взносы по долгам</h2>
            <div class="stack" style="margin-top: 12px; gap: 10px">
              {#each plan.planned_debt_payments as p}
                <div class="row">
                  <span class="small">{p.debt_name}</span>
                  <span class="num small">
                    {money(p.amount)} ₽
                    <button class="del-x" onclick={() => delDebt(p.id)} aria-label="Удалить"><i class="ti ti-x"></i></button>
                  </span>
                </div>
              {/each}
            </div>
            <div class="add-row">
              <select class="input" bind:value={newDebt.debt_id} aria-label="Долг">
                <option value={0}>Долг…</option>
                {#each debts as d}<option value={d.id}>{d.name}</option>{/each}
              </select>
              <input class="input num add-amt" inputmode="numeric" placeholder="₽" value={newDebt.amount || ''} oninput={(e) => (newDebt.amount = numFromInput(e))} />
              <button class="btn-add" onclick={addDebt} aria-label="Добавить"><i class="ti ti-plus"></i></button>
            </div>
          </div>
        {/if}
      </aside>
    </div>
  </div>
{/if}

<style>
  .limits { margin-top: var(--space-4); }
  .lhead, .lrow {
    display: grid;
    grid-template-columns: minmax(0, 1.6fr) 96px 118px 96px;
    gap: var(--space-3);
    align-items: center;
  }
  .lhead {
    padding-bottom: 8px;
    font-size: 11px; font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase;
    color: var(--text-muted);
  }
  .lrow { padding: 7px 0; border-top: 1px solid var(--line); }
  .lname { display: flex; align-items: center; gap: 9px; min-width: 0; font-size: 13.5px; }
  .lname i { font-size: 18px; flex-shrink: 0; }
  .lname span { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .linput { text-align: right; padding: 9px 10px; font-size: 13px; }
  .r { text-align: right; font-size: 13px; }

  .grp {
    display: flex; justify-content: space-between; align-items: baseline; gap: 10px;
    margin-top: var(--space-4); padding-bottom: 6px;
    font-size: var(--text-sm); font-weight: 600; color: var(--blue);
  }
  .grp .num { font-size: 11.5px; font-weight: 400; }

  .save-bar {
    position: sticky; bottom: 0;
    display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); flex-wrap: wrap;
    margin: var(--space-4) calc(-1 * var(--space-5)) calc(-1 * var(--space-5));
    padding: var(--space-3) var(--space-5);
    background: rgba(21, 25, 34, 0.94);
    backdrop-filter: blur(10px);
    border-top: 1px solid var(--line);
    border-radius: 0 0 var(--radius-lg) var(--radius-lg);
  }

  .income-input { margin-top: var(--space-3); font-size: var(--text-xl); text-align: right; padding: 12px 14px; }
  .meters { margin-top: var(--space-4); gap: var(--space-3); }

  .add-row { display: flex; gap: var(--space-2); align-items: center; margin-top: var(--space-3); }
  .add-row .input { flex: 1; min-width: 0; }
  .add-amt { flex: 0 0 88px; text-align: right; }
  .btn-add {
    background: var(--blue); color: #0b1220; border: none; border-radius: var(--radius-sm);
    width: 44px; height: 44px; flex-shrink: 0; display: grid; place-items: center;
  }
  .del-x { background: none; border: none; color: var(--text-muted); padding: 0 0 0 8px; }
  .del-x:hover { color: var(--red); }

  .small { font-size: var(--text-sm); }
  .tiny { font-size: var(--text-xs); }
  .red { color: var(--red); }
</style>
