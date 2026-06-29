<script lang="ts">
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
</script>

<div class="pbar">
  <div class="pbar-fill {autoColor}" style="width: {pct}%"></div>
  {#if showPace}<div class="pbar-pace" style="left: {pace}%"></div>{/if}
</div>
