<script lang="ts">
  import { period, showHelp } from '../stores'
  import { monthName, shiftMonth } from '../format'

  interface Props {
    title: string
    subtitle?: string
    /** Hide the month switcher on screens that are not month-scoped. */
    showPeriod?: boolean
    onadd?: () => void
  }
  let { title, subtitle = '', showPeriod = true, onadd }: Props = $props()

  function shift(delta: number) {
    period.update((p) => {
      const [y, m] = shiftMonth(p.year, p.month, delta)
      return { year: y, month: m }
    })
  }
</script>

<header class="app-header">
  <div class="titles">
    <h1>{title}</h1>
    {#if subtitle}<div class="sub">{subtitle}</div>{/if}
  </div>

  {#if showPeriod}
    <div class="month">
      <button aria-label="Предыдущий месяц" onclick={() => shift(-1)}><i class="ti ti-chevron-left"></i></button>
      <span>{monthName($period.month)} {$period.year}</span>
      <button aria-label="Следующий месяц" onclick={() => shift(1)}><i class="ti ti-chevron-right"></i></button>
    </div>
  {/if}

  <button
    class="toggle"
    class:on={$showHelp}
    aria-pressed={$showHelp}
    title="Показать пояснения к цифрам"
    onclick={() => showHelp.update((v) => !v)}
  >
    <i class="ti ti-help-circle"></i><span class="toggle-label">Пояснения</span>
  </button>

  {#if onadd}
    <button class="add" onclick={onadd}><i class="ti ti-plus"></i><span>Операция</span></button>
  {/if}
</header>

<style>
  .app-header {
    position: sticky;
    top: 0;
    z-index: 30;
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--space-3);
    padding: var(--space-3) var(--page-pad);
    background: rgba(12, 14, 19, 0.86);
    backdrop-filter: blur(14px);
    border-bottom: 1px solid var(--line);
  }
  .titles { min-width: 0; margin-right: auto; }
  h1 { font-size: clamp(19px, 2vw, 24px); letter-spacing: -0.02em; }
  .sub { font-size: 12.5px; color: var(--text-secondary); margin-top: 2px; }

  .month {
    display: flex; align-items: center; gap: 2px;
    background: var(--bg-surface); border: 1px solid var(--line);
    border-radius: 11px; padding: 3px;
  }
  .month span { min-width: 118px; text-align: center; font-size: 13.5px; font-weight: 600; }
  .month button {
    width: 32px; height: 32px; border: none; background: transparent;
    color: var(--text-secondary); border-radius: 8px; display: grid; place-items: center;
  }
  .month button:hover { background: rgba(255, 255, 255, 0.05); color: var(--text-primary); }
  .month i { font-size: 17px; }

  .toggle {
    display: flex; align-items: center; gap: 7px; height: 38px; padding: 0 13px;
    border-radius: 11px; border: 1px solid var(--line);
    background: var(--bg-surface); color: var(--text-secondary);
    font-size: 13px; font-weight: 500;
  }
  .toggle.on { background: rgba(106, 155, 255, 0.14); color: var(--blue); }
  .toggle i { font-size: 17px; }
  .toggle-label { display: none; }

  .add {
    display: none; align-items: center; gap: 7px; height: 38px; padding: 0 15px;
    border-radius: 11px; border: none; background: var(--blue); color: #0b1220;
    font-size: 13.5px; font-weight: 600;
  }
  .add i { font-size: 17px; }

  @media (min-width: 640px) { .toggle-label { display: inline; } }
  /* The FAB covers "add" on phones; show the header button once the FAB is gone. */
  @media (min-width: 900px) { .add { display: flex; } }
</style>
