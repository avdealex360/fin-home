<script lang="ts">
  interface Props {
    open: boolean
    title?: string
    onclose: () => void
    children: import('svelte').Snippet
  }
  let { open, title = '', onclose, children }: Props = $props()

  function onKey(e: KeyboardEvent) {
    if (e.key === 'Escape') onclose()
  }
</script>

<svelte:window on:keydown={onKey} />

{#if open}
  <div class="overlay" onclick={onclose} role="presentation"></div>
  <div class="sheet" role="dialog" aria-modal="true" aria-label={title}>
    <div class="grabber"></div>
    {#if title}<h2 class="sheet-title">{title}</h2>{/if}
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
    max-width: 480px;
    margin: 0 auto;
    background: var(--bg-elevated);
    border-radius: var(--radius-xl) var(--radius-xl) 0 0;
    box-shadow: var(--shadow-sheet);
    padding: var(--space-3) var(--space-4) calc(var(--space-6) + env(safe-area-inset-bottom));
    max-height: 92dvh;
    overflow-y: auto;
    animation: slideUp 0.25s ease;
  }
  .grabber {
    width: 40px;
    height: 4px;
    border-radius: 999px;
    background: var(--text-muted);
    margin: 0 auto var(--space-3);
  }
  .sheet-title {
    font-size: var(--text-lg);
    margin-bottom: var(--space-4);
  }
  .sheet-body { display: flex; flex-direction: column; gap: var(--space-4); }
  @keyframes slideUp { from { transform: translateY(100%); } to { transform: translateY(0); } }
  @keyframes fade { from { opacity: 0; } to { opacity: 1; } }
</style>
