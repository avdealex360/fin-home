<script lang="ts">
  import { api, type Transaction, type Category, type User } from '../lib/api'
  import { period, dataVersion, invalidate, showToast, showHelp } from '../lib/stores'
  import { money, formatDate, monthName } from '../lib/format'
  import Loader from '../lib/components/Loader.svelte'
  import BottomSheet from '../lib/components/BottomSheet.svelte'
  import TxForm from '../lib/components/TxForm.svelte'

  const PAGE_SIZE = 20
  const GROUP_LABELS: Record<string, string> = {
    needs: 'Нужды', wants: 'Желания', savings: 'Сбережения', income: 'Доходы',
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

  let usingDateRange = $derived(!!dateFrom || !!dateTo)

  let categoryFilterLabel = $derived(
    categoryIds.length === 0
      ? 'Все категории'
      : categoryIds.length === 1
        ? (categories.find((c) => c.id === categoryIds[0])?.name ?? '1 категория')
        : `${categoryIds.length} категории`,
  )

  let activeCount = $derived(
    (typeFilter ? 1 : 0) + (groupFilter ? 1 : 0) + (userFilter ? 1 : 0) +
    (categoryIds.length ? 1 : 0) + (usingDateRange ? 1 : 0),
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
  function clearCategories() { categoryIds = [] }
  function clearDates() { dateFrom = ''; dateTo = ''; activePreset = '' }
  function resetAll() {
    typeFilter = ''; groupFilter = ''; userFilter = ''; categoryIds = []
    clearDates(); customOpen = false
  }

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
      const y = new Date(now); y.setDate(y.getDate() - 1)
      dateFrom = dateTo = toISO(y)
    } else if (key === 'week') {
      const day = (now.getDay() + 6) % 7
      const monday = new Date(now); monday.setDate(now.getDate() - day)
      dateFrom = toISO(monday); dateTo = toISO(now)
    } else if (key === 'month') {
      dateFrom = toISO(new Date(now.getFullYear(), now.getMonth(), 1)); dateTo = toISO(now)
    } else if (key === 'year') {
      dateFrom = toISO(new Date(now.getFullYear(), 0, 1)); dateTo = toISO(now)
    }
    customOpen = false
  }

  function onManualDate() { activePreset = 'custom' }
  function categoryIcon(t: Transaction) { return categories.find((c) => c.id === t.category_id) }
  function toggleSort(field: 'date' | 'amount') {
    if (sortBy === field) sortDir = sortDir === 'asc' ? 'desc' : 'asc'
    else { sortBy = field; sortDir = 'desc' }
  }
  function monthKey(dateStr: string) { return dateStr.slice(0, 7) }
  function monthLabel(dateStr: string) {
    const d = new Date(dateStr)
    return `${monthName(d.getMonth() + 1)} ${d.getFullYear()}`
  }
  function dayLabel(dateStr: string) {
    const now = new Date()
    if (dateStr === toISO(now)) return 'Сегодня'
    const y = new Date(now); y.setDate(y.getDate() - 1)
    if (dateStr === toISO(y)) return 'Вчера'
    return formatDate(dateStr)
  }

  function openEdit(t: Transaction) { revealedId = null; editingTx = t }
  function onEdited() { editingTx = null; invalidate(); showToast('Операция изменена') }

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

  // Summary rail — totals for the whole selection, not just the visible page.
  let periodExpense = $derived(Object.values(monthTotals).reduce((s, v) => s + v, 0))
  let uncategorised = $derived(items.filter((t) => t.type === 'expense' && !t.category_id))
</script>

