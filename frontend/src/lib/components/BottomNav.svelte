<script lang="ts">
  import { route, navigate } from '../stores'

  interface Props {
    onadd: () => void
  }
  let { onadd }: Props = $props()

  const items = [
    { id: 'dashboard', label: 'Главная', icon: 'ti-home' },
    { id: 'transactions', label: 'Операции', icon: 'ti-list' },
    { id: 'plan', label: 'План', icon: 'ti-calendar' },
    { id: 'add', label: 'Добавить', icon: 'ti-plus' },
    { id: 'analytics', label: 'Аналитика', icon: 'ti-chart-bar' },
    { id: 'more', label: 'Ещё', icon: 'ti-dots' },
  ]

  function click(id: string) {
    if (id === 'add') onadd()
    else navigate(id)
  }
</script>

<nav class="bottom-nav">
  {#each items as it}
    <button
      class="nav-item"
      class:active={$route === it.id}
      class:accent={it.id === 'add'}
      aria-current={$route === it.id ? 'page' : undefined}
      onclick={() => click(it.id)}
    >
      <i class="ti {it.icon}"></i>
      <span>{it.label}</span>
    </button>
  {/each}
</nav>

<style>
  .bottom-nav {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 20;
    max-width: var(--shell-w);
    margin: 0 auto;
    height: calc(var(--nav-h) + env(safe-area-inset-bottom));
    padding-bottom: env(safe-area-inset-bottom);
    background: var(--bg-surface);
    border-top: 1px solid rgba(255, 255, 255, 0.05);
    display: flex;
  }
  .nav-item {
    flex: 1;
    background: none;
    border: none;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 3px;
    color: var(--text-muted);
    font-size: var(--text-xs);
  }
  .nav-item i { font-size: 22px; }
  .nav-item.active { color: var(--blue); }
  .nav-item.accent i { color: var(--blue); }
</style>
