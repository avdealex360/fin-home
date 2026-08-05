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
  let pickingId = $state<number | null>(null)

  // Curated Tabler icon names (webfont classes without the leading "ti ")
  const ICONS = [
    'ti-home', 'ti-shopping-cart', 'ti-basket', 'ti-car', 'ti-bus', 'ti-plane',
    'ti-gas-station', 'ti-bike', 'ti-heart-rate-monitor', 'ti-pill', 'ti-stethoscope',
    'ti-dental', 'ti-paw', 'ti-wifi', 'ti-phone', 'ti-bolt', 'ti-droplet', 'ti-flame',
    'ti-receipt', 'ti-credit-card', 'ti-tools-kitchen-2', 'ti-coffee', 'ti-pizza',
    'ti-beer', 'ti-device-tv', 'ti-device-gamepad-2', 'ti-music', 'ti-movie',
    'ti-book', 'ti-school', 'ti-hanger', 'ti-shirt', 'ti-scissors', 'ti-activity',
    'ti-barbell', 'ti-gift', 'ti-baby-carriage', 'ti-armchair', 'ti-tool',
    'ti-camera', 'ti-palette', 'ti-heart', 'ti-star', 'ti-shield', 'ti-building-bank',
    'ti-pig-money', 'ti-wallet', 'ti-cash', 'ti-coin', 'ti-chart-line',
    'ti-briefcase', 'ti-circle-plus', 'ti-arrow-down-circle', 'ti-inbox', 'ti-tag',
  ]

  async function setIcon(c: Category, icon: string) {
    // Empty string resets the override back to the name-based default
    await api.updateCategory(c.id, { name: c.name, group: c.group, icon })
    pickingId = null
    invalidate()
  }

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
                  <button
                    class="icon-btn"
                    onclick={() => (pickingId = pickingId === c.id ? null : c.id)}
                    aria-label="Сменить иконку"
                  >
                    <i class="ti {c.icon}" style="color:{c.color}"></i>
                  </button>
                  {c.name}
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
            {#if pickingId === c.id}
              <div class="icon-picker">
                {#each ICONS as ic}
                  <button
                    class="pick"
                    class:active={ic === c.icon}
                    onclick={() => setIcon(c, ic)}
                    aria-label={ic}
                  >
                    <i class="ti {ic}"></i>
                  </button>
                {/each}
                <button class="pick reset" onclick={() => setIcon(c, '')} aria-label="Сбросить иконку">
                  <i class="ti ti-restore"></i>
                </button>
              </div>
            {/if}
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
  .icon-btn {
    background: var(--bg-elevated);
    border: none;
    border-radius: var(--radius-sm);
    width: 32px;
    height: 32px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: var(--text-lg);
    cursor: pointer;
    flex-shrink: 0;
  }
  .icon-picker {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(40px, 1fr));
    gap: var(--space-1);
    padding: var(--space-2) 0;
    border-bottom: 1px solid var(--line, rgba(255, 255, 255, 0.08));
  }
  .pick {
    background: none;
    border: 1px solid transparent;
    border-radius: var(--radius-sm);
    height: 40px;
    font-size: var(--text-lg);
    color: var(--text-secondary);
    cursor: pointer;
  }
  .pick:hover { background: var(--bg-elevated); }
  .pick.active { border-color: var(--blue); color: var(--blue); }
  .pick.reset { color: var(--red); }
  .actions { display: flex; gap: var(--space-2); }
  .danger { color: var(--red); }
  .hidden-row { opacity: 0.55; }
  .small { font-size: var(--text-xs); }
  .add-row { display: flex; gap: var(--space-2); align-items: center; margin-top: var(--space-2); }
  .add-row .input { flex: 1; }
  .btn-add { background: var(--blue); color: #fff; border: none; border-radius: var(--radius-sm); width: 44px; height: 44px; flex-shrink: 0; }
</style>