<div class="page">
  <div class="cols">
    <div class="col-wide stack">
      <!-- Filters -->
      <div class="card filters">
        <div class="filter-row">
          <select class="input" bind:value={typeFilter} aria-label="Тип операции">
            <option value="">Все типы</option>
            <option value="expense">Расход</option>
            <option value="income">Доход</option>
          </select>
          <button class="input cat-trigger" onclick={() => (catSheetOpen = true)}>
            <span>{categoryFilterLabel}</span>
            <i class="ti ti-chevron-down"></i>
          </button>
          {#if users.length > 1}
            <select class="input" bind:value={userFilter} aria-label="Участник">
              <option value="">Все участники</option>
              {#each users as u}<option value={u.id}>{u.name}</option>{/each}
            </select>
          {/if}
        </div>

        <div class="chips-row">
          {#each [['', 'Все'], ['needs', 'Нужды'], ['wants', 'Желания'], ['savings', 'Сбережения']] as [g, label]}
            <button class="fchip" class:active={groupFilter === g} onclick={() => (groupFilter = g as typeof groupFilter)}>{label}</button>
          {/each}
        </div>

        <div class="chips-row">
          {#each [['today', 'Сегодня'], ['yesterday', 'Вчера'], ['week', 'Неделя'], ['month', 'Месяц'], ['year', 'Год']] as [key, label]}
            <button class="fchip" class:active={activePreset === key} onclick={() => applyPreset(key as 'today')}>{label}</button>
          {/each}
          <button class="fchip" class:active={activePreset === 'custom'} aria-label="Свой период" onclick={() => (customOpen = !customOpen)}>
            <i class="ti ti-calendar"></i>
          </button>
          <span class="spacer"></span>
          <button class="fchip" class:active={sortBy === 'date'} onclick={() => toggleSort('date')}>
            Дата {sortBy === 'date' ? (sortDir === 'asc' ? '↑' : '↓') : ''}
          </button>
          <button class="fchip" class:active={sortBy === 'amount'} onclick={() => toggleSort('amount')}>
            Сумма {sortBy === 'amount' ? (sortDir === 'asc' ? '↑' : '↓') : ''}
          </button>
          {#if activeCount > 0}
            <button class="fchip reset" onclick={resetAll}><i class="ti ti-x"></i> Сбросить {activeCount}</button>
          {/if}
        </div>

        {#if customOpen || activePreset === 'custom'}
          <div class="filter-row date-row">
            <label class="date-field"><span>С</span>
              <input class="input" type="date" bind:value={dateFrom} max={dateTo || undefined} aria-label="Дата с" oninput={onManualDate} />
            </label>
            <label class="date-field"><span>По</span>
              <input class="input" type="date" bind:value={dateTo} min={dateFrom || undefined} aria-label="Дата по" oninput={onManualDate} />
            </label>
            {#if usingDateRange}
              <button class="fchip" onclick={clearDates} aria-label="Сбросить даты"><i class="ti ti-x"></i></button>
            {/if}
          </div>
        {/if}
      </div>

      <!-- List -->
      {#if !loaded}
        <Loader />
      {:else if items.length === 0}
        <div class="card empty">
          <i class="ti ti-search-off"></i>
          <div>
            <div class="empty-title">Операций не найдено</div>
            <div class="muted small">Попробуйте снять часть фильтров или выбрать другой месяц.</div>
          </div>
          {#if activeCount > 0}<button class="btn btn-secondary btn-sm" onclick={resetAll}>Сбросить фильтры</button>{/if}
        </div>
      {:else}
        <div class="list card">
          {#each items as t, i (t.id)}
            {@const cat = categoryIcon(t)}
            {@const prevDate = i > 0 ? items[i - 1].date : null}
            {@const showMonthHeader = sortBy === 'date' && (i === 0 || monthKey(prevDate!) !== monthKey(t.date))}
            {@const showDayHeader = sortBy === 'date' && (i === 0 || prevDate !== t.date)}

            {#if showMonthHeader}
              <div class="month-header">
                <span>{monthLabel(t.date)}</span>
                {#if monthTotals[monthKey(t.date)]}<span class="num">− {money(monthTotals[monthKey(t.date)])} ₽</span>{/if}
              </div>
            {/if}
            {#if showDayHeader}
              <div class="day-header">
                <span>{dayLabel(t.date)}</span>
                {#if dayTotals[t.date]}<span class="num">итого за день − {money(dayTotals[t.date])} ₽</span>{/if}
              </div>
            {/if}

            <div class="tx" class:open={revealedId === t.id}>
              <span class="tx-ic" style="background: {(cat?.color ?? '#5b6478')}22; color: {cat?.color ?? 'var(--text-muted)'}">
                <i class="ti {cat?.icon ?? (t.type === 'income' ? 'ti-arrow-down-left' : 'ti-circle')}"></i>
              </span>
              <button class="tx-main" onclick={() => (revealedId = revealedId === t.id ? null : t.id)}>
                <span class="tx-name">{t.category_name ?? (t.type === 'income' ? 'Доход' : 'Без категории')}</span>
                <span class="tx-meta">
                  {sortBy === 'date' ? (t.user_name ?? '') : formatDate(t.date) + (t.user_name ? ` · ${t.user_name}` : '')}{t.comment ? ` · ${t.comment}` : ''}
                </span>
              </button>
              <span class="num tx-amt" class:income={t.type === 'income'}>
                {t.type === 'income' ? '+' : '−'} {money(t.amount)} ₽
              </span>
              <span class="tx-actions">
                <button aria-label="Изменить" onclick={() => openEdit(t)}><i class="ti ti-pencil"></i></button>
                <button class="danger" aria-label="Удалить" onclick={() => del(t)}><i class="ti ti-trash"></i></button>
              </span>
            </div>
          {/each}
        </div>

        <div class="pager">
          <button class="btn btn-secondary btn-sm" disabled={offset === 0} onclick={() => (offset = Math.max(0, offset - PAGE_SIZE))}>
            <i class="ti ti-chevron-left"></i> Назад
          </button>
          <span class="muted small num">{from}–{to} из {total}</span>
          <button class="btn btn-secondary btn-sm" disabled={to >= total} onclick={() => (offset += PAGE_SIZE)}>
            Далее <i class="ti ti-chevron-right"></i>
          </button>
        </div>
      {/if}
    </div>

    <!-- Summary rail -->
    <aside class="col stack">
      <div class="card">
        <h2 class="card-title">Итого по выборке</h2>
        {#if $showHelp}
          <p class="explain">Суммы считаются по всем операциям выборки, а не только по видимой странице.</p>
        {/if}
        <div class="stack" style="margin-top: 14px; gap: 12px">
          <div class="row"><span class="small muted">Расходы</span><span class="num big red">{money(periodExpense)} ₽</span></div>
          <div class="row" style="padding-top: 12px; border-top: 1px solid var(--line)">
            <span class="small muted">Операций</span><span class="num big">{total}</span>
          </div>
          <div class="row">
            <span class="small muted">Средний чек</span>
            <span class="num big">{total > 0 ? money(periodExpense / total) : 0} ₽</span>
          </div>
        </div>
      </div>

      {#if uncategorised.length}
        <div class="card">
          <h2 class="card-title">Нужно уточнить</h2>
          {#if $showHelp}
            <p class="explain">Пока у операции нет категории, она не попадает в лимиты и в аналитику.</p>
          {/if}
          <div class="stack" style="margin-top: 12px; gap: 10px">
            {#each uncategorised.slice(0, 5) as t}
              <button class="review" onclick={() => openEdit(t)}>
                <span class="review-main">
                  <span class="small">{t.comment || 'Без описания'}</span>
                  <span class="dim tiny">{formatDate(t.date)}{t.user_name ? ` · ${t.user_name}` : ''}</span>
                </span>
                <span class="num small">− {money(t.amount)} ₽</span>
              </button>
            {/each}
          </div>
        </div>
      {/if}

      <div class="card">
        <h2 class="card-title">Экспорт</h2>
        <div class="stack" style="margin-top: 12px; gap: 8px">
          <a class="btn btn-secondary" href="/api/settings/export/csv">Скачать CSV</a>
          <a class="btn btn-ghost" href="/api/settings/export/json">Скачать JSON</a>
        </div>
      </div>
    </aside>
  </div>
</div>

<BottomSheet open={!!editingTx} title="Изменить операцию" onclose={() => (editingTx = null)}>
  {#snippet children()}
    {#if editingTx}<TxForm existing={editingTx} onsubmitted={onEdited} />{/if}
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
                role="option" aria-selected={categoryIds.includes(c.id)}
                class="cat-chip" class:active={categoryIds.includes(c.id)}
                style="--c: {c.color}" onclick={() => toggleCategory(c.id)}
              >
                <i class="ti {c.icon}"></i><span>{c.name}</span>
              </button>
            {/each}
          </div>
        </div>
      {/if}
    {/each}
    <div class="sheet-actions">
      <button class="btn btn-ghost btn-sm" onclick={clearCategories} disabled={!categoryIds.length}>Сбросить</button>
      <button class="btn btn-primary" onclick={() => (catSheetOpen = false)}>
        Готово {categoryIds.length ? `(${categoryIds.length})` : ''}
      </button>
    </div>
  {/snippet}
</BottomSheet>

<style>
  .filters { display: flex; flex-direction: column; gap: var(--space-3); padding: var(--space-4); }
  .filter-row { display: flex; gap: var(--space-2); flex-wrap: wrap; }
  .filter-row .input { flex: 1 1 160px; min-width: 0; }
  .cat-trigger { display: flex; align-items: center; justify-content: space-between; gap: 8px; text-align: left; color: var(--text-primary); }

  .chips-row { display: flex; gap: var(--space-2); flex-wrap: wrap; align-items: center; }
  .chips-row .spacer { flex: 1 1 auto; }
  .fchip {
    height: 34px; padding: 0 13px; border-radius: 999px;
    border: 1px solid var(--line); background: var(--bg-elevated);
    color: var(--text-secondary); font-size: 12.5px; font-weight: 600;
    display: inline-flex; align-items: center; gap: 5px;
  }
  .fchip:hover { color: var(--text-primary); }
  .fchip.active { background: rgba(106, 155, 255, 0.16); color: var(--blue); border-color: var(--blue-border); }
  .fchip.reset { color: var(--red); }

  .date-row { align-items: flex-end; }
  .date-field { flex: 1 1 150px; min-width: 0; display: flex; flex-direction: column; gap: 4px; font-size: var(--text-xs); color: var(--text-secondary); }
  .date-field .input { width: 100%; font-size: var(--text-sm); padding: 10px; }

  .list { padding: var(--space-2) var(--space-4) var(--space-3); }
  .month-header, .day-header { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; }
  .month-header {
    font-size: var(--text-xs); font-weight: 600; letter-spacing: 0.05em; text-transform: uppercase;
    color: var(--text-secondary); padding: var(--space-4) 0 var(--space-1);
  }
  .month-header:first-child { padding-top: var(--space-2); }
  .month-header .num { text-transform: none; letter-spacing: -0.02em; }
  .day-header {
    position: sticky; top: var(--header-h); z-index: 5;
    background: var(--bg-surface); font-size: var(--text-xs); color: var(--text-muted);
    padding: var(--space-3) 0 var(--space-2);
  }

  .tx { display: flex; align-items: center; gap: var(--space-3); padding: 10px 0; border-top: 1px solid var(--line); }
  .tx-ic { width: 34px; height: 34px; flex: 0 0 34px; border-radius: 11px; display: grid; place-items: center; font-size: 17px; }
  .tx-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; background: none; border: none; padding: 0; text-align: left; }
  .tx-name { font-size: 14px; }
  .tx-meta { font-size: 11.5px; color: var(--text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .tx-amt { font-size: 14px; font-weight: 500; white-space: nowrap; }
  .tx-amt.income { color: var(--green); }
  .tx-actions { display: flex; gap: 2px; opacity: 0; transition: opacity var(--transition-fast); }
  .tx:hover .tx-actions, .tx.open .tx-actions { opacity: 1; }
  .tx-actions button {
    width: 32px; height: 32px; border: none; border-radius: 9px;
    background: transparent; color: var(--text-muted); display: grid; place-items: center;
  }
  .tx-actions button:hover { background: var(--bg-elevated); color: var(--text-primary); }
  .tx-actions .danger:hover { background: var(--red-bg); color: var(--red); }
  /* Touch: actions are always visible, no hover to rely on. */
  @media (hover: none) { .tx-actions { opacity: 1; } }

  .pager { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); }
  .empty { display: flex; align-items: center; gap: var(--space-4); flex-wrap: wrap; }
  .empty i { font-size: 28px; color: var(--text-muted); }
  .empty-title { font-size: 14px; font-weight: 600; }

  .big { font-size: 16px; font-weight: 600; }
  .red { color: var(--red); }
  .small { font-size: var(--text-sm); }
  .tiny { font-size: var(--text-xs); }

  .review {
    display: flex; align-items: center; gap: 10px; width: 100%;
    padding: 10px 12px; border-radius: var(--radius-md);
    background: var(--bg-elevated); border: none; color: inherit; text-align: left;
  }
  .review-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }

  .group-section { display: flex; flex-direction: column; gap: var(--space-1); }
  .group-label { font-size: var(--text-xs); color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.06em; padding: 0 2px; }
  .cats-grid { display: flex; flex-wrap: wrap; gap: var(--space-2); }
  .cat-chip {
    display: flex; flex-direction: column; align-items: center; gap: 4px;
    width: 72px; padding: 10px 4px; background: var(--bg-surface);
    border: 1px solid transparent; border-radius: var(--radius-sm);
    color: var(--text-secondary); font-size: var(--text-xs);
  }
  .cat-chip i { font-size: 22px; color: var(--c); }
  .cat-chip span { text-align: center; line-height: 1.1; }
  .cat-chip.active { border-color: var(--c); background: var(--bg-elevated); color: var(--text-primary); }
  .sheet-actions { display: flex; gap: var(--space-2); justify-content: space-between; margin-top: var(--space-4); }
</style>
