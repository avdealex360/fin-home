<script lang="ts">
  import { api, type Category, type User, type Transaction } from '../api'
  import MoneyInput from './MoneyInput.svelte'

  interface Props {
    onsubmitted: (tx: Transaction) => void
  }
  let { onsubmitted }: Props = $props()

  let type = $state<'expense' | 'income' | 'transfer'>('expense')
  let amount = $state(0)
  let categoryId = $state<number | null>(null)
  let userId = $state<number | null>(null)
  let date = $state(new Date().toISOString().slice(0, 10))
  let comment = $state('')
  let showComment = $state(false)
  let saving = $state(false)
  let error = $state('')

  let categories = $state<Category[]>([])
  let users = $state<User[]>([])

  $effect(() => {
    load()
  })

  let loaded = false
  async function load() {
    if (loaded) return
    loaded = true
    const [cats, us] = await Promise.all([api.categories(), api.users()])
    categories = cats
    users = us
    if (us.length) userId = us[0].id
  }

  let shownCategories = $derived(
    categories.filter((c) =>
      type === 'income' ? c.group === 'income' : c.group !== 'income',
    ),
  )

  // Reset selected category when switching type so it stays valid.
  $effect(() => {
    if (categoryId && !shownCategories.some((c) => c.id === categoryId)) {
      categoryId = null
    }
  })

  async function submit() {
    if (amount <= 0) {
      error = 'Введите сумму'
      return
    }
    saving = true
    error = ''
    try {
      const tx = await api.createTransaction({
        type,
        amount,
        category_id: categoryId,
        user_id: userId,
        date,
        comment: comment || null,
      })
      onsubmitted(tx)
    } catch (e) {
      error = (e as Error).message
      saving = false
    }
  }
</script>

<div class="type-tabs" role="tablist">
  {#each [['expense', 'Расход'], ['income', 'Доход'], ['transfer', 'Перевод']] as [t, label]}
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

<div class="cats" role="listbox" aria-label="Категория">
  {#each shownCategories as c (c.id)}
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
  {saving ? 'Сохраняю…' : type === 'income' ? 'Добавить и распределить' : 'Записать'}
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
