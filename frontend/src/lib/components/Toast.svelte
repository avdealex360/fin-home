<script lang="ts">
  import { untrack } from 'svelte'
  import { toast, type ToastState } from '../stores'
  import { SpringValue, SPRINGS, prefersReducedMotion } from '../motion'

  // The toast enters from below and leaves the same way; `shown` keeps the last
  // message on screen while it animates out.
  let shown = $state<ToastState | null>(null)
  let p = $state(0) // 0 = hidden, 1 = resting
  const reduced = prefersReducedMotion()
  const spring = new SpringValue(0, SPRINGS.default, (v) => (p = v), () => {
    if (spring.target === 0) shown = null
  })

  $effect(() => {
    const t = $toast
    untrack(() => {
      if (t) {
        shown = t
        spring.setTarget(1, reduced ? { response: 0.2, dampingRatio: 1 } : SPRINGS.default)
      } else if (shown) {
        spring.setTarget(0, reduced ? { response: 0.18, dampingRatio: 1 } : { response: 0.3, dampingRatio: 1 })
      }
    })
  })

  function doUndo() {
    const t = $toast
    if (t?.undo) t.undo()
    toast.set(null)
  }

  const RISE = 28
  let transform = $derived(
    reduced ? 'translate3d(-50%, 0, 0)' : `translate3d(-50%, ${((1 - p) * RISE).toFixed(2)}px, 0)`,
  )
</script>

{#if shown}
  <div class="toast" role="status" aria-live="polite" style="transform: {transform}; opacity: {Math.min(1, p * 1.25)}">
    <span>{shown.message}</span>
    {#if shown.undo}
      <button class="undo" onclick={doUndo}>Отменить</button>
    {/if}
  </div>
{/if}

<style>
  .toast {
    position: fixed;
    left: 50%;
    bottom: calc(var(--nav-h) + env(safe-area-inset-bottom) + var(--space-4));
    z-index: 60;
    background: rgba(30, 36, 49, 0.82);
    backdrop-filter: blur(20px) saturate(160%);
    -webkit-backdrop-filter: blur(20px) saturate(160%);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: var(--text-primary);
    border-radius: var(--radius-md);
    padding: 12px var(--space-4);
    display: flex;
    align-items: center;
    gap: var(--space-4);
    box-shadow: var(--shadow-sheet);
    font-size: var(--text-sm);
    font-weight: 500;
    letter-spacing: 0.005em;
    max-width: 90vw;
    will-change: transform, opacity;
  }
  @media (min-width: 900px) {
    .toast { bottom: var(--space-6); }
  }
  .undo { background: none; border: none; color: var(--blue); font-weight: 600; font-size: var(--text-sm); padding: 6px 4px; margin: -6px -4px; }

  @media (prefers-reduced-transparency: reduce) {
    .toast { background: var(--bg-elevated); backdrop-filter: none; -webkit-backdrop-filter: none; }
  }
</style>
