<script lang="ts">
  import { api, type GoalSummary, type FundSummary, type DebtSummary } from '../lib/api'
  import { dataVersion, invalidate, showToast } from '../lib/stores'
  import { money } from '../lib/format'
  import ProgressBar from '../lib/components/ProgressBar.svelte'

  let goals = $state<GoalSummary[]>([])
  let funds = $state<FundSummary[]>([])
  let debts = $state<DebtSummary[]>([])
  let settings = $state<Record<string, string>>({})

  // Which item has its action panel open: `${kind}:${id}` and the mode.
  let openPanel = $state<string | null>(null)
  let panelMode = $state<'contribute' | 'edit'>('contribute')
  let amount = $state(0)
  let edit = $state<any>({})

  let adding = $state<'goal' | 'fund' | 'debt' | null>(null)
  let nf = $state({ name: '', target_amount: 0, monthly_contribution: 0 })

  $effect(() => {
    void $dataVersion
    reload()
  })
  async function reload() {
    ;[goals, funds, debts, settings] = await Promise.all([
      api.goals(), api.funds(), api.debts(), api.settings(),
    ])
  }

  function toggle(kind: string, id: number, mode: 'contribute' | 'edit', item?: any) {
    const key = `${kind}:${id}`
    if (openPanel === key && panelMode === mode) {
      openPanel = null
      return
    }
    openPanel = key
    panelMode = mode
    amount = 0
    if (mode === 'edit' && item) edit = { ...item }
  }
  const isOpen = (kind: string, id: number, mode: string) =>
    openPanel === `${kind}:${id}` && panelMode === mode

  async function contributeGoal(id: number) {
    await api.goalContribute(id, { amount }); done('Пополнено')
  }
  async function contributeFund(id: number) {
    await api.fundContribute(id, { amount }); done('Пополнено')
  }
  async function payDebt(id: number) {
    await api.debtPayment(id, { amount }); done('Платёж записан')
  }
  async function saveGoalEdit(id: number) {
    await api.updateGoal(id, { name: edit.name, target_amount: edit.target_amount, monthly_contribution: edit.monthly_contribution, deadline: edit.deadline || null }); done('Сохранено')
  }
  async function saveFundEdit(id: number) {
    await api.updateFund(id, { name: edit.name, target_amount: edit.target_amount, monthly_contribution: edit.monthly_contribution, is_rolling: edit.is_rolling }); done('Сохранено')
  }
  async function saveDebtEdit(id: number) {
    await api.updateDebt(id, { name: edit.name, total_amount: edit.total_amount, remaining: edit.remaining, interest_rate: edit.interest_rate, monthly_payment: edit.monthly_payment, type: edit.type }); done('Сохранено')
  }
  function done(msg: string) {
    openPanel = null
    invalidate()
    showToast(msg)
  }

  async function createItem() {
    if (!nf.name) return
    if (adding === 'goal') await api.createGoal({ name: nf.name, target_amount: nf.target_amount, monthly_contribution: nf.monthly_contribution })
    if (adding === 'fund') await api.createFund({ name: nf.name, target_amount: nf.target_amount, monthly_contribution: nf.monthly_contribution })
    if (adding === 'debt') await api.createDebt({ name: nf.name, total_amount: nf.target_amount, type: 'loan' })
    nf = { name: '', target_amount: 0, monthly_contribution: 0 }
    adding = null
    invalidate()
    showToast('Создано')
  }

  async function delGoal(g: GoalSummary) { if (confirm(`Удалить цель «${g.name}»?`)) { await api.deleteGoal(g.id); invalidate() } }
  async function delFund(f: FundSummary) { if (confirm(`Удалить копилку «${f.name}»?`)) { await api.deleteFund(f.id); invalidate() } }
  async function delDebt(d: DebtSummary) { if (confirm(`Удалить долг «${d.name}»?`)) { await api.deleteDebt(d.id); invalidate() } }

  async function saveNames() {
    await api.saveSettings({ user1_name: settings.user1_name, user2_name: settings.user2_name, eur_rub_rate: settings.eur_rub_rate })
    showToast('Сохранено')
  }
</script>

