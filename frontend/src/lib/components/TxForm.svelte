<script lang="ts">
  import { api, type Category, type GroupSummary, type User, type Transaction } from '../api'
  import { period } from '../stores'
  import { money } from '../format'
  import MoneyInput from './MoneyInput.svelte'
  import ProgressBar from './ProgressBar.svelte'

  interface Props {
    onsubmitted: (tx: Transaction) => void
    existing?: Transaction
  }
  let { onsubmitted, existing }: Props = $props()

  let type = $state<'expense' | 'income'>(existing?.type === 'income' ? 'income' : 'expense')
  let amount = $state(existing?.amount ?? 0)
  let categoryId = $state<number | null>(existing?.category_id ?? null)
  let userId = $state<number | null>(existing?.user_id ?? null)
  let date = $state(existing?.date ?? new Date().toISOString().slice(0, 10))
  let comment = $state(existing?.comment ?? '')
  let showComment = $state(!!existing?.comment)
  let saving = $state(false)
  let error = $state('')

  let categories = $state<Category[]>([])
  let users = $state<User[]>([])
  // Map group name -> GroupSummary for remaining-in-bucket hint
  let groupMap = $state<Record<string, GroupSummary>>({})

  $effect(() => {
    load()
  })

  let loaded = false
  async function load() {
    if (loaded) return
    loaded = true
    // Snapshot period values before async call
    const { year, month } = $period
    const [cats, us, dash] = await Promise.all([
      api.categories(),
      api.users(),
      api.dashboard(year, month),
    ])
    categories = cats
    users = us
    if (us.length && userId === null) userId = us[0].id
    // Build group map from dashboard groups
    const m: Record<string, GroupSummary> = {}
    for (const g of dash.groups) {
      m[g.name] = g
    }
    groupMap = m
  }

  // Categories for income type
  let incomeCategories = $derived(categories.filter((c) => c.group === 'income' && !c.is_hidden))

  // Categories grouped for the expense form
  let needsCategories = $derived(categories.filter((c) => c.group === 'needs' && !c.is_hidden))
  let wantsCategories = $derived(categories.filter((c) => c.group === 'wants' && !c.is_hidden))
  let savingsCategories = $derived(categories.filter((c) => c.group === 'savings' && !c.is_hidden))

  // All visible non-income categories
  let expenseCategories = $derived(
    categories.filter((c) => c.group !== 'income' && !c.is_hidden),
  )

  // Reset selected category when switching type so it stays valid.
  let shownCategories = $derived(
    type === 'income' ? incomeCategories : expenseCategories,
  )
  $effect(() => {
    if (categories.length && categoryId && !shownCategories.some((c) => c.id === categoryId)) {
      categoryId = null
    }
  })

  // Derive the group of the currently selected category
  let selectedCategory = $derived(categories.find((c) => c.id === categoryId) ?? null)
  let selectedGroup = $derived<GroupSummary | null>(
    selectedCategory ? (groupMap[selectedCategory.group] ?? null) : null,
  )

  // Labels for bucket headers
  const GROUP_LABELS: Record<string, string> = {
    needs: 'Нужды',
    wants: 'Желания',
    savings: 'Сбережения',
  }

  async function submit() {
    if (amount <= 0) {
      error = 'Введите сумму'
      return
    }
    saving = true
    error = ''
    try {
      const body = { type, amount, category_id: categoryId, user_id: userId, date, comment: comment || null }
      const tx = existing ? await api.updateTransaction(existing.id, body) : await api.createTransaction(body)
      onsubmitted(tx)
    } catch (e) {
      error = (e as Error).message
      saving = false
    }
  }
</script>

