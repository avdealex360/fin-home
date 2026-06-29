<script lang="ts">
  import { toast } from '../stores'
  function doUndo() {
    const t = $toast
    if (t?.undo) t.undo()
    toast.set(null)
  }
</script>

{#if $toast}
  <div class="toast" role="status" aria-live="polite">
    <span>{$toast.message}</span>
    {#if $toast.undo}
      <button class="undo" onclick={doUndo}>Отменить</button>
    {/if}
  </div>
{/if}

<style>
  .toast {
    position: fixed;
    left: 50%;
    transform: translateX(-50%);
    bottom: calc(var(--nav-h) + env(safe-area-inset-bottom) + var(--space-4));
    z-index: 60;
    background: var(--bg-elevated);
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: var(--text-primary);
    border-radius: var(--radius-md);
    padding: 12px var(--space-4);
    display: flex;
    align-items: center;
    gap: var(--space-4);
    box-shadow: var(--shadow-sheet);
    font-size: var(--text-sm);
    max-width: 90vw;
    animation: pop 0.2s ease;
  }
  .undo { background: none; border: none; color: var(--blue); font-weight: 600; font-size: var(--text-sm); }
  @keyframes pop { from { opacity: 0; transform: translate(-50%, 20px); } to { opacity: 1; transform: translate(-50%, 0); } }
</style>
