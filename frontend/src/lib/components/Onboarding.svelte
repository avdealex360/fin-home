<script lang="ts">
  import { api } from '../api'
  interface Props {
    ondone: () => void
  }
  let { ondone }: Props = $props()
  let busy = $state(false)

  async function pick(mode: 'demo' | 'clean') {
    busy = true
    await api.onboard(mode)
    ondone()
  }
</script>

<div class="onb">
  <div class="logo"><i class="ti ti-coins"></i></div>
  <h1>fin-home</h1>
  <p class="muted">Семейный бюджет по методу 50/30/20</p>

  <div class="opts">
    <button class="card opt" disabled={busy} onclick={() => pick('demo')}>
      <i class="ti ti-sparkles"></i>
      <strong>Загрузить пример</strong>
      <span class="muted">Готовые категории, копилки, долги и цели — чтобы сразу осмотреться. Всё можно изменить или удалить.</span>
    </button>
    <button class="card opt" disabled={busy} onclick={() => pick('clean')}>
      <i class="ti ti-file"></i>
      <strong>Начать с чистого листа</strong>
      <span class="muted">Пустой бюджет. Категории, копилки и цели создаёте сами.</span>
    </button>
  </div>
</div>

<style>
  .onb {
    max-width: 480px;
    margin: 0 auto;
    min-height: 100dvh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--space-3);
    padding: var(--space-6);
    text-align: center;
  }
  .logo {
    width: 72px; height: 72px; border-radius: var(--radius-lg);
    background: var(--blue-bg); color: var(--blue);
    display: flex; align-items: center; justify-content: center;
  }
  .logo i { font-size: 40px; }
  .opts { display: flex; flex-direction: column; gap: var(--space-3); width: 100%; margin-top: var(--space-6); }
  .opt {
    display: flex; flex-direction: column; gap: 6px; text-align: left;
    border: 1px solid rgba(255,255,255,0.06); color: var(--text-primary);
  }
  .opt i { font-size: 24px; color: var(--blue); }
  .opt strong { font-size: var(--text-lg); }
</style>
