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
    height: calc(var(--nav-h) + env(safe-area-inset-bottom));
    padding-bottom: env(safe-area-inset-bottom);
    background: rgba(15, 19, 27, 0.74);
    backdrop-filter: blur(20px) saturate(160%);
    -webkit-backdrop-filter: blur(20px) saturate(160%);
    /* bright top edge = light catching the material */
    border-top: 1px solid rgba(255, 255, 255, 0.07);
    display: flex;
  }
  .bottom-nav::before {
    content: '';
    position: absolute;
    left: 0; right: 0; top: -18px; height: 18px;
    background: linear-gradient(to top, rgba(12, 14, 19, 0.5), rgba(12, 14, 19, 0));
    pointer-events: none;
  }
  @media (prefers-reduced-transparency: reduce) {
    .bottom-nav { background: #0f131b; backdrop-filter: none; -webkit-backdrop-filter: none; }
    .bottom-nav::before { display: none; }
  }
  @media (prefers-contrast: more) {
    .bottom-nav { background: #0f131b; border-top-color: var(--text-muted); }
  }
  /* Replaced by the left sidebar from tablet width up. */
  @media (min-width: 900px) {
    .bottom-nav { display: none; }
  }
  .nav-item {
    flex: 1;
    min-height: 44px;
    background: none;
    border: none;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 3px;
    color: var(--text-muted);
    font-size: 10.5px;
    font-weight: 500;
    letter-spacing: 0.01em;
    transition: color 160ms ease-out, transform 220ms cubic-bezier(0.2, 0.8, 0.2, 1);
  }
  .nav-item:active { transform: none; }
  .nav-item i { font-size: 22px; transition: transform 220ms cubic-bezier(0.2, 0.8, 0.2, 1); }
  /* Press: the icon dips the instant the finger lands; release springs it back. */
  .nav-item:active i { transform: scale(0.88); transition-duration: 80ms; }
  .nav-item.active { color: var(--blue); }
  .nav-item.accent i { color: var(--blue); }
</style>