<div class="type-tabs" role="tablist">
  {#each [['expense', 'Расход'], ['income', 'Доход']] as [t, label]}
    <button
      role="tab"
      aria-selected={type === t}
      class="type-tab"
      class:active={type === t}
      onclick={() => (type = t as typeof type)}
    >
      {label}
    </button>
  {/each}
</div>

<MoneyInput bind:value={amount} />

{#if type === 'expense'}
  <!-- Grouped expense categories: Нужды, Желания, Сбережения -->
  {#each [['needs', needsCategories], ['wants', wantsCategories], ['savings', savingsCategories]] as [group, cats]}
    {#if (cats as Category[]).length > 0}
      <div class="group-section">
        <span class="group-label">{GROUP_LABELS[group as string]}</span>
        <div class="cats" role="listbox" aria-label={GROUP_LABELS[group as string]}>
          {#each (cats as Category[]) as c (c.id)}
            <button
              role="option"
              aria-selected={categoryId === c.id}
              class="cat-chip"
              class:active={categoryId === c.id}
              style="--c: {c.color}"
              onclick={() => (categoryId = c.id)}
            >
              <i class="ti {c.icon}"></i>
              <span>{c.name}</span>
            </button>
          {/each}
        </div>
      </div>
    {/if}
  {/each}

  <!-- Remaining-in-bucket hint when a needs/wants category is selected -->
  {#if selectedGroup && categoryId !== null}
    <div class="bucket-hint">
      <div class="bucket-hint-text">
        <span>осталось в {GROUP_LABELS[selectedCategory!.group]}:</span>
        <span class="bucket-amounts">
          <strong>{money(selectedGroup.remaining)}</strong>
          <span class="of-text">из {money(selectedGroup.limit)}</span>
        </span>
      </div>
      <ProgressBar spent={selectedGroup.spent} limit={selectedGroup.limit} />
    </div>
  {/if}
{:else}
  <!-- Income: flat list of income categories -->
  <div class="cats" role="listbox" aria-label="Категория">
    {#each incomeCategories as c (c.id)}
      <button
        role="option"
        aria-selected={categoryId === c.id}
        class="cat-chip"
        class:active={categoryId === c.id}
        style="--c: {c.color}"
        onclick={() => (categoryId = c.id)}
      >
        <i class="ti {c.icon}"></i>
        <span>{c.name}</span>
      </button>
    {/each}
  </div>
{/if}

{#if users.length > 1}
  <div class="who">
    {#each users as u}
      <button class="who-btn" class:active={userId === u.id} onclick={() => (userId = u.id)}>
        {u.name}
      </button>
    {/each}
  </div>
{/if}

<div class="meta-row">
  <input class="input" type="date" bind:value={date} aria-label="Дата" />
  <button class="btn-ghost btn-sm" onclick={() => (showComment = !showComment)}>
    <i class="ti ti-message"></i> Комментарий
  </button>
</div>
{#if showComment}
  <input class="input" placeholder="Комментарий" bind:value={comment} />
{/if}

{#if error}<p class="err">{error}</p>{/if}

<button class="btn btn-primary" onclick={submit} disabled={saving}>
  {saving ? 'Сохраняю…' : existing ? 'Сохранить' : type === 'income' ? 'Добавить и распределить' : 'Записать'}
</button>

<style>
  .type-tabs { display: flex; gap: var(--space-2); }
  .type-tab {
    flex: 1;
    background: var(--bg-surface);
    border: none;
    color: var(--text-secondary);
    padding: 10px;
    border-radius: var(--radius-sm);
    font-size: var(--text-sm);
  }
  .type-tab.active { background: var(--blue); color: #fff; }

  .group-section { display: flex; flex-direction: column; gap: var(--space-1); }
  .group-label {
    font-size: var(--text-xs);
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding: 0 2px;
  }

  .cats {
    display: flex;
    gap: var(--space-2);
    overflow-x: auto;
    padding-bottom: var(--space-2);
    scrollbar-width: none;
  }
  .cats::-webkit-scrollbar { display: none; }
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

  .bucket-hint {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    padding: var(--space-2) var(--space-3);
    background: var(--bg-surface);
    border-radius: var(--radius-sm);
  }
  .bucket-hint-text {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    font-size: var(--text-sm);
    color: var(--text-secondary);
  }
  .bucket-amounts { display: flex; align-items: baseline; gap: var(--space-1); }
  .bucket-amounts strong { color: var(--text-primary); }
  .of-text { font-size: var(--text-xs); color: var(--text-secondary); }

  .who { display: flex; gap: var(--space-2); }
  .who-btn {
    flex: 1;
    background: var(--bg-surface);
    border: 1px solid transparent;
    border-radius: 999px;
    color: var(--text-secondary);
    padding: 10px;
    font-size: var(--text-sm);
  }
  .who-btn.active { border-color: var(--blue); color: var(--text-primary); }
  .meta-row { display: flex; gap: var(--space-2); align-items: center; }
  .meta-row .input { flex: 1; }
  .err { color: var(--red); font-size: var(--text-sm); margin: 0; }
</style>
