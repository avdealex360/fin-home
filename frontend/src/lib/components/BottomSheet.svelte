<script lang="ts">
  interface Props {
    open: boolean
    title?: string
    onclose: () => void
    children: import('svelte').Snippet
  }
  let { open, title = '', onclose, children }: Props = $props()

  const CLOSE_THRESHOLD = 60
  const TAP_SLOP = 6

  let dragY = $state(0)
  let dragging = $state(false)
  let startY = 0
  let moved = 0

  function onKey(e: KeyboardEvent) {
    if (e.key === 'Escape') onclose()
  }

  function onDragStart(e: PointerEvent) {
    e.preventDefault()
    startY = e.clientY
    dragging = true
    moved = 0
  }
  function onDragMove(e: PointerEvent) {
    if (!dragging) return
    const delta = e.clientY - startY
    moved = Math.max(moved, Math.abs(delta))
    dragY = Math.max(0, delta)
  }
  function onDragEnd() {
    if (!dragging) return
    dragging = false
    // A near-stationary tap (or a swipe past the threshold) both close —
    // only a real partial drag that falls short snaps back.
    if (dragY > CLOSE_THRESHOLD || moved < TAP_SLOP) {
      onclose()
    }
    dragY = 0
  }
</script>

<svelte:window
  on:keydown={onKey}
  on:pointermove={onDragMove}
  on:pointerup={onDragEnd}
  on:pointercancel={onDragEnd}
/>

{#if open}
  <div class="overlay" onclick={onclose} role="presentation"></div>
  <div
    class="sheet"
    class:dragging
    style="--drag-y: {dragY}px"
    role="dialog"
    aria-modal="true"
    aria-label={title}
  >
    <div class="sheet-header" role="button" tabindex="0" aria-label="Закрыть" onpointerdown={onDragStart}>
      <div class="grabber"></div>
      {#if title}<h2 class="sheet-title">{title}</h2>{/if}
    </div>
    <div class="sheet-body">
      {@render children()}
    </div>
  </div>
{/if}

<style>
  .overlay {
    position: fixed;
    inset: 0;
    background: var(--bg-overlay);
    z-index: 40;
    animation: fade 0.2s ease;
  }
  .sheet {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 50;
    max-width: var(--shell-w);
    margin: 0 auto;
    background: var(--bg-elevated);
    border-radius: var(--radius-xl) var(--radius-xl) 0 0;
    box-shadow: var(--shadow-sheet);
    padding: var(--space-3) var(--space-4) calc(var(--space-6) + env(safe-area-inset-bottom));
    max-height: 92dvh;
    overflow-y: auto;
    transform: translateY(var(--drag-y, 0));
    animation: slideUp 0.25s ease;
    transition: transform 0.2s ease;
  }
  /* Desktop: present as a centred dialog rather than a bottom sheet.
     Drag offset composes with the centring translate via the CSS var. */
  @media (min-width: 640px) {
    .sheet {
      top: 50%;
      bottom: auto;
      max-width: 520px;
      transform: translate(0, calc(-50% + var(--drag-y, 0)));
      border-radius: var(--radius-xl);
      max-height: 88dvh;
      animation: fadeScale 0.2s ease;
    }
  }
  .sheet.dragging {
    transition: none;
  }
  .sheet-header {
    padding: var(--space-3) 0;
    margin: -8px 0 var(--space-2);
    cursor: grab;
    touch-action: none;
    user-select: none;
  }
  .grabber {
    width: 40px;
    height: 4px;
    border-radius: 999px;
    background: var(--text-muted);
    margin: 0 auto var(--space-2);
  }
  .sheet-title {
    font-size: var(--text-lg);
    margin: 0;
  }
  .sheet-body { display: flex; flex-direction: column; gap: var(--space-4); }
  @keyframes slideUp { from { transform: translateY(100%); } to { transform: translateY(var(--drag-y, 0)); } }
  @keyframes fadeScale { from { opacity: 0; } to { opacity: 1; } }
  @keyframes fade { from { opacity: 0; } to { opacity: 1; } }
</style>
