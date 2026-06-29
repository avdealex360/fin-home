<script lang="ts">
  interface Props {
    onclick: () => void
  }
  let { onclick }: Props = $props()
</script>

<button class="fab" {onclick} aria-label="Добавить операцию">
  <i class="ti ti-plus"></i>
</button>

<style>
  .fab {
    position: fixed;
    right: max(var(--space-4), calc(50% - 240px + var(--space-4)));
    bottom: calc(var(--nav-h) + env(safe-area-inset-bottom) + var(--space-4));
    z-index: 25;
    width: 56px;
    height: 56px;
    border-radius: 999px;
    border: none;
    background: var(--blue);
    color: #fff;
    box-shadow: var(--shadow-fab);
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .fab i { font-size: 28px; }
  .fab:active { transform: scale(0.94); }
</style>
