<script lang="ts">
  import { route, navigate } from '../stores'

  interface Props {
    onadd: () => void
    /** Real family members, e.g. "Аня и Илья". Falls back to "Семья". */
    brandSub?: string
    /** Short summary shown at the bottom of the expanded sidebar. */
    freeAmount?: string
    perDay?: string
    daysLeft?: number
  }
  let { onadd, brandSub = '', freeAmount = '', perDay = '', daysLeft = 0 }: Props = $props()

  const items = [
    { id: 'dashboard', label: 'Главная', icon: 'ti-home' },
    { id: 'transactions', label: 'Операции', icon: 'ti-list' },
    { id: 'plan', label: 'План', icon: 'ti-calendar-stats' },
    { id: 'deposit', label: 'Накопления', icon: 'ti-pig-money' },
    { id: 'analytics', label: 'Аналитика', icon: 'ti-chart-histogram' },
    { id: 'more', label: 'Ещё', icon: 'ti-dots' },
  ]
</script>

<aside class="side-nav">
  <div class="brand">
    <span class="mark">₽</span>
    <span class="brand-text">
      <span class="brand-title">Семейный бюджет</span>
      <span class="brand-sub">{brandSub || 'Семья'}</span>
    </span>
  </div>

  <nav>
    {#each items as it}
      <button
        class="nav-item"
        class:active={$route === it.id}
        aria-current={$route === it.id ? 'page' : undefined}
        title={it.label}
        onclick={() => navigate(it.id)}
      >
        <i class="ti {it.icon}"></i>
        <span class="nav-label">{it.label}</span>
      </button>
    {/each}
  </nav>

  <div class="spacer"></div>

  <button class="add" onclick={onadd}>
    <i class="ti ti-plus"></i>
    <span class="nav-label">Операция</span>
  </button>

  {#if freeAmount}
    <div class="summary">
      <div class="section-label">Свободно · {daysLeft} дн.</div>
      <div class="num summary-amt">{freeAmount} ₽</div>
      <div class="summary-sub">≈ {perDay} ₽ в день</div>
    </div>
  {/if}
</aside>

<style>
  /* Hidden on phones — BottomNav takes over there. */
  .side-nav { display: none; }

  @media (min-width: 900px) {
    .side-nav {
      display: flex;
      flex-direction: column;
      gap: 6px;
      flex: 0 0 var(--rail-w);
      width: var(--rail-w);
      position: sticky;
      top: 0;
      height: 100dvh;
      padding: 18px 12px 14px;
      background: #0f131b;
      border-right: 1px solid var(--line);
    }
  }
  @media (min-width: 1280px) {
    .side-nav { flex-basis: var(--side-w); width: var(--side-w); }
  }

  .brand { display: flex; align-items: center; gap: 10px; padding: 4px 8px 18px; }
  .mark {
    width: 32px; height: 32px; flex: 0 0 32px; border-radius: 10px;
    background: linear-gradient(150deg, var(--blue), var(--green));
    display: grid; place-items: center; color: #0b1220; font-weight: 700;
  }
  .brand-text { display: none; min-width: 0; }
  .brand-title { display: block; font-size: 14px; font-weight: 600; }
  .brand-sub { display: block; font-size: 11px; color: var(--text-muted); }

  nav { display: flex; flex-direction: column; gap: 4px; }

  .nav-item {
    display: flex; align-items: center; gap: 11px;
    width: 100%; min-height: 44px; padding: 0 12px;
    border: none; border-radius: 11px; background: transparent;
    color: var(--text-secondary); font-size: 14px; font-weight: 500; text-align: left;
    transition: background var(--transition-fast), color var(--transition-fast);
  }
  .nav-item:hover { background: rgba(255, 255, 255, 0.04); color: var(--text-primary); }
  .nav-item.active { background: rgba(106, 155, 255, 0.14); color: var(--blue); }
  .nav-item i { font-size: 20px; flex: 0 0 20px; }

  .nav-label { display: none; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

  .spacer { flex: 1; }

  .add {
    display: flex; align-items: center; justify-content: center; gap: 8px;
    width: 100%; min-height: 46px; border: none; border-radius: 13px;
    background: var(--blue); color: #0b1220; font-size: 14px; font-weight: 600;
    box-shadow: var(--shadow-fab);
  }
  .add i { font-size: 19px; }

  .summary { display: none; margin-top: 12px; padding: 12px; border-radius: 13px; background: var(--bg-surface); border: 1px solid var(--line); }
  .summary-amt { font-size: 20px; font-weight: 600; margin-top: 6px; }
  .summary-sub { font-size: 12px; color: var(--text-secondary); margin-top: 2px; }

  /* Labels and the summary card only appear once there is room. */
  @media (min-width: 1280px) {
    .brand-text, .nav-label, .summary { display: block; }
  }
</style>