<div class="page-header"><h1>Ещё</h1></div>

<div class="page">
  <!-- Goals -->
  <section>
    <div class="row section-label"><span>Цели</span>
      <button class="btn-ghost btn-sm" onclick={() => (adding = adding === 'goal' ? null : 'goal')} aria-label="Добавить цель"><i class="ti ti-plus"></i></button>
    </div>
    <div class="stack">
      {#each goals as g}
        <div class="card">
          <div class="row"><strong>{g.name}</strong><span class="num">{money(g.current_amount)} / {money(g.target_amount)}</span></div>
          <ProgressBar spent={g.current_amount} limit={g.target_amount} color="green" />
          {#if g.months_to_goal}<div class="muted small">≈ {g.months_to_goal} мес. до цели</div>{/if}
          <div class="actions">
            <button class="btn-ghost btn-sm" onclick={() => toggle('goal', g.id, 'contribute')}>Пополнить</button>
            <button class="btn-ghost btn-sm" onclick={() => toggle('goal', g.id, 'edit', g)}>Изменить</button>
            <button class="btn-ghost btn-sm danger" onclick={() => delGoal(g)}>Удалить</button>
          </div>
          {#if isOpen('goal', g.id, 'contribute')}
            <div class="panel">
              <input class="input num" inputmode="numeric" placeholder="Сумма" bind:value={amount} />
              <button class="btn btn-primary" onclick={() => contributeGoal(g.id)}>Пополнить</button>
            </div>
          {/if}
          {#if isOpen('goal', g.id, 'edit')}
            <div class="panel">
              <input class="input" bind:value={edit.name} />
              <input class="input num" inputmode="numeric" placeholder="Цель" bind:value={edit.target_amount} />
              <input class="input num" inputmode="numeric" placeholder="Взнос/мес" bind:value={edit.monthly_contribution} />
              <input class="input" type="date" bind:value={edit.deadline} />
              <button class="btn btn-primary" onclick={() => saveGoalEdit(g.id)}>Сохранить</button>
            </div>
          {/if}
        </div>
      {/each}
    </div>
  </section>

  <!-- Funds -->
  <section>
    <div class="row section-label"><span>Копилки</span>
      <button class="btn-ghost btn-sm" onclick={() => (adding = adding === 'fund' ? null : 'fund')} aria-label="Добавить копилку"><i class="ti ti-plus"></i></button>
    </div>
    <div class="stack">
      {#each funds as f}
        <div class="card">
          <div class="row"><strong>{f.name}</strong><span class="num">{money(f.current_amount)} / {money(f.target_amount)}</span></div>
          <ProgressBar spent={f.current_amount} limit={f.target_amount} color="green" />
          <div class="actions">
            <button class="btn-ghost btn-sm" onclick={() => toggle('fund', f.id, 'contribute')}>Пополнить</button>
            <button class="btn-ghost btn-sm" onclick={() => toggle('fund', f.id, 'edit', f)}>Изменить</button>
            <button class="btn-ghost btn-sm danger" onclick={() => delFund(f)}>Удалить</button>
          </div>
          {#if isOpen('fund', f.id, 'contribute')}
            <div class="panel">
              <input class="input num" inputmode="numeric" placeholder="Сумма" bind:value={amount} />
              <button class="btn btn-primary" onclick={() => contributeFund(f.id)}>Пополнить</button>
            </div>
          {/if}
          {#if isOpen('fund', f.id, 'edit')}
            <div class="panel">
              <input class="input" bind:value={edit.name} />
              <input class="input num" inputmode="numeric" placeholder="Цель" bind:value={edit.target_amount} />
              <input class="input num" inputmode="numeric" placeholder="Взнос/мес" bind:value={edit.monthly_contribution} />
              <label class="check"><input type="checkbox" bind:checked={edit.is_rolling} /> Возобновляемая</label>
              <button class="btn btn-primary" onclick={() => saveFundEdit(f.id)}>Сохранить</button>
            </div>
          {/if}
        </div>
      {/each}
    </div>
  </section>

  <!-- Debts -->
  <section>
    <div class="row section-label"><span>Долги</span>
      <button class="btn-ghost btn-sm" onclick={() => (adding = adding === 'debt' ? null : 'debt')} aria-label="Добавить долг"><i class="ti ti-plus"></i></button>
    </div>
    <div class="stack">
      {#each debts as d}
        <div class="card">
          <div class="row"><strong>{d.name}</strong><span class="num">{money(d.remaining)} ₽</span></div>
          <div class="muted small">{d.interest_rate > 0 ? `${d.interest_rate}%` : 'Без %'}{d.priority_label ? ` · ${d.priority_label}` : ''}</div>
          <div class="actions">
            <button class="btn-ghost btn-sm" onclick={() => toggle('debt', d.id, 'contribute')}>Платёж</button>
            <button class="btn-ghost btn-sm" onclick={() => toggle('debt', d.id, 'edit', d)}>Изменить</button>
            <button class="btn-ghost btn-sm danger" onclick={() => delDebt(d)}>Удалить</button>
          </div>
          {#if isOpen('debt', d.id, 'contribute')}
            <div class="panel">
              <input class="input num" inputmode="numeric" placeholder="Сумма платежа" bind:value={amount} />
              <button class="btn btn-primary" onclick={() => payDebt(d.id)}>Записать платёж</button>
            </div>
          {/if}
          {#if isOpen('debt', d.id, 'edit')}
            <div class="panel">
              <input class="input" bind:value={edit.name} />
              <input class="input num" inputmode="numeric" placeholder="Всего" bind:value={edit.total_amount} />
              <input class="input num" inputmode="numeric" placeholder="Остаток" bind:value={edit.remaining} />
              <input class="input num" inputmode="decimal" placeholder="Ставка %" bind:value={edit.interest_rate} />
              <input class="input num" inputmode="numeric" placeholder="Платёж/мес" bind:value={edit.monthly_payment} />
              <button class="btn btn-primary" onclick={() => saveDebtEdit(d.id)}>Сохранить</button>
            </div>
          {/if}
        </div>
      {/each}
    </div>
  </section>

  {#if adding}
    <div class="card stack">
      <div class="section-label">Новое: {adding === 'goal' ? 'цель' : adding === 'fund' ? 'копилка' : 'долг'}</div>
      <input class="input" placeholder="Название" bind:value={nf.name} />
      <input class="input num" inputmode="numeric" placeholder={adding === 'debt' ? 'Сумма долга' : 'Целевая сумма'} bind:value={nf.target_amount} />
      {#if adding !== 'debt'}
        <input class="input num" inputmode="numeric" placeholder="Взнос/мес" bind:value={nf.monthly_contribution} />
      {/if}
      <button class="btn btn-primary" onclick={createItem}>Создать</button>
    </div>
  {/if}

  <!-- Settings -->
  <section>
    <div class="section-label">Настройки</div>
    <div class="card stack">
      <div class="field"><label for="u1">Имя 1</label><input id="u1" class="input" bind:value={settings.user1_name} /></div>
      <div class="field"><label for="u2">Имя 2</label><input id="u2" class="input" bind:value={settings.user2_name} /></div>
      <div class="field"><label for="er">Курс EUR/RUB</label><input id="er" class="input num" bind:value={settings.eur_rub_rate} /></div>
      <button class="btn btn-secondary" onclick={saveNames}>Сохранить</button>
      <a class="btn btn-ghost" href="/api/settings/export/json">Экспорт JSON</a>
      <a class="btn btn-ghost" href="/api/settings/export/csv">Экспорт CSV</a>
    </div>
  </section>
</div>

<style>
  section { display: flex; flex-direction: column; gap: var(--space-2); }
  .actions { display: flex; gap: var(--space-2); margin-top: var(--space-2); flex-wrap: wrap; }
  .danger { color: var(--red); }
  .btn-ghost.btn { width: 100%; }
  .small { font-size: var(--text-xs); margin-top: 4px; }
  .panel { display: flex; flex-direction: column; gap: var(--space-2); margin-top: var(--space-3); padding-top: var(--space-3); border-top: 1px solid rgba(255,255,255,0.06); }
  .check { display: flex; align-items: center; gap: 8px; font-size: var(--text-sm); color: var(--text-secondary); }
</style>
