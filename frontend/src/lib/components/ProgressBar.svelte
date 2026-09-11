<script lang="ts">
  import { SpringValue, SPRINGS, prefersReducedMotion } from '../motion'

  interface Props {
    spent: number
    limit: number
    color?: 'green' | 'yellow' | 'red' | 'blue'
    showPace?: boolean
  }
  let { spent, limit, color, showPace = false }: Props = $props()

  let pct = $derived(limit > 0 ? Math.min((spent / limit) * 100, 100) : 0)
  let autoColor = $derived(
    color ?? (pct < 70 ? 'green' : pct < 90 ? 'yellow' : 'red'),
  )
  // Pace: where you "should" be today within the month.
  let pace = $derived.by(() => {
    const now = new Date()
    const dim = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate()
    return (now.getDate() / dim) * 100
  })

  // The fill settles into its new value like a real gauge; on data change it
  // re-targets from wherever it currently is instead of restarting.
  const reduced = prefersReducedMotion()
  let shownPct = $state(0)
  const spring = new SpringValue(0, SPRINGS.gentle, (v) => (shownPct = v))
  let first = true
  $effect(() => {
    const target = pct
    if (reduced) { spring.snap(target); return }
    if (first) {
      first = false
      // Fill from empty on first paint: reads as "loading the month", not a jump.
      spring.snap(0)
    }
    spring.setTarget(target)
  })
</script>

<div class="pbar">
  <div class="pbar-fill {autoColor}" style="width: {shownPct}%"></div>
  {#if showPace}<div class="pbar-pace" style="left: {pace}%"></div>{/if}
</div>
