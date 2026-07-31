<script lang="ts">
  import { api, type FundSummary, type DebtSummary, type User } from '../lib/api'
  import { authenticated, dataVersion, invalidate, me, showToast, showHelp } from '../lib/stores'
  import { money } from '../lib/format'
  import ProgressBar from '../lib/components/ProgressBar.svelte'

  let funds = $state<FundSummary[]>([])
  let debts = $state<DebtSummary[]>([])
  let users = $state<User[]>([])
  let newUserName = $state('')
  let editingUserId = $state<number | null>(null)
  let editingUserName = $state('')
  let editingUserTgId = $state<string>('')

  let openPanel = $state<string | null>(null)
  let panelMode = $state<'contribute' | 'spend' | 'edit'>('contribute')
  let amount = $state(0)
  let edit = $state<any>({})

  let adding = $state<'fund' | 'debt' | null>(null)
  let nf = $state({ name: '', target_amount: 0, monthly_contribution: 0, group: 'wants' as 'wants' | 'savings', target_date: '', is_rolling: false })

  $effect(() => { void $dataVersion; reload() })
  async function reload() {
    ;[funds, debts, users] = await Promise.all([api.funds(), api.debts(), api.users()])
  }

  async function addUser() {
    if (!newUserName.trim()) return
    await api.createUser({ name: newUserName.trim() })
    newUserName = ''
    invalidate()
  }
  function startEditUser(u: User) {
    editingUserId = u.id
    editingUserName = u.name
    editingUserTgId = u.telegram_id ?? ''
  }
  async function saveUserEdit() {
    if (editingUserId == null || !editingUserName.trim()) return
    await api.updateUser(editingUserId, { name: editingUserName.trim(), telegram_id: editingUserTgId || null })
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
    if (openPanel === key && panelMode === mode) { openPanel = null; return }
    openPanel = key
    panelMode = mode
    amount = 0
    if (mode === 'edit' && item) edit = { ...item }
  }
  const isOpen = (kind: string, id: number, mode: string) => openPanel === `${kind}:${id}` && panelMode === mode

  async function contributeFund(id: number) { await api.fundContribute(id, { amount }); done('Пополнено') }
  async function spendFund(id: number) { await api.fundSpend(id, { amount }); done('Потрачено') }
  async function payDebt(id: number) { await api.debtPayment(id, { amount }); done('Платёж записан') }
  async function saveFundEdit(id: number) {
    await api.updateFund(id, {
      name: edit.name, target_amount: edit.target_amount, monthly_contribution: edit.monthly_contribution,
      target_date: edit.target_date || null, is_rolling: edit.is_rolling, group: edit.group,
    })
    done('Сохранено')
  }
  async function saveDebtEdit(id: number) {
    await api.updateDebt(id, {
      name: edit.name, total_amount: edit.total_amount, remaining: edit.remaining,
      interest_rate: edit.interest_rate, monthly_payment: edit.monthly_payment, type: edit.type,
    })
    done('Сохранено')
  }
  function done(msg: string) { openPanel = null; invalidate(); showToast(msg) }

  async function createItem() {
    if (!nf.name) return
    if (adding === 'fund') {
      await api.createFund({
        name: nf.name, target_amount: nf.target_amount, monthly_contribution: nf.monthly_contribution,
        group: nf.group, target_date: nf.target_date || null, is_rolling: nf.is_rolling,
      })
    }
    if (adding === 'debt') await api.createDebt({ name: nf.name, total_amount: nf.target_amount, type: 'loan' })
    nf = { name: '', target_amount: 0, monthly_contribution: 0, group: 'wants', target_date: '', is_rolling: false }
    adding = null
    invalidate()
    showToast('Создано')
  }

  async function delFund(f: FundSummary) { if (confirm(`Удалить копилку «${f.name}»?`)) { await api.deleteFund(f.id); invalidate() } }
  async function delDebt(d: DebtSummary) { if (confirm(`Удалить долг «${d.name}»?`)) { await api.deleteDebt(d.id); invalidate() } }

  async function logout() { await api.logout(); authenticated.set(false) }

  const groupLabel = (g: 'wants' | 'savings') => (g === 'wants' ? 'Желания' : 'Сбережения')

  let LINKS = $derived([
    { href: '#/transactions', icon: 'ti-list', name: 'Все операции', meta: 'История, фильтры, экспорт' },
    { href: '#/categories', icon: 'ti-category', name: 'Категории', meta: 'Названия, иконки и группы' },
    { href: '#/deposit', icon: 'ti-building-bank', name: 'Калькулятор вклада', meta: 'Капитализация и ставки по годам' },
    ...($me?.is_admin
      ? [
          { href: '#/integrations', icon: 'ti-robot', name: 'Телеграм-бот и AI', meta: 'Запись трат сообщением' },
          { href: '#/admin', icon: 'ti-shield-lock', name: 'Админка', meta: 'Пространства, аккаунты, инвайты' },
        ]
      : []),
    { href: '#/faq', icon: 'ti-help', name: 'Как это работает', meta: 'Частые вопросы' },
  ])

  const GLOSSARY = [
    { term: 'Свободно до конца месяца', def: 'Сколько ещё можно потратить, не залезая в накопления.', formula: 'доход − расходы − отложено' },
    { term: 'Можно тратить в день', def: 'Ровный дневной бюджет на остаток месяца.', formula: 'свободно ÷ дней до конца месяца' },
    { term: 'Норма сбережений', def: 'Главный показатель здоровья бюджета. Здоровым считается 20% и выше.', formula: '(доход − расходы) ÷ доход × 100%' },
    { term: 'Темп месяца', def: 'Светлая риска на шкалах: где вы должны быть по календарю. Заливка правее риски — тратите быстрее плана.', formula: 'прошло дней ÷ дней в месяце' },
    { term: 'Чистый поток', def: 'Разница между тем, что пришло, и тем, что ушло за месяц.', formula: 'доход − расход' },
    { term: 'Регулярные расходы', def: 'Платежи, которые повторяются каждый месяц: жильё, кредиты, сад, связь.', formula: 'траты в категории ≥ 3 месяцев подряд' },
  ]
