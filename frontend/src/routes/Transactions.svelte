<script lang="ts">
  import { api, type Transaction, type Category, type User } from '../lib/api'
  import { period, dataVersion, invalidate, showToast } from '../lib/stores'
  import { money, formatDate, monthName } from '../lib/format'
  import Loader from '../lib/components/Loader.svelte'
  import BottomSheet from '../lib/components/BottomSheet.svelte'
  import TxForm from '../lib/components/TxForm.svelte'

  const PAGE_SIZE = 20

  const GROUP_LABELS: Record<string, string> = {
    needs: 'Нужды',
    wants: 'Желания',
    savings: 'Сбережения',
    income: 'Доходы',
  }

  let items = $state<Transaction[]>([])
  let total = $state(0)
  let offset = $state(0)
  let loaded = $state(false)
  let dayTotals = $state<Record<string, number>>({})
  let monthTotals = $state<Record<string, number>>({})

  let categories = $state<Category[]>([])
  let users = $state<User[]>([])

  let typeFilter = $state<'' | 'income' | 'expense'>('')
  let categoryIds = $state<number[]>([])
  let catSheetOpen = $state(false)
  let groupFilter = $state<'' | 'needs' | 'wants' | 'savings'>('')
  let userFilter = $state<number | ''>('')
  let dateFrom = $state('')
  let dateTo = $state('')
  let activePreset = $state<'' | 'today' | 'yesterday' | 'week' | 'month' | 'year' | 'custom'>('')
  let customOpen = $state(false)
  let sortBy = $state<'date' | 'amount'>('date')
  let sortDir = $state<'asc' | 'desc'>('desc')

  // A custom date range (or a preset) takes precedence over the global month period.
  let usingDateRange = $derived(!!dateFrom || !!dateTo)

  let categoryFilterLabel = $derived(
    categoryIds.length === 0
      ? 'Все категории'
      : categoryIds.length === 1
        ? (categories.find((c) => c.id === categoryIds[0])?.name ?? '1 категория')
        : `${categoryIds.length} категории`,
  )

  let revealedId = $state<number | null>(null)
  let editingTx = $state<Transaction | null>(null)

  $effect(() => {
    void $dataVersion
    void typeFilter; void categoryIds; void groupFilter; void userFilter
    void dateFrom; void dateTo; void sortBy; void sortDir; void offset
    void $period
    load()
  })

  $effect(() => {
    // Reset to the first page whenever a filter changes.
    void typeFilter; void categoryIds; void groupFilter; void userFilter
    void dateFrom; void dateTo; void sortBy; void sortDir; void $period
    offset = 0
  })

  async function loadFilters() {
    const [cats, us] = await Promise.all([api.categories(undefined, true), api.users()])
    categories = cats
    users = us
  }
  loadFilters()

  async function load() {
    const { year, month } = $period
    // A date range (preset or custom) wins; otherwise scope to the current month.
    const noMonth = usingDateRange
    const r = await api.transactionsList({
      year: noMonth ? undefined : year,
      month: noMonth ? undefined : month,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
      type: typeFilter || undefined,
      category_ids: categoryIds.length ? categoryIds : undefined,
      group: groupFilter || undefined,
      user_id: userFilter || undefined,
      sort_by: sortBy,
      sort_dir: sortDir,
      limit: PAGE_SIZE,
      offset,
    })
    items = r.items
    total = r.total
    dayTotals = r.day_totals
    monthTotals = r.month_totals
    loaded = true
  }

  function toggleCategory(id: number) {
    categoryIds = categoryIds.includes(id) ? categoryIds.filter((x) => x !== id) : [...categoryIds, id]
  }
  function clearCategories() {
    categoryIds = []
  }

  function clearDates() {
    dateFrom = ''
    dateTo = ''
    activePreset = ''
  }

  // Local calendar date as YYYY-MM-DD — NOT Date#toISOString(), which converts to UTC
  // and silently shifts the date back a day for any timezone ahead of UTC (e.g. Moscow).
  function toISO(d: Date) {
    const y = d.getFullYear()
    const m = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    return `${y}-${m}-${day}`
  }

  function applyPreset(key: 'today' | 'yesterday' | 'week' | 'month' | 'year') {
    activePreset = key
    const now = new Date()
    if (key === 'today') {
      dateFrom = dateTo = toISO(now)
    } else if (key === 'yesterday') {
      const y = new Date(now)
      y.setDate(y.getDate() - 1)
      dateFrom = dateTo = toISO(y)
    } else if (key === 'week') {
      const day = (now.getDay() + 6) % 7 // Monday = 0
      const monday = new Date(now)
      monday.setDate(now.getDate() - day)
      dateFrom = toISO(monday)
      dateTo = toISO(now)
    } else if (key === 'month') {
      dateFrom = toISO(new Date(now.getFullYear(), now.getMonth(), 1))
      dateTo = toISO(now)
    } else if (key === 'year') {
      dateFrom = toISO(new Date(now.getFullYear(), 0, 1))
      dateTo = toISO(now)
    }
    customOpen = false
  }

  function onManualDate() {
    activePreset = 'custom'
  }

  function categoryIcon(t: Transaction) {
    return categories.find((c) => c.id === t.category_id)
  }

  function toggleSort(field: 'date' | 'amount') {
    if (sortBy === field) sortDir = sortDir === 'asc' ? 'desc' : 'asc'
    else { sortBy = field; sortDir = 'desc' }
  }

  function monthKey(dateStr: string) {
    return dateStr.slice(0, 7) // "YYYY-MM"
  }
  function monthLabel(dateStr: string) {
    const d = new Date(dateStr)
    return `${monthName(d.getMonth() + 1)} ${d.getFullYear()}`
  }

  function dayLabel(dateStr: string) {
    const now = new Date()
    if (dateStr === toISO(now)) return 'Сегодня'
    const y = new Date(now)
    y.setDate(y.getDate() - 1)
    if (dateStr === toISO(y)) return 'Вчера'
    return formatDate(dateStr)
  }

  function openEdit(t: Transaction) {
    revealedId = null
    editingTx = t
  }
  function onEdited() {
    editingTx = null
    invalidate()
    showToast('Операция изменена')
  }

  async function del(t: Transaction) {
    revealedId = null
    items = items.filter((x) => x.id !== t.id)
    await api.deleteTransaction(t.id)
    invalidate()
    showToast('Операция удалена', async () => {
      await api.createTransaction({
        type: t.type, amount: t.amount, category_id: t.category_id,
        user_id: t.user_id, date: t.date, comment: t.comment,
      })
      invalidate()
    })
  }

  let from = $derived(total === 0 ? 0 : offset + 1)
  let to = $derived(Math.min(offset + PAGE_SIZE, total))
