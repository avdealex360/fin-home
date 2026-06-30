<script lang="ts">
  const scenarios = [
    { icon: 'ti-wallet', title: 'Как устроены деньги',
      steps: ['Доход делится на 3 корзины: Нужды 50%, Желания 30%, Сбережения 20%.',
              'Сбережения уходят в два места: Вклад (заморожен, только растёт) и Копилки (можно тратить).'] },
    { icon: 'ti-arrow-down-circle', title: 'Записать доход и распределить',
      steps: ['Нажмите + → Доход → сумма.', 'Распределите по корзинам 50/30/20.',
              'Часть в Вклад, часть в копилки — остаток виден сверху.'] },
    { icon: 'ti-arrow-up-circle', title: 'Записать расход',
      steps: ['Нажмите + → Расход.', 'Категории сгруппированы по корзинам.',
              'Видно, сколько осталось в корзине за месяц.'] },
    { icon: 'ti-pig-money', title: 'Копилки: отложить и потратить',
      steps: ['Откройте «Ещё» → Копилки.', '«Пополнить» — отложить.', '«Потратить» — снять на мелкую цель.'] },
    { icon: 'ti-building-bank', title: 'Вклад: пополнить и следить за ростом',
      steps: ['Вкладку «Вклад».', '«Пополнить» — баланс растёт.', 'Снять нельзя; калькулятор показывает прогноз с %.'] },
    { icon: 'ti-percentage', title: 'Что такое 50/30/20',
      steps: ['50% — обязательные нужды, 30% — желания, 20% — в сбережения.',
              'Отклонение видно на Главной, в Плане и в Аналитике.'] },
    { icon: 'ti-calendar', title: 'Спланировать месяц',
      steps: ['Вкладка «План» → ожидаемый доход.', 'Задайте лимиты категорий.',
              '«Подогнать под 50/30/20» подровняет суммы под цель.'] },
    { icon: 'ti-lock', title: 'Закрыть месяц',
      steps: ['В «Плане» → «Закрыть месяц».', 'Остатки лимитов переносятся на следующий месяц.'] },
  ]
</script>

<div class="page-header"><h1>Как это работает</h1></div>
<div class="page">
  <div class="card hero">
    <div class="pots">
      <div class="pot"><i class="ti ti-building-bank"></i><strong>Вклад</strong><span class="muted">заморожен, +%</span></div>
      <div class="pot"><i class="ti ti-pig-money"></i><strong>Копилки</strong><span class="muted">можно тратить</span></div>
    </div>
    <div class="split">
      <span class="seg needs">Нужды 50%</span><span class="seg wants">Желания 30%</span><span class="seg sav">Сбереж. 20%</span>
    </div>
  </div>
  {#each scenarios as s}
    <div class="card faq">
      <div class="faq-h"><i class="ti {s.icon}"></i><strong>{s.title}</strong></div>
      <ol>{#each s.steps as st}<li>{st}</li>{/each}</ol>
    </div>
  {/each}
</div>

<style>
  .hero { display: flex; flex-direction: column; gap: var(--space-3); }
  .pots { display: flex; gap: var(--space-3); }
  .pot { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 2px; padding: var(--space-3);
         background: var(--bg-surface); border-radius: var(--radius-md); }
  .pot i { font-size: 26px; color: var(--gold); }
  .split { display: flex; border-radius: var(--radius-sm); overflow: hidden; font-size: var(--text-xs); }
  .seg { padding: 6px 0; text-align: center; color: #fff; }
  .seg.needs { background: var(--blue); flex: 50; }
  .seg.wants { background: var(--yellow); flex: 30; }
  .seg.sav { background: var(--green); flex: 20; }
  .faq-h { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
  .faq-h i { font-size: 20px; color: var(--blue); }
  .faq ol { margin: 0; padding-left: 18px; display: flex; flex-direction: column; gap: 4px; font-size: var(--text-sm); color: var(--text-secondary); }
</style>
