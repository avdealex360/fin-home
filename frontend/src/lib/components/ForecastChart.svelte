<script lang="ts">
  /** Cumulative spend so far, last month's curve for reference, and a dotted
   *  line to the history-based forecast — against the month's plan.
   *  Answers "will we make it?" without pretending spend is linear. */
  interface Props {
    cumulative: number[]
    /** Previous month's cumulative curve (full month), empty when there is none. */
    prev?: number[]
    planLimit: number
    /** History-based month total; null hides the forecast line. */
    forecastTotal: number | null
    daysInMonth: number
  }
  let { cumulative, prev = [], planLimit, forecastTotal, daysInMonth }: Props = $props()

  const W = 500
  const H = 210
  const PAD_TOP = 24
  const PLOT = H - PAD_TOP - 8

  let max = $derived(Math.max(planLimit, forecastTotal ?? 0, ...cumulative, ...prev) * 1.05 || 1)
  let px = $derived((day: number) => 3 + (day / daysInMonth) * (W - 6))
  let py = $derived((v: number) => H - 8 - (v / max) * PLOT)

  const toPath = (pts: { x: number; y: number }[]) =>
    pts.map((p, i) => `${i ? 'L' : 'M'}${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ')

  let points = $derived(cumulative.map((v, i) => ({ x: px(i + 1), y: py(v) })))
  let line = $derived(toPath(points))
  let area = $derived(
    points.length
      ? `M${points[0].x.toFixed(1)} ${H - 8} ${points.map((p) => `L${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ')} L${points[points.length - 1].x.toFixed(1)} ${H - 8} Z`
      : '',
  )
  // Previous month may have a different length; stretch it onto this month's axis.
  let prevLine = $derived(
    prev.length
      ? toPath(prev.map((v, i) => ({ x: px(((i + 1) / prev.length) * daysInMonth), y: py(v) })))
      : '',
  )
  let last = $derived(points[points.length - 1] ?? { x: px(1), y: py(0) })
  let forecast = $derived(
    forecastTotal !== null
      ? `M${last.x.toFixed(1)} ${last.y.toFixed(1)} L${px(daysInMonth).toFixed(1)} ${py(forecastTotal).toFixed(1)}`
      : '',
  )
  let limitTop = $derived(`${((py(planLimit) / H) * 100).toFixed(2)}%`)
  let limitLabel = $derived(`план ${Math.round(planLimit).toLocaleString('ru-RU').replace(/ /g, ' ')} ₽`)
</script>

<div class="wrap">
  {#if planLimit > 0}<span class="limit-label" style="top: {limitTop}">{limitLabel}</span>{/if}
  <svg viewBox="0 0 {W} {H}">
    {#if planLimit > 0}
      <line x1="0" y1={py(planLimit)} x2={W} y2={py(planLimit)} stroke="var(--yellow)" stroke-width="1" stroke-dasharray="4 4" opacity="0.6" />
    {/if}
    {#if prevLine}
      <path d={prevLine} fill="none" stroke="rgba(255,255,255,.22)" stroke-width="1.5" stroke-linejoin="round" />
    {/if}
    <path d={area} fill="rgba(240,104,106,.13)" />
    <path d={line} fill="none" stroke="var(--red)" stroke-width="2.5" stroke-linejoin="round" />
    {#if forecast}
      <path d={forecast} fill="none" stroke="var(--red)" stroke-width="2" stroke-dasharray="5 4" opacity="0.65" />
      <circle cx={px(daysInMonth)} cy={py(forecastTotal ?? 0)} r="3" fill="none" stroke="var(--red)" stroke-width="1.5" opacity="0.65" />
    {/if}
    <circle cx={last.x} cy={last.y} r="3.5" fill="var(--red)" />
  </svg>
  <div class="legend">
    <span><i style="background: var(--red)"></i>этот месяц</span>
    {#if prevLine}<span><i style="background: rgba(255,255,255,.35)"></i>прошлый</span>{/if}
    {#if forecast}<span><i class="dash"></i>по обычным месяцам</span>{/if}
  </div>
</div>

<style>
  .wrap { position: relative; margin-top: var(--space-3); }
  svg { width: 100%; height: auto; display: block; }
  .limit-label {
    position: absolute;
    left: 2px;
    transform: translateY(-100%);
    font-size: 11px;
    color: var(--yellow);
    pointer-events: none;
  }
  .legend { display: flex; flex-wrap: wrap; gap: 6px 14px; margin-top: 6px; font-size: 11px; color: var(--text-muted); }
  .legend span { display: inline-flex; align-items: center; gap: 6px; }
  .legend i { width: 14px; height: 2px; border-radius: 2px; display: inline-block; }
  .legend i.dash { background: repeating-linear-gradient(90deg, var(--red) 0 4px, transparent 4px 7px); opacity: 0.75; }
</style>
