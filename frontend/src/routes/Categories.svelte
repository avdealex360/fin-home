<script lang="ts">
  import { api, type Category } from '../lib/api'
  import { dataVersion, invalidate, showToast } from '../lib/stores'
  import Loader from '../lib/components/Loader.svelte'

  let categories = $state<Category[]>([])
  let loaded = $state(false)
  let adding = $state<string | null>(null)
  let newName = $state('')
  let editingId = $state<number | null>(null)
  let editingName = $state('')

  const GROUPS: { key: Category['group']; label: string }[] = [
    { key: 'needs', label: 'Нужды' },
    { key: 'wants', label: 'Желания' },
    { key: 'savings', label: 'Сбережения' },
    { key: 'income', label: 'Доход' },
  ]

  $effect(() => {
    void $dataVersion
    load()
  })
  async function load() {
    categories = await api.categories(undefined, true)
    loaded = true
  }

  function byGroup(g: string) {
    return categories.filter((c) => c.group === g)
  }

  async function addCategory(group: string) {
    if (!newName.trim()) return
    await api.createCategory({ name: newName.trim(), group: group as Category['group'] })
    newName = ''
    adding = null
    invalidate()
    showToast('Категория добавлена')
  }

  function startEdit(c: Category) {
    editingId = c.id
    editingName = c.name
  }
  async function saveEdit(c: Category) {
    if (!editingName.trim()) return
    await api.updateCategory(c.id, { name: editingName.trim(), group: c.group })
    editingId = null
    invalidate()
  }

  async function removeCategory(c: Category) {
    if (!confirm(`Удалить категорию «${c.name}»? Если в ней уже были операции — она не удалится, а скроется (история и отчёты не пострадают).`)) return
    const r = await api.deleteCategory(c.id)
    invalidate()
    showToast(r.hidden ? 'Категория использовалась в операциях — скрыта, история сохранена' : 'Категория удалена')
  }

  async function restoreCategory(c: Category) {
    await api.updateCategory(c.id, { name: c.name, group: c.group, is_hidden: false })
    invalidate()
    showToast('Категория восстановлена')
  }
</script>

<div class="page-header"><h1>Категории</h1></div>

{#if !loaded}
  <Loader />
{:else}
  <div class="page">
    {#each GROUPS as g}
      <section>
        <div class="row section-label">
          <span>{g.label}</span>
          <button class="btn-ghost btn-sm" onclick={() => (adding = adding === g.key ? null : g.key)} aria-label="Добавить категорию">
            <i class="ti ti-plus"></i>
          </button>
        </div>
        <div class="card stack">
          {#each byGroup(g.key) as c (c.id)}
            <div class="row" class:hidden-row={c.is_hidden}>
              {#if editingId === c.id}
                <input class="input" bind:value={editingName} />
                <button class="btn-ghost btn-sm" onclick={() => saveEdit(c)} aria-label="Сохранить"><i class="ti ti-check"></i></button>
              {:else}
                <span class="cat-name">
                  <i class="ti {c.icon}" style="color:{c.color}"></i> {c.name}
                  {#if c.is_hidden}<span class="muted small"> · скрыта</span>{/if}
                </span>
                <span class="actions">
                  {#if c.is_hidden}
                    <button class="btn-ghost btn-sm" onclick={() => restoreCategory(c)} aria-label="Восстановить"><i class="ti ti-arrow-back-up"></i></button>
                  {:else}
                    <button class="btn-ghost btn-sm" onclick={() => startEdit(c)} aria-label="Переименовать"><i class="ti ti-pencil"></i></button>
                    <button class="btn-ghost btn-sm danger" onclick={() => removeCategory(c)} aria-label="Удалить"><i class="ti ti-trash"></i></button>
                  {/if}
                </span>
              {/if}
            </div>
          {:else}
            <p class="muted">Пока нет категорий.</p>
          {/each}
          {#if adding === g.key}
            <div class="add-row">
              <input class="input" placeholder="Название" bind:value={newName} />
              <button class="btn-add" onclick={() => addCategory(g.key)} aria-label="Добавить"><i class="ti ti-plus"></i></button>
            </div>
          {/if}
        </div>
      </section>
    {/each}
  </div>
{/if}

<style>
  section { display: flex; flex-direction: column; gap: var(--space-2); }
  .cat-name { display: flex; align-items: center; gap: 6px; }
  .actions { display: flex; gap: var(--space-2); }
  .danger { color: var(--red); }
  .hidden-row { opacity: 0.55; }
  .small { font-size: var(--text-xs); }
  .add-row { display: flex; gap: var(--space-2); align-items: center; margin-top: var(--space-2); }
  .add-row .input { flex: 1; }
  .btn-add { background: var(--blue); color: #fff; border: none; border-radius: var(--radius-sm); width: 44px; height: 44px; flex-shrink: 0; }
</style>
