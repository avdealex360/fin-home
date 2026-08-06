<script lang="ts">
  // Инвестиции — справочный раздел: знания для новичка, рынок MOEX, AI-обзор.
  // На бюджет и 50/30/20 не влияет (как калькулятор вклада).
  import { api, type InvestMarket, type InvestOverview } from '../lib/api'
  import { showToast } from '../lib/stores'

  let market = $state<InvestMarket | null>(null)
  let overview = $state<InvestOverview | null>(null)
  let tickers = $state<string[]>([])
  let newTicker = $state('')
  let editing = $state(false)
  let busy = $state(false)
  let openCard = $state<number | null>(0)

  async function load() {
    const [wl, m] = await Promise.all([api.investWatchlist(), api.investMarket()])
    tickers = wl.tickers
    market = m
    overview = await api.investOverview()
  }
  load()

  async function saveWatchlist(next: string[]) {
    busy = true
    try {
      const wl = await api.saveInvestWatchlist(next)
      tickers = wl.tickers
      market = await api.investMarket()
    } catch (e) {
      showToast((e as Error).message)
    } finally {
      busy = false
    }
  }

  function addTicker() {
    const t = newTicker.trim().toUpperCase()
    if (!t) return
    if (tickers.includes(t)) { newTicker = ''; return }
    saveWatchlist([...tickers, t])
    newTicker = ''
  }

  function removeTicker(t: string) {
    if (tickers.length <= 1) { showToast('Нужен хотя бы один тикер'); return }
    saveWatchlist(tickers.filter((x) => x !== t))
  }

  const fmtPrice = (p: number | null) =>
    p === null ? '—' : p.toLocaleString('ru-RU', { maximumFractionDigits: 2 })

  const knowledge = [
    { title: 'ИИС: что это и какой открывать в 2026',
      body: ['С 2024 года новым инвесторам доступен только ИИС-3 — старые типы А и Б для новых договоров закрыты. ИИС-3 объединяет обе льготы: вычет на взносы (до 400 000 ₽ в год, возврат до 52 000 ₽ при ставке 13%) и освобождение дохода от налога при закрытии.',
              'Минимальный срок владения для льгот — 5 лет (для договоров, открытых в 2024–2026).',
              'Вычет на взносы имеет смысл, только если у вас есть официальный НДФЛ, который можно вернуть.',
              'Досрочное закрытие = потеря льгот. Кладите на ИИС только деньги, которые точно не понадобятся в ближайшие 5 лет.'] },
    { title: 'Классы активов: из чего выбирать',
      body: ['Акции — доля в бизнесе. Потенциально самая высокая доходность, но и самые сильные колебания.',
              'Облигации (ОФЗ, корпоративные) — вы даёте в долг под фиксированный процент. Предсказуемо, но доходность ниже.',
              'Фонды (БПИФ) — корзина бумаг одной покупкой: диверсификация без анализа отдельных компаний. Для новичка обычно лучший старт.',
              'Фонды денежного рынка (например LQDT) — «почти вклад» внутри брокерского счёта: низкий риск, доходность около ключевой ставки.'] },
    { title: 'Диверсификация: не клади всё в одну корзину',
      body: ['Распределяйте между классами активов (акции/облигации), а не только между разными акциями.',
              'Один фонд на индекс МосБиржи уже даёт долю в ~40–50 крупнейших компаниях РФ.',
              'Не держите весь портфель в бумагах одной компании — даже если это ваш любимый Сбер.',
              'Помните о валютной и страновой концентрации: весь российский рынок — это тоже одна «корзина».'] },
    { title: 'Типовые портфели новичка',
      body: ['Консервативный: 70–80% облигации/фонд денежного рынка, 20–30% фонд на индекс акций. Минимальные просадки.',
              'Сбалансированный: 50/50 акции (через фонд) и облигации. Классика для горизонта 5+ лет.',
              'Правило большого пальца: доля облигаций ≈ ваш возраст в процентах.',
              'Главное — регулярность: пополнять портфель каждый месяц важнее, чем угадать момент входа.'] },
    { title: 'Типичные ошибки новичка',
      body: ['Инвестировать без финансовой подушки (3–6 месяцев расходов на вкладе/накопительном счёте).',
              'Покупать на эмоциях то, что выросло, и продавать в панике то, что упало.',
              'Частые сделки: комиссии и налоги съедают доходность. Стратегия «купил и держи» новичку почти всегда выгоднее.',
              'Верить обещаниям гарантированной доходности выше вклада — так не бывает без риска.'] },
    { title: 'Особенности у Сбера',
      body: ['Приложение СберИнвестор: ИИС открывается онлайн за несколько минут.',
              'У Сбера свои БПИФ без комиссии за сделку в своём приложении: SBMX (индекс МосБиржи), SBGB (гособлигации), SBCB и другие.',
              'Комиссии фонда (TER) всё равно есть — они зашиты в цену пая, сравнивайте у аналогов.',
              'Вычет по ИИС оформляется через личный кабинет ФНС; Сбер отдаёт справки автоматически.'] },
  ]
