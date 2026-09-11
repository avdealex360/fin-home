<script lang="ts">
  import { SpringValue, SPRINGS, prefersReducedMotion } from '../motion'

  interface Props {
    spent: number
    limit: number
    color?: 'green' | 'yellow' | 'red' | 'blue'
  }
  let { spent, limit, color }: Props = $props()

  let pct = $derived(limit > 0 ? Math.min((spent / limit) * 100, 100) : 0)
  let autoColor = $derived(
    color ?? (pct < 70 ? 'green' : pct < 90 ? 'yellow' : 'red'),
  )

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
</div>
