<script lang="ts">
  const scenarios = [
    { icon: 'ti-wallet', title: 'Как устроены деньги',
      steps: ['Доход делится на 3 корзины: Нужды 50%, Желания 30%, Сбережения 20%.',
              'Сбережения — это категории (например «Пополнение вклада») и Копилки, как обычные траты внутри своей корзины.'] },
    { icon: 'ti-arrow-down-circle', title: 'Записать доход и распределить',
      steps: ['Нажмите + → Доход → сумма.', 'Распределите по корзинам 50/30/20.',
              'Часть — в копилки или категорию сбережений, остаток виден сверху.'] },
    { icon: 'ti-arrow-up-circle', title: 'Записать расход',
      steps: ['Нажмите + → Расход.', 'Категории сгруппированы по корзинам.',
              'Видно, сколько осталось в корзине за месяц.'] },
    { icon: 'ti-pig-money', title: 'Копилки: отложить и потратить',
      steps: ['Откройте «Ещё» → Копилки.', '«Пополнить» — отложить.', '«Потратить» — снять на мелкую цель.'] },
    { icon: 'ti-building-bank', title: 'Вклад: калькулятор капитализации',
      steps: ['«Ещё» → «Калькулятор вклада».', 'Первый взнос, ставки по годам, срок и план пополнения.',
              'Это справка: на бюджет и 50/30/20 не влияет, реальное пополнение вклада записывайте как обычный расход.'] },
    { icon: 'ti-percentage', title: 'Что такое 50/30/20',
      steps: ['50% — обязательные нужды, 30% — желания, 20% — в сбережения.',
              'Отклонение видно на Главной, в Плане и в Аналитике.'] },
    { icon: 'ti-calendar', title: 'Спланировать месяц',
      steps: ['Вкладка «План» → укажите ожидаемый доход, он сохранится сам.', 'Задайте лимиты категорий по каждой корзине.'] },
    { icon: 'ti-lock', title: 'Закрыть месяц',
      steps: ['В «Плане» → «Закрыть месяц».', 'Остатки лимитов переносятся на следующий месяц.'] },
    { icon: 'ti-list', title: 'Все операции: смотреть и править',
      steps: ['«Ещё» → «Все операции» (или тапните «Последние операции» на Главной).',
              'Фильтры по типу/категории/участнику, сортировка, страницы.',
              'Тап по операции → «Изменить» или «Удалить».'] },
    { icon: 'ti-category', title: 'Категории: свои под себя',
      steps: ['«Ещё» → «Категории».', 'Добавляйте, переименовывайте, удаляйте.',
              'Если категория уже использовалась — она скрывается, а не удаляется: история и отчёты не портятся.'] },
  ]
</script>

<div class="page-header"><h1>Как это работает</h1></div>
<div class="page">
  <div class="card hero">
    <div class="pots">
      <div class="pot"><i class="ti ti-coin"></i><strong>Категория «Сбережения»</strong><span class="muted">как обычный расход</span></div>
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
