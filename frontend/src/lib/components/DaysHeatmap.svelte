<script lang="ts">
  import { money } from '../format'

  /** Calendar heat-map of daily spend — makes weekend/payday patterns obvious. */
  interface Props {
    values: number[]       // index 0 = day 1
    firstWeekday: number   // 0 = Monday
    today: number
    monthLabel: string
  }
  let { values, firstWeekday, today, monthLabel }: Props = $props()

  const WEEKDAYS = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс']

  let max = $derived(Math.max(1, ...values.slice(0, today)))
  let cells = $derived.by(() => {
    const out: { day: number | null; value: number; future: boolean; t: number }[] = []
    for (let i = 0; i < firstWeekday; i++) out.push({ day: null, value: 0, future: false, t: 0 })
    values.forEach((v, i) => {
      const day = i + 1
      out.push({ day, value: v, future: day > today, t: Math.min(v / max, 1) })
    })
    return out
  })
</script>

<div class="grid">
  {#each WEEKDAYS as w}<span class="wd">{w}</span>{/each}
  {#each cells as c}
    {#if c.day === null}
      <span class="cell empty"></span>
    {:else}
      <span
        class="cell"
        class:future={c.future}
        title={c.future ? `${c.day} ${monthLabel} — ещё не наступило` : `${c.day} ${monthLabel} — ${money(c.value)} ₽`}
        style="background: {c.future ? 'transparent' : c.value === 0 ? '#1a2030' : `rgba(106,155,255,${(0.12 + c.t * 0.78).toFixed(2)})`};
               color: {c.future ? 'var(--text-muted)' : c.t > 0.55 ? '#0b1220' : 'var(--text-secondary)'}"
      >{c.day}</span>
    {/if}
  {/each}
</div>

<div class="scale">
  <span>меньше</span>
  <i style="background:#1a2030"></i>
  <i style="background:rgba(106,155,255,.28)"></i>
  <i style="background:rgba(106,155,255,.55)"></i>
  <i style="background:var(--blue)"></i>
  <span>больше</span>
</div>

<style>
  .grid {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 6px;
    margin-top: var(--space-3);
    max-width: 340px;
  }
  .wd { font-size: 10px; color: var(--text-muted); text-align: center; }
  .cell {
    aspect-ratio: 1;
    border-radius: 7px;
    display: grid;
    place-items: center;
    font-size: 10px;
    font-family: var(--font-mono);
  }
  .cell.future { border: 1px solid rgba(255, 255, 255, 0.05); }
  .cell.empty { background: transparent; }
  .scale { display: flex; align-items: center; gap: 8px; margin-top: var(--space-3); font-size: 11px; color: var(--text-muted); }
  .scale i { width: 14px; height: 14px; border-radius: 4px; display: inline-block; }
</style>
