<script lang="ts">
  import { api, type AllocationView } from '../api'
  import { money } from '../format'

  interface Props {
    txId: number
    ondone: () => void
  }
  let { txId, ondone }: Props = $props()

  let view = $state<AllocationView | null>(null)
  // key = `${level}:${kind}:${id}` -> amount
  let amounts = $state<Record<string, number>>({})
  let saving = $state(false)

  const keyOf = (level: number, kind: string, id: number) => `${level}:${kind}:${id}`

  $effect(() => {
    init()
  })
  let loaded = false
  async function init() {
    if (loaded) return
    loaded = true
    const v = await api.allocationView(txId)
    view = v
    // Prefill from existing allocation if present, else 0.
    const next: Record<string, number> = {}
    for (const lvl of v.levels) {
      for (const it of lvl.items) {
        next[keyOf(lvl.level, it.kind, it.id)] = 0
      }
    }
    for (const ex of v.existing) {
      const kind = ex.fund_id ? 'fund' : 'category'
      const id = ex.fund_id ?? ex.category_id ?? 0
      next[keyOf(ex.allocation_level, kind, id)] = ex.amount
    }
    amounts = next
  }

  let assigned = $derived(Object.values(amounts).reduce((s, n) => s + (n || 0), 0))
  let remaining = $derived((view?.transaction.amount ?? 0) - assigned)

  function autoFill() {
    if (!view) return
    const next = { ...amounts }
    for (const lvl of view.levels) {
      for (const it of lvl.items) {
        next[keyOf(lvl.level, it.kind, it.id)] = Math.round(it.suggested_amount)
      }
    }
    amounts = next
  }

  async function save() {
    if (!view) return
    saving = true
    const allocations: unknown[] = []
    for (const lvl of view.levels) {
      for (const it of lvl.items) {
        const amt = amounts[keyOf(lvl.level, it.kind, it.id)] || 0
        if (amt <= 0) continue
        allocations.push({
          category_id: it.kind === 'category' ? it.id : null,
          fund_id: it.kind === 'fund' ? it.id : null,
          amount: amt,
          allocation_level: lvl.level,
        })
      }
    }
    await api.allocate(txId, allocations)
    ondone()
  }
</script>

{#if !view}
  <div class="spinner-wrap">Загрузка…</div>
{:else}
  <div class="counter" class:done={Math.abs(remaining) < 1}>
    <span class="counter-label">К распределению</span>
    <span class="counter-value num">{money(remaining)} ₽</span>
  </div>

  <button class="btn btn-secondary" onclick={autoFill}>
    <i class="ti ti-wand"></i> Распределить по плану автоматически
  </button>

  <div class="levels">
    {#each view.levels as lvl}
      {#if lvl.items.length}
        <div class="level">
          <div class="section-label">{lvl.label}</div>
          {#each lvl.items as it}
            <div class="alloc-row">
              <span class="alloc-name">
                {#if it.kind === 'fund'}<i class="ti ti-pig-money"></i>{/if}
                {it.name}
              </span>
              <input
                class="input alloc-input num"
                inputmode="numeric"
                value={amounts[keyOf(lvl.level, it.kind, it.id)] || ''}
                oninput={(e) =>
                  (amounts[keyOf(lvl.level, it.kind, it.id)] =
                    parseFloat((e.target as HTMLInputElement).value) || 0)}
              />
            </div>
          {/each}
        </div>
      {/if}
    {/each}
  </div>

  <button class="btn btn-primary" onclick={save} disabled={saving}>
    {saving ? 'Сохраняю…' : remaining > 0 ? `Сохранить (остаток ${money(remaining)} ₽)` : 'Готово'}
  </button>
{/if}

<style>
  .counter {
    text-align: center;
    padding: var(--space-3);
    border-radius: var(--radius-md);
    background: var(--blue-bg);
    border: 1px solid var(--blue-border);
  }
  .counter.done { background: var(--green-bg); border-color: var(--green-border); }
  .counter-label { display: block; font-size: var(--text-xs); color: var(--text-secondary); text-transform: uppercase; }
  .counter-value { font-size: var(--text-2xl); font-weight: 500; }
  .levels { display: flex; flex-direction: column; gap: var(--space-4); }
  .alloc-row { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); padding: 6px 0; }
  .alloc-name { font-size: var(--text-sm); display: flex; align-items: center; gap: 6px; }
  .alloc-input { width: 110px; text-align: right; }
</style>
