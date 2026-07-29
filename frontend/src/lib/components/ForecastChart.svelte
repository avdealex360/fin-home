<script lang="ts">
  /** Cumulative spend so far + dotted projection to the end of the month,
   *  against the month's plan. Answers "will we make it?" at a glance. */
  interface Props {
    cumulative: number[]
    planLimit: number
    projected: number
    daysInMonth: number
  }
  let { cumulative, planLimit, projected, daysInMonth }: Props = $props()

  const W = 500
  const H = 210
  const PAD_TOP = 24
  const PLOT = H - PAD_TOP - 8

  let max = $derived(Math.max(planLimit, projected, ...cumulative) * 1.05 || 1)
  let px = $derived((day: number) => 3 + (day / daysInMonth) * (W - 6))
  let py = $derived((v: number) => H - 8 - (v / max) * PLOT)

  let points = $derived(cumulative.map((v, i) => ({ x: px(i + 1), y: py(v) })))
  let line = $derived(points.map((p, i) => `${i ? 'L' : 'M'}${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' '))
  let area = $derived(
    points.length
      ? `M${points[0].x.toFixed(1)} ${H - 8} ${points.map((p) => `L${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ')} L${points[points.length - 1].x.toFixed(1)} ${H - 8} Z`
      : '',
  )
  let last = $derived(points[points.length - 1] ?? { x: px(1), y: py(0) })
  let forecast = $derived(`M${last.x.toFixed(1)} ${last.y.toFixed(1)} L${px(daysInMonth).toFixed(1)} ${py(projected).toFixed(1)}`)
  let paceLine = $derived(`M${px(1).toFixed(1)} ${py(planLimit / daysInMonth).toFixed(1)} L${px(daysInMonth).toFixed(1)} ${py(planLimit).toFixed(1)}`)
  let limitTop = $derived(`${((py(planLimit) / H) * 100).toFixed(2)}%`)
  let limitLabel = $derived(`план ${Math.round(planLimit).toLocaleString('ru-RU').replace(/\u00a0/g, ' ')} ₽`)
</script>

<div class="wrap">
  <span class="limit-label" style="top: {limitTop}">{limitLabel}</span>
  <svg viewBox="0 0 {W} {H}">
    <line x1="0" y1={py(planLimit)} x2={W} y2={py(planLimit)} stroke="var(--yellow)" stroke-width="1" stroke-dasharray="4 4" opacity="0.6" />
    <path d={paceLine} fill="none" stroke="rgba(255,255,255,.18)" stroke-width="1.5" />
    <path d={area} fill="rgba(240,104,106,.13)" />
    <path d={line} fill="none" stroke="var(--red)" stroke-width="2.5" stroke-linejoin="round" />
    <path d={forecast} fill="none" stroke="var(--red)" stroke-width="2" stroke-dasharray="5 4" opacity="0.65" />
    <circle cx={last.x} cy={last.y} r="3.5" fill="var(--red)" />
  </svg>
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
</style>