</script>

<div class="page-header"><h1>Все операции</h1></div>

<div class="page">
  <div class="card stack filters">
    <div class="filter-row">
      <select class="input" bind:value={typeFilter}>
        <option value="">Все типы</option>
        <option value="expense">Расход</option>
        <option value="income">Доход</option>
      </select>
      <button class="input cat-trigger" onclick={() => (catSheetOpen = true)}>
        <span>{categoryFilterLabel}</span>
        <i class="ti ti-chevron-down"></i>
      </button>
    </div>

    <div class="filter-row group-row">
      {#each [['', 'Все'], ['needs', 'Нужды'], ['wants', 'Желания'], ['savings', 'Сбережения']] as [g, label]}
        <button
          class="btn-ghost btn-sm"
          class:active={groupFilter === g}
          onclick={() => (groupFilter = g as typeof groupFilter)}
        >{label}</button>
      {/each}
    </div>

    {#if users.length > 1}
      <div class="filter-row">
        <select class="input" bind:value={userFilter}>
          <option value="">Все участники</option>
          {#each users as u}<option value={u.id}>{u.name}</option>{/each}
        </select>
      </div>
    {/if}

    <div class="filter-row presets-row">
      {#each [['today', 'Сегодня'], ['yesterday', 'Вчера'], ['week', 'Неделя'], ['month', 'Месяц'], ['year', 'Год']] as [key, label]}
        <button
          class="btn-ghost btn-sm"
          class:active={activePreset === key}
          onclick={() => applyPreset(key as 'today' | 'yesterday' | 'week' | 'month' | 'year')}
        >{label}</button>
      {/each}
      <button
        class="btn-ghost btn-sm"
        class:active={activePreset === 'custom'}
        aria-label="Свой период"
        onclick={() => (customOpen = !customOpen)}
      ><i class="ti ti-calendar"></i></button>
    </div>
    {#if customOpen || activePreset === 'custom'}
      <div class="filter-row date-row">
        <label class="date-field">
          <span>С</span>
          <input class="input" type="date" bind:value={dateFrom} max={dateTo || undefined} aria-label="Дата с" oninput={onManualDate} />
        </label>
        <label class="date-field">
          <span>По</span>
          <input class="input" type="date" bind:value={dateTo} min={dateFrom || undefined} aria-label="Дата по" oninput={onManualDate} />
        </label>
        {#if usingDateRange}
          <button class="btn-ghost btn-sm clear-dates" onclick={clearDates} aria-label="Сбросить даты"><i class="ti ti-x"></i></button>
        {/if}
      </div>
    {/if}
    <div class="filter-row sort-row">
      <button class="btn-ghost btn-sm" class:active={sortBy === 'date'} onclick={() => toggleSort('date')}>
        Дата {sortBy === 'date' ? (sortDir === 'asc' ? '↑' : '↓') : ''}
      </button>
      <button class="btn-ghost btn-sm" class:active={sortBy === 'amount'} onclick={() => toggleSort('amount')}>
        Сумма {sortBy === 'amount' ? (sortDir === 'asc' ? '↑' : '↓') : ''}
      </button>
    </div>
  </div>

  {#if !loaded}
    <Loader />
  {:else if items.length === 0}
    <p class="muted">Операций не найдено.</p>
  {:else}
    <div class="stack">
      {#each items as t, i (t.id)}
        {@const cat = categoryIcon(t)}
        {@const prevDate = i > 0 ? items[i - 1].date : null}
        {@const showMonthHeader = sortBy === 'date' && (i === 0 || monthKey(prevDate!) !== monthKey(t.date))}
        {@const showDayHeader = sortBy === 'date' && (i === 0 || prevDate !== t.date)}
        {#if showMonthHeader}
          <div class="month-header">
            <span>{monthLabel(t.date)}</span>
            {#if monthTotals[monthKey(t.date)]}
              <span class="num">−{money(monthTotals[monthKey(t.date)])} ₽</span>
            {/if}
          </div>
        {/if}
        {#if showDayHeader}
          <div class="day-header">
            <span>{dayLabel(t.date)}</span>
            {#if dayTotals[t.date]}
              <span class="num">−{money(dayTotals[t.date])} ₽</span>
            {/if}
          </div>
        {/if}
        <div class="tx-wrap">
          <button class="tx" onclick={() => (revealedId = revealedId === t.id ? null : t.id)}>
            <span class="tx-cat">
              {#if cat}<i class="ti {cat.icon}" style="color:{cat.color}"></i>{/if}
              {t.category_name ?? (t.type === 'income' ? 'Доход' : '—')}
            </span>
            {#if t.comment}
              <span class="tx-comment muted">{t.comment}</span>
            {/if}
            {#if sortBy !== 'date'}
              <span class="tx-meta muted">{formatDate(t.date)}{t.user_name ? ` · ${t.user_name}` : ''}</span>
            {:else if t.user_name}
              <span class="tx-meta muted">{t.user_name}</span>
            {/if}
            <span class="tx-amt num" class:income={t.type === 'income'}>
              {t.type === 'income' ? '+' : '−'}{money(t.amount)} ₽
            </span>
          </button>
          {#if revealedId === t.id}
            <div class="tx-actions">
              <button class="btn-ghost btn-sm" onclick={() => openEdit(t)} aria-label="Изменить"><i class="ti ti-pencil"></i></button>
              <button class="tx-del" onclick={() => del(t)} aria-label="Удалить"><i class="ti ti-trash"></i></button>
            </div>
          {/if}
        </div>
      {/each}
    </div>

    <div class="pager">
      <button class="btn-ghost btn-sm" disabled={offset === 0} onclick={() => (offset = Math.max(0, offset - PAGE_SIZE))}>
        <i class="ti ti-chevron-left"></i> Назад
      </button>
      <span class="muted small">{from}–{to} из {total}</span>
      <button class="btn-ghost btn-sm" disabled={to >= total} onclick={() => (offset += PAGE_SIZE)}>
        Далее <i class="ti ti-chevron-right"></i>
      </button>
    </div>
  {/if}
</div>

<BottomSheet open={!!editingTx} title="Изменить операцию" onclose={() => (editingTx = null)}>
  {#snippet children()}
    {#if editingTx}
      <TxForm existing={editingTx} onsubmitted={onEdited} />
    {/if}
  {/snippet}
</BottomSheet>

<BottomSheet open={catSheetOpen} title="Категории" onclose={() => (catSheetOpen = false)}>
  {#snippet children()}
    {#each ['needs', 'wants', 'savings', 'income'] as g}
      {@const cats = categories.filter((c) => c.group === g)}
      {#if cats.length}
        <div class="group-section">
          <span class="group-label">{GROUP_LABELS[g]}</span>
          <div class="cats-grid" role="listbox" aria-label={GROUP_LABELS[g]} aria-multiselectable="true">
            {#each cats as c (c.id)}
              <button
                role="option"
                aria-selected={categoryIds.includes(c.id)}
                class="cat-chip"
                class:active={categoryIds.includes(c.id)}
                style="--c: {c.color}"
                onclick={() => toggleCategory(c.id)}
              >
                <i class="ti {c.icon}"></i>
                <span>{c.name}</span>
              </button>
            {/each}
          </div>
        </div>
      {/if}
    {/each}
    <div class="sheet-actions">
      <button class="btn-ghost btn-sm" onclick={clearCategories} disabled={!categoryIds.length}>Сбросить</button>
      <button class="btn btn-primary" onclick={() => (catSheetOpen = false)}>Готово {categoryIds.length ? `(${categoryIds.length})` : ''}</button>
    </div>
  {/snippet}
</BottomSheet>

<style>
  .filters { gap: var(--space-2); }
  .filter-row { display: flex; gap: var(--space-2); }
  .filter-row .input { flex: 1; }
  .cat-trigger { display: flex; align-items: center; justify-content: space-between; text-align: left; color: var(--text-primary); }
  .group-row { flex-wrap: wrap; }
  .group-row button.active { color: var(--text-primary); }
  .presets-row { flex-wrap: wrap; }
  .presets-row button.active { color: var(--text-primary); }
  .date-row { align-items: flex-end; flex-wrap: wrap; }
  .date-field { flex: 1 1 140px; min-width: 0; display: flex; flex-direction: column; gap: 4px; font-size: var(--text-xs); color: var(--text-secondary); }
  .date-field .input { width: 100%; min-width: 0; font-size: var(--text-sm); padding: 10px; }
  .clear-dates { flex: 0 0 auto; align-self: stretch; }
  .sort-row button.active { color: var(--text-primary); }

  .group-section { display: flex; flex-direction: column; gap: var(--space-1); }
  .group-label {
    font-size: var(--text-xs);
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding: 0 2px;
  }
  .cats-grid { display: flex; flex-wrap: wrap; gap: var(--space-2); }
  .cat-chip {
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    width: 72px;
    padding: 10px 4px;
    background: var(--bg-surface);
    border: 1px solid transparent;
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    font-size: var(--text-xs);
  }
  .cat-chip i { font-size: 22px; color: var(--c); }
  .cat-chip span { text-align: center; line-height: 1.1; }
  .cat-chip.active { border-color: var(--c); background: var(--bg-elevated); color: var(--text-primary); }
  .sheet-actions { display: flex; gap: var(--space-2); justify-content: space-between; }

  .month-header { display: flex; justify-content: space-between; align-items: baseline; font-size: var(--text-xs); color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.06em; padding: var(--space-2) 2px 2px; }
  .month-header:first-child { padding-top: 0; }
  .month-header .num { text-transform: none; letter-spacing: -0.02em; }
  .day-header { display: flex; justify-content: space-between; align-items: baseline; font-size: var(--text-xs); color: var(--text-muted); padding: var(--space-1) 2px 2px; }
  .day-header .num { color: var(--text-secondary); }
  .month-header + .day-header { padding-top: 2px; }

  .tx-wrap { display: flex; gap: var(--space-2); align-items: stretch; }
  .tx { flex: 1; display: grid; grid-template-columns: 1fr auto; grid-template-rows: auto auto; gap: 2px 0; background: var(--bg-surface); border: none; border-radius: var(--radius-md); padding: var(--space-3); text-align: left; }
  .tx-cat { font-size: var(--text-base); display: flex; align-items: center; gap: 6px; }
  .tx-comment { font-size: var(--text-sm); grid-column: 1; }
  .tx-meta { font-size: var(--text-xs); }
  .tx-amt { grid-row: 1 / -1; grid-column: 2; align-self: center; }
  .tx-amt.income { color: var(--green); }
  .tx-actions { display: flex; flex-direction: column; gap: var(--space-1); }
  .tx-del { background: var(--red-bg); color: var(--red); border: none; border-radius: var(--radius-md); width: 56px; flex: 1; }
  .pager { display: flex; align-items: center; justify-content: space-between; padding-top: var(--space-2); }
  .small { font-size: var(--text-xs); }
</style>