</script>

<div class="page">
  <section class="card">
    <h2 class="card-title">Рынок сегодня</h2>
    {#if !market}
      <p class="muted">Загружаю котировки…</p>
    {:else if market.error}
      <p class="muted">Данные MOEX временно недоступны. Попробуйте позже.</p>
    {:else}
      <div class="quotes">
        {#each market.quotes as q}
          <div class="quote">
            <div class="q-name">
              <strong>{q.ticker}</strong>
              <span class="muted">{q.name}</span>
            </div>
            <div class="q-val">
              <span class="mono">{fmtPrice(q.price)}</span>
              {#if q.change_pct !== null}
                <span class="chg" class:up={q.change_pct >= 0} class:down={q.change_pct < 0}>
                  {q.change_pct >= 0 ? '▲' : '▼'} {Math.abs(q.change_pct).toFixed(2)}%
                </span>
              {/if}
            </div>
            {#if editing}
              <button class="rm" onclick={() => removeTicker(q.ticker)} disabled={busy}
                      aria-label="Убрать {q.ticker}">✕</button>
            {/if}
          </div>
        {/each}
      </div>
    {/if}
    <div class="wl-edit">
      <button class="btn btn-ghost" onclick={() => (editing = !editing)}>
        {editing ? 'Готово' : 'Изменить список'}
      </button>
      {#if editing}
        <form class="add" onsubmit={(e) => { e.preventDefault(); addTicker() }}>
          <input placeholder="Тикер, напр. LKOH" bind:value={newTicker} maxlength="12" />
          <button class="btn btn-primary" type="submit" disabled={busy}>Добавить</button>
        </form>
      {/if}
    </div>
    <p class="muted src">Котировки: Московская биржа (ISS), задержка до 10 минут.</p>
  </section>

  <section class="card">
    <h2 class="card-title">AI-обзор рынка</h2>
    {#if !overview}
      <p class="muted">Загружаю…</p>
    {:else if !overview.configured}
      <p class="muted">
        Чтобы получать ежедневный обзор, настройте ключи AI в
        <a href="#/integrations">«Интеграциях»</a>.
      </p>
    {:else if overview.text}
      <p class="ov">{overview.text}</p>
    {:else}
      <p class="muted">Обзор сегодня недоступен (нет данных рынка или AI не ответил).</p>
    {/if}
  </section>

  <section class="kb">
    <h2 class="card-title kb-title">База знаний</h2>
    {#each knowledge as k, i}
      <div class="card kcard">
        <button class="k-head" onclick={() => (openCard = openCard === i ? null : i)}>
          <strong>{k.title}</strong>
          <i class="ti {openCard === i ? 'ti-chevron-up' : 'ti-chevron-down'}"></i>
        </button>
        {#if openCard === i}
          <ul>{#each k.body as line}<li>{line}</li>{/each}</ul>
        {/if}
      </div>
    {/each}
    <p class="muted src">
      Раздел справочный: на бюджет и 50/30/20 не влияет. Покупки на ИИС записывайте
      обычной операцией в категории корзины «Сбережения».
    </p>
  </section>
</div>

<style>
  .page { display: flex; flex-direction: column; gap: 12px; padding-bottom: 40px; }
  .quotes { display: flex; flex-direction: column; }
  .quote { display: flex; align-items: center; gap: 10px; padding: 10px 0;
           border-bottom: 1px solid var(--border, rgba(255,255,255,.06)); }
  .quote:last-child { border-bottom: none; }
  .q-name { flex: 1; display: flex; flex-direction: column; min-width: 0; }
  .q-name .muted { font-size: var(--text-xs); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .q-val { display: flex; align-items: baseline; gap: 8px; }
  .mono { font-family: var(--font-mono, monospace); }
  .chg { font-size: var(--text-xs); }
  .chg.up { color: var(--green); }
  .chg.down { color: var(--red); }
  .rm { background: none; border: none; color: var(--text-muted); font-size: 16px; padding: 4px 6px; }
  .wl-edit { display: flex; flex-direction: column; gap: 8px; margin-top: 8px; }
  .add { display: flex; gap: 8px; }
  .add input { flex: 1; text-transform: uppercase; }
  .src { font-size: var(--text-xs); margin: 8px 0 0; }
  .ov { white-space: pre-line; margin: 0; font-size: var(--text-sm); line-height: 1.5; }
  .kb { display: flex; flex-direction: column; gap: 8px; }
  .kb-title { margin-bottom: 0; }
  .kcard { padding: 0; overflow: hidden; }
  .k-head { display: flex; justify-content: space-between; align-items: center; width: 100%;
            background: none; border: none; color: inherit; padding: 14px 16px; font-size: var(--text-sm);
            text-align: left; cursor: pointer; }
  .kcard ul { margin: 0; padding: 0 16px 14px 32px; display: flex; flex-direction: column; gap: 6px;
              font-size: var(--text-sm); color: var(--text-secondary); }
  .muted { color: var(--text-muted); }
</style>
