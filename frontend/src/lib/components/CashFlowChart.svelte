<script lang="ts">
  /** Income / expense bars per month with a "what's left" line on top.
   *  Month labels are HTML, not <text>, so they stay 10.5px at any width. */
  interface Props {
    labels: string[]
    income: number[]
    expense: number[]
  }
  let { labels, income, expense }: Props = $props()

  const W = 680
  const BASE = 190

  let max = $derived(Math.max(1, ...income, ...expense))
  let slot = $derived(W / Math.max(labels.length, 1))
  let scale = $derived(165 / max)

  let bars = $derived(
    income.map((v, i) => {
      const mid = i * slot + slot / 2
      return {
        xi: mid - 12,
        hi: v * scale,
        yi: BASE - v * scale,
        xe: mid + 1,
        he: expense[i] * scale,
        ye: BASE - expense[i] * scale,
      }
    }),
  )
  let netPoints = $derived(
    income.map((v, i) => ({
      x: i * slot + slot / 2,
      y: BASE - (v - expense[i]) * scale,
    })),
  )
  let netPath = $derived(netPoints.map((p, i) => `${i ? 'L' : 'M'}${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' '))
</script>

<div class="legend">
  <span><i style="background: var(--green)"></i>Доход</span>
  <span><i style="background: var(--red)"></i>Расход</span>
  <span><i class="line" style="background: var(--gold)"></i>Что осталось</span>
</div>

<svg viewBox="0 0 {W} 200" class="chart">
  <line x1="0" y1={BASE} x2={W} y2={BASE} stroke="rgba(255,255,255,.10)" stroke-width="1" />
  {#each bars as b}
    <rect x={b.xi} y={b.yi} width="11" height={Math.max(b.hi, 0)} rx="3" fill="var(--green)" opacity="0.85" />
    <rect x={b.xe} y={b.ye} width="11" height={Math.max(b.he, 0)} rx="3" fill="var(--red)" opacity="0.85" />
  {/each}
  <path d={netPath} fill="none" stroke="var(--gold)" stroke-width="2" stroke-linejoin="round" />
  {#each netPoints as p}
    <circle cx={p.x} cy={p.y} r="2.6" fill="var(--gold)" />
  {/each}
</svg>

<div class="labels" style="grid-template-columns: repeat({labels.length}, 1fr)">
  {#each labels as l}<span>{l}</span>{/each}
</div>

<style>
  .chart { width: 100%; height: auto; display: block; margin-top: var(--space-3); }
  .legend { display: flex; flex-wrap: wrap; gap: var(--space-4); font-size: 11.5px; color: var(--text-secondary); }
  .legend span { display: inline-flex; align-items: center; gap: 6px; }
  .legend i { width: 9px; height: 9px; border-radius: 3px; display: inline-block; }
  .legend i.line { width: 14px; height: 2px; border-radius: 0; }
  .labels { display: grid; margin-top: 2px; font-size: 10.5px; color: var(--text-muted); text-align: center; }
</style>
