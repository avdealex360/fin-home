<script lang="ts">
  import { api, type FundSummary, type DebtSummary, type User } from '../lib/api'
  import { authenticated, dataVersion, invalidate, showToast } from '../lib/stores'
  import { money } from '../lib/format'
  import ProgressBar from '../lib/components/ProgressBar.svelte'

  let funds = $state<FundSummary[]>([])
  let debts = $state<DebtSummary[]>([])
  let users = $state<User[]>([])
  let newUserName = $state('')
  let editingUserId = $state<number | null>(null)
  let editingUserName = $state('')

  // Which item has its action panel open: `${kind}:${id}` and the mode.
  let openPanel = $state<string | null>(null)
  let panelMode = $state<'contribute' | 'spend' | 'edit'>('contribute')
  let amount = $state(0)
  let edit = $state<any>({})

  let adding = $state<'fund' | 'debt' | null>(null)
  let nf = $state({ name: '', target_amount: 0, monthly_contribution: 0, group: 'wants' as 'wants' | 'savings', target_date: '', is_rolling: false })

  $effect(() => {
    void $dataVersion
    reload()
  })
  async function reload() {
    ;[funds, debts, users] = await Promise.all([
      api.funds(), api.debts(), api.users(),
    ])
  }

  async function addUser() {
    if (!newUserName.trim()) return
    await api.createUser(newUserName.trim())
    newUserName = ''
    invalidate()
  }
  function startEditUser(u: User) {
    editingUserId = u.id
    editingUserName = u.name
  }
  async function saveUserEdit() {
    if (editingUserId == null || !editingUserName.trim()) return
    await api.updateUser(editingUserId, editingUserName.trim())
    editingUserId = null
    invalidate()
  }
  async function removeUser(u: User) {
    if (!confirm(`Удалить участника «${u.name}»?`)) return
    await api.deleteUser(u.id)
    invalidate()
  }

  function toggle(kind: string, id: number, mode: 'contribute' | 'spend' | 'edit', item?: any) {
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

  async function contributeFund(id: number) {
    await api.fundContribute(id, { amount }); done('Пополнено')
  }
  async function spendFund(id: number) {
    await api.fundSpend(id, { amount }); done('Потрачено')
  }
  async function payDebt(id: number) {
    await api.debtPayment(id, { amount }); done('Платёж записан')
  }
  async function saveFundEdit(id: number) {
    await api.updateFund(id, { name: edit.name, target_amount: edit.target_amount, monthly_contribution: edit.monthly_contribution, target_date: edit.target_date || null, is_rolling: edit.is_rolling, group: edit.group }); done('Сохранено')
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
    if (adding === 'fund') await api.createFund({ name: nf.name, target_amount: nf.target_amount, monthly_contribution: nf.monthly_contribution, group: nf.group, target_date: nf.target_date || null, is_rolling: nf.is_rolling })
    if (adding === 'debt') await api.createDebt({ name: nf.name, total_amount: nf.target_amount, type: 'loan' })
    nf = { name: '', target_amount: 0, monthly_contribution: 0, group: 'wants', target_date: '', is_rolling: false }
    adding = null
    invalidate()
    showToast('Создано')
  }

  async function delFund(f: FundSummary) { if (confirm(`Удалить копилку «${f.name}»?`)) { await api.deleteFund(f.id); invalidate() } }
  async function delDebt(d: DebtSummary) { if (confirm(`Удалить долг «${d.name}»?`)) { await api.deleteDebt(d.id); invalidate() } }

  async function logout() {
    await api.logout()
    authenticated.set(false)
  }

  const groupLabel = (g: 'wants' | 'savings') => g === 'wants' ? 'Желания' : 'Сбережения'
</script>

<div class="page-header"><h1>Ещё</h1></div>

<div class="page">
  <a class="btn btn-ghost faq-btn" href="#/deposit"><i class="ti ti-building-bank"></i> Калькулятор вклада</a>
  <a class="btn btn-ghost faq-btn" href="#/faq"><i class="ti ti-help"></i> Как это работает</a>

  <!-- Funds -->
  <section>
    <div class="row section-label"><span>Копилки</span>
      <button class="btn-ghost btn-sm" onclick={() => (adding = adding === 'fund' ? null : 'fund')} aria-label="Добавить копилку"><i class="ti ti-plus"></i></button>
    </div>
    <div class="stack">
      {#each funds as f}
        <div class="card">
          <div class="row">
            <strong>{f.name}</strong>
            <span class="num">{money(f.current_amount)} / {money(f.target_amount)}</span>
          </div>
          <div class="meta-row">
            <span class="badge">{groupLabel(f.group)}</span>
            {#if f.target_date}<span class="muted small">до {f.target_date}</span>{/if}
            {#if f.is_rolling}<span class="muted small">· возобн.</span>{/if}
          </div>
          <ProgressBar spent={f.current_amount} limit={f.target_amount} color="green" />
          <div class="actions">
            <button class="btn-ghost btn-sm" onclick={() => toggle('fund', f.id, 'contribute')}>Пополнить</button>
            <button class="btn-ghost btn-sm" onclick={() => toggle('fund', f.id, 'spend')}>Потратить</button>
            <button class="btn-ghost btn-sm" onclick={() => toggle('fund', f.id, 'edit', f)}>Изменить</button>
            <button class="btn-ghost btn-sm danger" onclick={() => delFund(f)}>Удалить</button>
          </div>
          {#if isOpen('fund', f.id, 'contribute')}
            <div class="panel">
              <input class="input num" inputmode="numeric" placeholder="Сумма" bind:value={amount} />
              <button class="btn btn-primary" onclick={() => contributeFund(f.id)}>Пополнить</button>
            </div>
          {/if}
          {#if isOpen('fund', f.id, 'spend')}
            <div class="panel">
              <input class="input num" inputmode="numeric" placeholder="Сумма" bind:value={amount} />
              <button class="btn btn-primary" onclick={() => spendFund(f.id)}>Потратить</button>
            </div>
          {/if}
          {#if isOpen('fund', f.id, 'edit')}
            <div class="panel">
              <input class="input" bind:value={edit.name} />
              <select class="input" bind:value={edit.group}>
                <option value="wants">Желания</option>
                <option value="savings">Сбережения</option>
              </select>
              <input class="input num" inputmode="numeric" placeholder="Цель (сумма)" bind:value={edit.target_amount} />
              <input class="input num" inputmode="numeric" placeholder="Взнос/мес" bind:value={edit.monthly_contribution} />
              <input class="input" type="date" placeholder="Дата цели" bind:value={edit.target_date} />
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
      <div class="section-label">Новое: {adding === 'fund' ? 'копилка' : 'долг'}</div>
      <input class="input" placeholder="Название" bind:value={nf.name} />
      {#if adding === 'fund'}
        <select class="input" bind:value={nf.group}>
          <option value="wants">Желания</option>
          <option value="savings">Сбережения</option>
        </select>
      {/if}
      <input class="input num" inputmode="numeric" placeholder={adding === 'debt' ? 'Сумма долга' : 'Целевая сумма'} bind:value={nf.target_amount} />
      {#if adding === 'fund'}
        <input class="input num" inputmode="numeric" placeholder="Взнос/мес" bind:value={nf.monthly_contribution} />
        <input class="input" type="date" placeholder="Дата цели" bind:value={nf.target_date} />
        <label class="check"><input type="checkbox" bind:checked={nf.is_rolling} /> Возобновляемая</label>
      {/if}
      <button class="btn btn-primary" onclick={createItem}>Создать</button>
    </div>
  {/if}

  <!-- Participants -->
  <section>
    <div class="section-label">Участники</div>
    <div class="card stack">
      {#each users as u}
        <div class="row">
          {#if editingUserId === u.id}
            <input class="input" bind:value={editingUserName} />
            <button class="btn-ghost btn-sm" onclick={saveUserEdit} aria-label="Сохранить имя"><i class="ti ti-check"></i></button>
          {:else}
            <span>{u.name}</span>
            <span class="actions">
              <button class="btn-ghost btn-sm" onclick={() => startEditUser(u)} aria-label="Переименовать"><i class="ti ti-pencil"></i></button>
              <button class="btn-ghost btn-sm danger" onclick={() => removeUser(u)} aria-label="Удалить участника"><i class="ti ti-trash"></i></button>
            </span>
          {/if}
        </div>
      {/each}
      <div class="add-row">
        <input class="input" placeholder="Имя участника" bind:value={newUserName} />
        <button class="btn-add" onclick={addUser} aria-label="Добавить"><i class="ti ti-plus"></i></button>
      </div>
    </div>
  </section>

  <!-- Settings -->
  <section>
    <div class="section-label">Настройки</div>
    <div class="card stack">
      <a class="btn btn-ghost" href="/api/settings/export/json">Экспорт JSON</a>
      <a class="btn btn-ghost" href="/api/settings/export/csv">Экспорт CSV</a>
      <button class="btn btn-ghost danger" onclick={logout}>Выйти</button>
    </div>
  </section>
</div>

<style>
  .faq-btn { display: flex; align-items: center; gap: var(--space-2); justify-content: center; border: 1px solid rgba(255,255,255,0.06); border-radius: var(--radius-md); padding: 12px; }
  section { display: flex; flex-direction: column; gap: var(--space-2); }
  .actions { display: flex; gap: var(--space-2); margin-top: var(--space-2); flex-wrap: wrap; }
  .add-row { display: flex; gap: var(--space-2); align-items: center; margin-top: var(--space-2); }
  .add-row .input { flex: 1; }
  .btn-add { background: var(--blue); color: #fff; border: none; border-radius: var(--radius-sm); width: 44px; height: 44px; flex-shrink: 0; }
  .danger { color: var(--red); }
  .btn-ghost.btn { width: 100%; }
  .small { font-size: var(--text-xs); margin-top: 4px; }
  .panel { display: flex; flex-direction: column; gap: var(--space-2); margin-top: var(--space-3); padding-top: var(--space-3); border-top: 1px solid rgba(255,255,255,0.06); }
  .check { display: flex; align-items: center; gap: 8px; font-size: var(--text-sm); color: var(--text-secondary); }
  .meta-row { display: flex; align-items: center; gap: var(--space-2); margin-top: 2px; margin-bottom: 2px; }
  .badge { font-size: var(--text-xs); padding: 2px 6px; border-radius: 4px; background: rgba(255,255,255,0.08); color: var(--text-secondary); }
</style>
