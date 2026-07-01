<script lang="ts">
  import { api, type Transaction, type Category, type User } from '../lib/api'
  import { period, dataVersion, invalidate, showToast } from '../lib/stores'
  import { money, formatDate } from '../lib/format'
  import Loader from '../lib/components/Loader.svelte'
  import BottomSheet from '../lib/components/BottomSheet.svelte'
  import TxForm from '../lib/components/TxForm.svelte'

  const PAGE_SIZE = 20

  let items = $state<Transaction[]>([])
  let total = $state(0)
  let offset = $state(0)
  let loaded = $state(false)

  let categories = $state<Category[]>([])
  let users = $state<User[]>([])

  let typeFilter = $state<'' | 'income' | 'expense'>('')
  let categoryFilter = $state<number | ''>('')
  let userFilter = $state<number | ''>('')
  let allTime = $state(true)
  let dateFrom = $state('')
  let dateTo = $state('')
  let sortBy = $state<'date' | 'amount'>('date')
  let sortDir = $state<'asc' | 'desc'>('desc')

  // A custom date range takes precedence over the month/all-time toggle.
  let usingDateRange = $derived(!!dateFrom || !!dateTo)

  let revealedId = $state<number | null>(null)
  let editingTx = $state<Transaction | null>(null)

  $effect(() => {
    void $dataVersion
    void typeFilter; void categoryFilter; void userFilter; void allTime; void dateFrom; void dateTo; void sortBy; void sortDir; void offset
    void $period
    load()
  })

  $effect(() => {
    // Reset to the first page whenever a filter changes.
    void typeFilter; void categoryFilter; void userFilter; void allTime; void dateFrom; void dateTo; void sortBy; void sortDir; void $period
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
    // Date range wins; otherwise fall back to the month / all-time toggle.
    const noMonth = allTime || usingDateRange
    const r = await api.transactionsList({
      year: noMonth ? undefined : year,
      month: noMonth ? undefined : month,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
      type: typeFilter || undefined,
      category_id: categoryFilter || undefined,
      user_id: userFilter || undefined,
      sort_by: sortBy,
      sort_dir: sortDir,
      limit: PAGE_SIZE,
      offset,
    })
    items = r.items
    total = r.total
    loaded = true
  }

  function clearDates() {
    dateFrom = ''
    dateTo = ''
  }

  function categoryIcon(t: Transaction) {
    return categories.find((c) => c.id === t.category_id)
  }

  function toggleSort(field: 'date' | 'amount') {
    if (sortBy === field) sortDir = sortDir === 'asc' ? 'desc' : 'asc'
    else { sortBy = field; sortDir = 'desc' }
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
      <select class="input" bind:value={categoryFilter}>
        <option value="">Все категории</option>
        {#each categories as c}<option value={c.id}>{c.name}</option>{/each}
      </select>
    </div>
    {#if users.length > 1}
      <div class="filter-row">
        <select class="input" bind:value={userFilter}>
          <option value="">Все участники</option>
          {#each users as u}<option value={u.id}>{u.name}</option>{/each}
        </select>
        <label class="check"><input type="checkbox" bind:checked={allTime} disabled={usingDateRange} /> За всё время</label>
      </div>
    {:else}
      <label class="check"><input type="checkbox" bind:checked={allTime} disabled={usingDateRange} /> За всё время</label>
    {/if}

    <div class="filter-row date-row">
      <label class="date-field">
        <span>С</span>
        <input class="input" type="date" bind:value={dateFrom} max={dateTo || undefined} aria-label="Дата с" />
      </label>
      <label class="date-field">
        <span>По</span>
        <input class="input" type="date" bind:value={dateTo} min={dateFrom || undefined} aria-label="Дата по" />
      </label>
      {#if usingDateRange}
        <button class="btn-ghost btn-sm clear-dates" onclick={clearDates} aria-label="Сбросить даты"><i class="ti ti-x"></i></button>
      {/if}
    </div>
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
      {#each items as t (t.id)}
        {@const cat = categoryIcon(t)}
        <div class="tx-wrap">
          <button class="tx" onclick={() => (revealedId = revealedId === t.id ? null : t.id)}>
            <span class="tx-cat">
              {#if cat}<i class="ti {cat.icon}" style="color:{cat.color}"></i>{/if}
              {t.category_name ?? (t.type === 'income' ? 'Доход' : '—')}
            </span>
            <span class="tx-meta muted">{formatDate(t.date)}{t.user_name ? ` · ${t.user_name}` : ''}</span>
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

<style>
  .filters { gap: var(--space-2); }
  .filter-row { display: flex; gap: var(--space-2); }
  .filter-row .input { flex: 1; }
  .date-row { align-items: flex-end; }
  .date-field { flex: 1; display: flex; flex-direction: column; gap: 4px; font-size: var(--text-xs); color: var(--text-secondary); }
  .date-field .input { width: 100%; }
  .clear-dates { flex: 0 0 auto; align-self: stretch; }
  .sort-row button.active { color: var(--text-primary); }
  .check { display: flex; align-items: center; gap: 8px; font-size: var(--text-sm); color: var(--text-secondary); white-space: nowrap; }
  .tx-wrap { display: flex; gap: var(--space-2); align-items: stretch; }
  .tx { flex: 1; display: grid; grid-template-columns: 1fr auto; grid-template-rows: auto auto; gap: 2px 0; background: var(--bg-surface); border: none; border-radius: var(--radius-md); padding: var(--space-3); text-align: left; }
  .tx-cat { font-size: var(--text-base); display: flex; align-items: center; gap: 6px; }
  .tx-meta { font-size: var(--text-xs); }
  .tx-amt { grid-row: 1 / 3; grid-column: 2; align-self: center; }
  .tx-amt.income { color: var(--green); }
  .tx-actions { display: flex; flex-direction: column; gap: var(--space-1); }
  .tx-del { background: var(--red-bg); color: var(--red); border: none; border-radius: var(--radius-md); width: 56px; flex: 1; }
  .pager { display: flex; align-items: center; justify-content: space-between; padding-top: var(--space-2); }
  .small { font-size: var(--text-xs); }
</style>