</script>

<div class="page">
  <div class="cols">
    <section class="col-wide stack">
      <!-- Funds -->
      <div class="card">
        <div class="row">
          <h2 class="card-title">Копилки</h2>
          <button class="btn btn-secondary btn-sm" onclick={() => (adding = adding === 'fund' ? null : 'fund')}>
            <i class="ti ti-plus"></i> Копилка
          </button>
        </div>
        {#if $showHelp}
          <p class="explain">Справочный ручной учёт: остатки вы меняете сами, в операции, план и аналитику они не попадают. Реальную трату или перевод записывайте отдельной операцией.</p>
        {/if}
        {#if funds.length === 0}
          <p class="muted small" style="margin-top: 12px">Копилок пока нет. Создайте первую — например, «Подушка безопасности».</p>
        {:else}
          <div class="items">
            {#each funds as f}
              <div class="item">
                <div class="row">
                  <strong class="small">{f.name}</strong>
                  <span class="num small">{money(f.current_amount)} / {money(f.target_amount)} ₽</span>
                </div>
                <div class="meta-row">
                  <span class="badge">{groupLabel(f.group)}</span>
                  {#if f.target_date}<span class="dim tiny">до {f.target_date}</span>{/if}
                  {#if f.is_rolling}<span class="dim tiny">· возобновляемая</span>{/if}
                </div>
                <ProgressBar spent={f.current_amount} limit={f.target_amount} color="green" />
                {#if f.monthly_contribution > 0 && f.target_amount > f.current_amount}
                  <div class="dim tiny">
                    При {money(f.monthly_contribution)} ₽ в месяц — ещё
                    {Math.ceil((f.target_amount - f.current_amount) / f.monthly_contribution)} мес.
                  </div>
                {/if}
                <div class="actions">
                  <button class="act" onclick={() => toggle('fund', f.id, 'contribute')}>Пополнить</button>
                  <button class="act" onclick={() => toggle('fund', f.id, 'spend')}>Потратить</button>
                  <button class="act" onclick={() => toggle('fund', f.id, 'edit', f)}>Изменить</button>
                  <button class="act danger" onclick={() => delFund(f)}>Удалить</button>
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
                    <input class="input" bind:value={edit.name} aria-label="Название" />
                    <select class="input" bind:value={edit.group} aria-label="Группа">
                      <option value="wants">Желания</option>
                      <option value="savings">Сбережения</option>
                    </select>
                    <input class="input num" inputmode="numeric" placeholder="Цель (сумма)" bind:value={edit.target_amount} />
                    <input class="input num" inputmode="numeric" placeholder="Взнос/мес" bind:value={edit.monthly_contribution} />
                    <input class="input" type="date" bind:value={edit.target_date} aria-label="Дата цели" />
                    <label class="check"><input type="checkbox" bind:checked={edit.is_rolling} /> Возобновляемая</label>
                    <button class="btn btn-primary" onclick={() => saveFundEdit(f.id)}>Сохранить</button>
                  </div>
                {/if}
              </div>
            {/each}
          </div>
        {/if}
      </div>

      <!-- Debts -->
      <div class="card">
        <div class="row">
          <h2 class="card-title">Долги</h2>
          <button class="btn btn-secondary btn-sm" onclick={() => (adding = adding === 'debt' ? null : 'debt')}>
            <i class="ti ti-plus"></i> Долг
          </button>
        </div>
        {#if $showHelp}
          <p class="explain">Справочный ручной учёт остатков: платёж здесь уменьшает только долг, а сам расход записывайте обычной операцией в свою категорию. Гасить выгоднее тот долг, у которого выше ставка.</p>
        {/if}
        {#if debts.length === 0}
          <p class="muted small" style="margin-top: 12px">Долгов нет — это хорошая новость.</p>
        {:else}
          <div class="items">
            {#each debts as d}
              <div class="item">
                <div class="row">
                  <strong class="small">{d.name}</strong>
                  <span class="num small">осталось {money(d.remaining)} ₽</span>
                </div>
                <div class="dim tiny">
                  {d.interest_rate > 0 ? `${d.interest_rate}% годовых` : 'Без процентов'}{d.priority_label ? ` · ${d.priority_label}` : ''}
                </div>
                <ProgressBar spent={d.total_amount - d.remaining} limit={d.total_amount} color="blue" />
                <div class="actions">
                  <button class="act" onclick={() => toggle('debt', d.id, 'contribute')}>Платёж</button>
                  <button class="act" onclick={() => toggle('debt', d.id, 'edit', d)}>Изменить</button>
                  <button class="act danger" onclick={() => delDebt(d)}>Удалить</button>
                </div>
                {#if isOpen('debt', d.id, 'contribute')}
                  <div class="panel">
                    <input class="input num" inputmode="numeric" placeholder="Сумма платежа" bind:value={amount} />
                    <button class="btn btn-primary" onclick={() => payDebt(d.id)}>Записать платёж</button>
                  </div>
                {/if}
                {#if isOpen('debt', d.id, 'edit')}
                  <div class="panel">
                    <input class="input" bind:value={edit.name} aria-label="Название" />
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
        {/if}
      </div>

      {#if adding}
        <div class="card stack">
          <h2 class="card-title">Новое: {adding === 'fund' ? 'копилка' : 'долг'}</h2>
          <input class="input" placeholder="Название" bind:value={nf.name} />
          {#if adding === 'fund'}
            <select class="input" bind:value={nf.group} aria-label="Группа">
              <option value="wants">Желания</option>
              <option value="savings">Сбережения</option>
            </select>
          {/if}
          <input class="input num" inputmode="numeric" placeholder={adding === 'debt' ? 'Сумма долга' : 'Целевая сумма'} bind:value={nf.target_amount} />
          {#if adding === 'fund'}
            <input class="input num" inputmode="numeric" placeholder="Взнос/мес" bind:value={nf.monthly_contribution} />
            <input class="input" type="date" bind:value={nf.target_date} aria-label="Дата цели" />
            <label class="check"><input type="checkbox" bind:checked={nf.is_rolling} /> Возобновляемая</label>
          {/if}
          <div class="row" style="gap: 8px">
            <button class="btn btn-ghost btn-sm" onclick={() => (adding = null)}>Отмена</button>
            <button class="btn btn-primary btn-sm" onclick={createItem}>Создать</button>
          </div>
        </div>
      {/if}
    </section>

    <aside class="col stack">
      <!-- Family -->
      <div class="card">
        <h2 class="card-title">Участники</h2>
        <div class="stack" style="margin-top: 12px; gap: 12px">
          {#each users as u}
            {#if editingUserId === u.id}
              <div class="stack" style="gap: 8px">
                <input class="input" bind:value={editingUserName} aria-label="Имя" />
                <input class="input" bind:value={editingUserTgId} placeholder="Telegram ID (для бота)" />
                <button class="btn btn-primary btn-sm" onclick={saveUserEdit}>Сохранить</button>
              </div>
            {:else}
              <div class="person">
                <span class="avatar">{u.name.slice(0, 1).toUpperCase()}</span>
                <span class="person-main">
                  <span class="small">{u.name}</span>
                  <span class="dim tiny">{u.telegram_id ? 'Telegram подключён' : 'Telegram не подключён'}</span>
                </span>
                <button class="icon-btn" onclick={() => startEditUser(u)} aria-label="Переименовать"><i class="ti ti-pencil"></i></button>
                <button class="icon-btn danger" onclick={() => removeUser(u)} aria-label="Удалить участника"><i class="ti ti-trash"></i></button>
              </div>
            {/if}
          {/each}
        </div>
        <div class="add-row">
          <input class="input" placeholder="Имя участника" bind:value={newUserName} />
          <button class="btn-add" onclick={addUser} aria-label="Добавить"><i class="ti ti-plus"></i></button>
        </div>
      </div>

      <!-- Navigation -->
      <div class="card links">
        {#each LINKS as l}
          <a class="link" href={l.href}>
            <i class="ti {l.icon}"></i>
            <span class="link-main">
              <span class="small">{l.name}</span>
              <span class="dim tiny">{l.meta}</span>
            </span>
            <i class="ti ti-chevron-right chev"></i>
          </a>
        {/each}
      </div>

      <!-- Glossary: the answer to "какая цифра за что отвечает" -->
      <div class="card">
        <h2 class="card-title">Что значат цифры</h2>
        <p class="explain">Короткий словарь — чтобы не гадать, откуда берётся каждое число.</p>
        <div class="glossary">
          {#each GLOSSARY as g}
            <div class="gitem">
              <div class="small" style="font-weight: 600">{g.term}</div>
              <div class="muted tiny" style="line-height: 1.5; margin-top: 4px">{g.def}</div>
              <div class="num tiny dim" style="margin-top: 6px">{g.formula}</div>
            </div>
          {/each}
        </div>
      </div>

      <div class="card stack">
        <h2 class="card-title">Данные</h2>
        <a class="btn btn-secondary" href="/api/settings/export/csv">Экспорт CSV</a>
        <a class="btn btn-ghost" href="/api/settings/export/json">Экспорт JSON</a>
        <button class="btn btn-ghost danger" onclick={logout}>Выйти</button>
      </div>
    </aside>
  </div>
</div>

<style>
  .items { display: flex; flex-direction: column; gap: var(--space-3); margin-top: var(--space-4); }
  .item {
    display: flex; flex-direction: column; gap: 8px;
    padding: var(--space-3) var(--space-4);
    background: var(--bg-elevated); border-radius: var(--radius-md);
  }
  .meta-row { display: flex; align-items: center; gap: var(--space-2); }
  .badge { font-size: var(--text-xs); padding: 2px 8px; border-radius: 999px; background: rgba(255, 255, 255, 0.06); color: var(--text-secondary); }

  .actions { display: flex; gap: var(--space-2); flex-wrap: wrap; margin-top: 2px; }
  .act {
    min-height: 32px; padding: 0 11px; border-radius: 9px;
    border: 1px solid var(--line); background: transparent;
    color: var(--text-secondary); font-size: 12.5px; font-weight: 500;
  }
  .act:hover { color: var(--text-primary); background: rgba(255, 255, 255, 0.04); }
  .act.danger { color: var(--red); }
  .panel {
    display: flex; flex-direction: column; gap: var(--space-2);
    margin-top: var(--space-2); padding-top: var(--space-3);
    border-top: 1px solid var(--line);
  }
  .check { display: flex; align-items: center; gap: 8px; font-size: var(--text-sm); color: var(--text-secondary); }

  .person { display: flex; align-items: center; gap: 11px; }
  .avatar {
    width: 34px; height: 34px; flex: 0 0 34px; border-radius: 50%;
    background: var(--blue); color: #0b1220; display: grid; place-items: center;
    font-weight: 700; font-size: 14px;
  }
  .person-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 1px; }
  .icon-btn {
    width: 32px; height: 32px; border: none; border-radius: 9px;
    background: transparent; color: var(--text-muted); display: grid; place-items: center;
  }
  .icon-btn:hover { background: var(--bg-elevated); color: var(--text-primary); }
  .icon-btn.danger:hover { background: var(--red-bg); color: var(--red); }

  .add-row { display: flex; gap: var(--space-2); align-items: center; margin-top: var(--space-3); }
  .add-row .input { flex: 1; min-width: 0; }
  .btn-add {
    background: var(--blue); color: #0b1220; border: none; border-radius: var(--radius-sm);
    width: 44px; height: 44px; flex-shrink: 0; display: grid; place-items: center;
  }

  .links { padding: var(--space-2) var(--space-5); }
  .link { display: flex; align-items: center; gap: 12px; padding: 13px 0; border-bottom: 1px solid var(--line); color: var(--text-primary); }
  .link:last-child { border-bottom: none; }
  .link > i { font-size: 19px; color: var(--text-secondary); flex: 0 0 19px; }
  .link-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 1px; }
  .chev { font-size: 17px; color: var(--text-muted); }

  .glossary { display: flex; flex-direction: column; }
  .gitem { padding: 13px 0; border-top: 1px solid var(--line); }
  .gitem:first-child { border-top: none; padding-top: 10px; }

  .small { font-size: var(--text-sm); }
  .tiny { font-size: var(--text-xs); }
  .danger { color: var(--red); }
</style>
