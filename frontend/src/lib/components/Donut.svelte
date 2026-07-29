<script lang="ts">
  interface Segment { label: string; value: number; color: string }
  interface Props {
    segments: Segment[]
    total: number
    caption?: string
    size?: number
  }
  let { segments, total, caption = '', size = 168 }: Props = $props()

  const R = 66
  const C = 2 * Math.PI * R

  let arcs = $derived.by(() => {
    let offset = 0
    return segments.map((s) => {
      const frac = total > 0 ? s.value / total : 0
      const arc = {
        color: s.color,
        dash: `${Math.max(frac * C - 2, 0).toFixed(1)} ${(C - frac * C + 2).toFixed(1)}`,
        offset: (-offset).toFixed(1),
      }
      offset += frac * C
      return arc
    })
  })
  let display = $derived(Math.round(total).toLocaleString('ru-RU').replace(/\u00a0/g, ' '))
</script>

<div class="donut" style="width:{size}px;height:{size}px">
  <svg viewBox="0 0 168 168">
    {#each arcs as a}
      <circle cx="84" cy="84" r={R} fill="none" stroke={a.color} stroke-width="17" stroke-dasharray={a.dash} stroke-dashoffset={a.offset} />
    {/each}
  </svg>
  <div class="center">
    <span class="num total">{display}</span>
    {#if caption}<span class="cap">{caption}</span>{/if}
  </div>
</div>

<style>
  .donut { position: relative; flex: 0 0 auto; }
  svg { width: 100%; height: 100%; transform: rotate(-90deg); }
  .center {
    position: absolute; inset: 0;
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    text-align: center;
  }
  .total { font-size: 20px; font-weight: 600; }
  .cap { font-size: 11px; color: var(--text-muted); }
</style>
