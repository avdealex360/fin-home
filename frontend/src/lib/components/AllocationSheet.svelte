<script lang="ts">
  import { api, type AllocationView, type AllocationBucket } from '../api'
  import { money } from '../format'
  import Loader from './Loader.svelte'

  interface Props {
    txId: number
    ondone: () => void
  }
  let { txId, ondone }: Props = $props()

  let view = $state<AllocationView | null>(null)
  // key = `${group}:${kind}:${id}` -> amount
  let amounts = $state<Record<string, number>>({})
  let saving = $state(false)

  const keyOf = (group: string, kind: string, id: number | string) => `${group}:${kind}:${id}`

  $effect(() => {
    init()
  })
  let loaded = false
  async function init() {
    if (loaded) return
    loaded = true
    const v = await api.allocationView(txId)
    view = v
    // Initialize all items to 0
    const next: Record<string, number> = {}
    for (const b of v.buckets) {
      for (const it of b.items) {
        next[keyOf(b.group, it.kind, it.id)] = 0
      }
    }
    // Prefill from existing allocation
    for (const ex of v.existing) {
      if (ex.fund_id) {
        // find which bucket this fund belongs to
        for (const b of v.buckets) {
          const found = b.items.find(it => it.kind === 'fund' && it.id === ex.fund_id)
          if (found) {
            next[keyOf(b.group, 'fund', ex.fund_id)] = ex.amount
            break
          }
        }
      } else if (ex.category_id) {
        // find which bucket this category belongs to
        for (const b of v.buckets) {
          const found = b.items.find(it => it.kind === 'category' && it.id === ex.category_id)
          if (found) {
            next[keyOf(b.group, 'category', ex.category_id)] = ex.amount
            break
          }
        }
      }
    }
    amounts = next
  }

  let assigned = $derived(Object.values(amounts).reduce((s, n) => s + (n || 0), 0))
  let remaining = $derived((view?.transaction.amount ?? 0) - assigned)

  function bucketAssigned(b: AllocationBucket): number {
    return b.items.reduce((s, it) => s + (amounts[keyOf(b.group, it.kind, it.id)] || 0), 0)
  }

  function autoFill() {
    if (!view) return
    const next = { ...amounts }
    for (const b of view.buckets) {
      for (const it of b.items) {
        next[keyOf(b.group, it.kind, it.id)] = Math.round(it.suggested_amount)
      }
    }
    amounts = next
  }

  async function save() {
    if (!view) return
    saving = true
    const allocations: unknown[] = []
    for (const b of view.buckets) {
      for (const it of b.items) {
        const amt = amounts[keyOf(b.group, it.kind, it.id)] || 0
        if (amt <= 0) continue
        allocations.push({
          category_id: it.kind === 'category' ? it.id : null,
          fund_id: it.kind === 'fund' ? it.id : null,
          amount: amt,
          group: b.group,
        })
      }
    }
    await api.allocate(txId, allocations)
    ondone()
  }
</script>

{#if !view}
  <Loader />
{:else}
  <div class="counter" class:done={Math.abs(remaining) < 1}>
    <span class="counter-label">К распределению</span>
    <span class="counter-value num">{money(remaining)} ₽</span>
  </div>

  <button class="btn btn-secondary" onclick={autoFill}>
    <i class="ti ti-wand"></i> Распределить по плану автоматически
  </button>

  <div class="buckets">
    {#each view.buckets as b}
      {#if b.items.length}
        {@const ba = bucketAssigned(b)}
        {@const met = ba >= b.target_amount && b.target_amount > 0}
        <div class="bucket">
          <div class="bucket-header">
            <span class="bucket-label">{b.label}</span>
            <span class="bucket-percent">{b.percent}%</span>
            <span class="bucket-counter" class:done={met}>
              {money(ba)} / {money(b.target_amount)} ₽
            </span>
          </div>
          {#each b.items as it}
            <div class="alloc-row">
              <span class="alloc-name">
                {#if it.kind === 'fund'}<i class="ti ti-pig-money"></i>{/if}
                {it.name}
              </span>
              <input
                class="input alloc-input num"
                inputmode="numeric"
                value={amounts[keyOf(b.group, it.kind, it.id)] || ''}
                oninput={(e) =>
                  (amounts[keyOf(b.group, it.kind, it.id)] =
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
  .buckets { display: flex; flex-direction: column; gap: var(--space-4); }
  .bucket { display: flex; flex-direction: column; gap: 0; }
  .bucket-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) 0 var(--space-1);
    border-bottom: 1px solid var(--border);
    margin-bottom: var(--space-1);
  }
  .bucket-label { font-size: var(--text-sm); font-weight: 600; color: var(--text-primary); flex: 1; }
  .bucket-percent { font-size: var(--text-xs); color: var(--text-secondary); }
  .bucket-counter {
    font-size: var(--text-xs);
    color: var(--text-secondary);
    font-variant-numeric: tabular-nums;
  }
  .bucket-counter.done { color: var(--color-success, #4ade80); }
  .alloc-row { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); padding: 6px 0; }
  .alloc-name { font-size: var(--text-sm); display: flex; align-items: center; gap: 6px; }
  .alloc-input { width: 110px; text-align: right; }
</style>
