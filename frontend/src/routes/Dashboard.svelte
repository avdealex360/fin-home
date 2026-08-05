<script lang="ts">
  import { api, type Category, type MonthSummary, type Transaction } from '../lib/api'
  import { period, dataVersion, showHelp, showToast, invalidate, navigate } from '../lib/stores'
  import { wallet, loadWalletOnce, loadWallet, refreshIfStale } from '../lib/wallet'
  import { money, monthName, formatDate, usdcRound, usdcParts, timeOnly } from '../lib/format'
  import { monthPace } from '../lib/insights'
  import ProgressBar from '../lib/components/ProgressBar.svelte'
  import Loader from '../lib/components/Loader.svelte'
  import TxForm from '../lib/components/TxForm.svelte'
  import BottomSheet from '../lib/components/BottomSheet.svelte'

  let summary = $state<MonthSummary | null>(null)
  let recent = $state<Transaction[]>([])
  let plan = $state<any>(null)
  let categories = $state<Category[]>([])

  $effect(() => {
    const { year, month } = $period
    void $dataVersion
    load(year, month)
  })

  async function load(year: number, month: number) {
    const [s, r, p, c] = await Promise.all([
      api.dashboard(year, month),
      api.transactions(8, year, month),
      api.plan(year, month),
      api.categories(),
    ])
    summary = s
    recent = r
    plan = p
    categories = c
  }

  let pace = $derived(
    summary
      ? monthPace(summary.total_spent, plan?.expected_income || summary.income_fact, $period.year, $period.month)
      : null,
  )

  // "Свободно" is the one number the whole screen is built around:
  // income that actually arrived − spent − what was moved to savings.
  let saved = $derived(summary?.groups.find((g) => g.name === 'savings')?.spent ?? 0)
  let perDay = $derived(pace && pace.daysLeft > 0 ? (summary?.balance ?? 0) / pace.daysLeft : 0)
  let paceDelta = $derived(
    pace && perDay > 0 ? Math.round(((pace.perDaySoFar - perDay) / perDay) * 100) : 0,
  )

  let catRows = $derived.by(() => {
    if (!plan?.limits || !categories.length) return []
    const byId = new Map(categories.map((c) => [c.id, c]))
    return plan.limits
      .map((l: any) => {
        const cat = byId.get(l.category_id)
        const pct = l.limit_amount > 0 ? (l.spent / l.limit_amount) * 100 : 0
        return {
          name: cat?.name ?? 'Категория',
          icon: cat?.icon ?? 'ti-circle',
          color: pct > 100 ? 'red' : pct > 90 ? 'yellow' : 'green',
          spent: l.spent,
          limit: l.limit_amount,
          left: l.limit_amount - l.spent,
          pct: Math.round(pct),
        }
      })
      .filter((r: any) => r.limit > 0)
      .sort((a: any, b: any) => b.spent - a.spent)
  })

  // Кошелёк USDC: если он настроен, тап по большому числу переворачивает карточку
  // с рублёвого баланса на баланс кошелька (и обратно).
  loadWalletOnce()
  let flipped = $state(false)
  let walletBusy = $state(false)
  // Календарный месяц, а не просматриваемый: правило «одно письмо в месяц» живёт
  // по реальной дате, независимо от того, какой месяц открыт в шапке.
  const currentMonthKey = (() => {
    const now = new Date()
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
  })()

  let walletAmount = $derived(usdcParts($wallet?.balance))

  function toggleFlip() {
    flipped = !flipped
    if (flipped) void refreshIfStale()
  }
  async function refreshWallet() {
    walletBusy = true
    try { await loadWallet(true) } finally { walletBusy = false }
  }

  let editingTx = $state<Transaction | null>(null)
  function openEdit(tx: Transaction) { editingTx = tx }
  function onEdited() { editingTx = null; invalidate(); showToast('Операция изменена') }

  async function del(tx: Transaction) {
    recent = recent.filter((t) => t.id !== tx.id)
    await api.deleteTransaction(tx.id)
    invalidate()
    showToast('Операция удалена', async () => {
      await api.createTransaction({
        type: tx.type, amount: tx.amount, category_id: tx.category_id,
        user_id: tx.user_id, date: tx.date, comment: tx.comment,
      })
      invalidate()
    })
  }
</script>

{#if !summary || !pace}
  <Loader />
{:else}
  <div class="page">
    <div class="cols stretch">
      <!-- HERO: one number, and the arithmetic behind it. -->
      <section class="hero col-wide">
        <div class="hero-top">
          <span class="section-label">{flipped ? 'Кошелёк USDC (ERC-20)' : 'Свободно до конца месяца'}</span>
          {#if flipped}
            <span class="chip blue"><i class="ti ti-currency-ethereum"></i>Ethereum</span>
          {:else}
            <span class="chip blue">осталось {pace.daysLeft} дн.</span>
          {/if}
        </div>

        {#if $wallet?.configured}
          <!-- Переворот: рубли ⇄ баланс кошелька. Показываем только когда кошелёк настроен. -->
          <button
            class="flip"
            class:flipped
            title="Нажмите, чтобы перевернуть: рубли ⇄ USDC"
            aria-label={flipped ? 'Показать рублёвый баланс' : 'Показать баланс кошелька USDC'}
            onclick={toggleFlip}
          >
            <span class="flip-inner">
              <span class="face num hero-amount">
                {money(summary.balance)} ₽<i class="ti ti-rotate-2 flip-hint"></i>
              </span>
              <span class="face back num hero-amount">
                <span>{walletAmount[0]}<span class="frac">{walletAmount[1]}</span></span>
                <span class="ticker">USDC</span>
              </span>
            </span>
          </button>
        {:else}
          <div class="num hero-amount">{money(summary.balance)} ₽</div>
        {/if}

        {#if $showHelp}
          <p class="explain">
            {#if flipped}
              Баланс кошелька по данным Etherscan, обновляется раз в 5 минут. На бюджет не
              влияет: когда зарплата придёт — запишите её обычной операцией «Доход».
            {:else}
              Сквозной баланс: остаток прошлых месяцев плюс доход этого месяца, минус траты
              и отложенное. Начальный остаток задаётся в «Ещё» → «Начальный остаток».
            {/if}
          </p>
        {/if}

        {#if flipped && $wallet}
          <div class="formula num">
            <span class="f blue">Адрес {$wallet.address}</span>
            <span class="f green">Обновлено {timeOnly($wallet.checked_at) || '—'}</span>
            {#if $wallet.threshold > 0}
              <span class="f gold">Порог {usdcRound($wallet.threshold)}</span>
            {/if}
          </div>
          {#if $wallet.error}
            <p class="explain wallet-err">Etherscan: {$wallet.error}</p>
          {/if}

          <div class="hero-foot">
            <div>
              <div class="k">Уведомление в Telegram</div>
              <div class="v vtext {$wallet.threshold > 0 ? 'green' : 'yellow'}">
                {$wallet.threshold > 0 ? `от ${usdcRound($wallet.threshold)} USDC` : 'порог не задан'}
              </div>
            </div>
            <div>
              <div class="k">За этот месяц</div>
              <div class="v vtext blue">
                {$wallet.alert_month === currentMonthKey ? 'уже отправлено' : 'ещё не отправляли'}
              </div>
            </div>
            <button class="chip blue wrefresh" onclick={refreshWallet} disabled={walletBusy}>
              <i class="ti ti-refresh"></i>{walletBusy ? 'Обновляю…' : 'Обновить'}
            </button>
          </div>
        {:else}
          <!-- «Траты» здесь без сбережений: отложенное вынесено отдельным слагаемым,
               иначе оно визуально вычиталось бы дважды и формула не сходилась бы
               с числом сверху. -->
          <div class="formula num">
            <span class="f blue">Остаток {money(summary.carryover)}</span>
            <span class="op">+</span>
            <span class="f green">Доход {money(summary.income_fact)}</span>
            <span class="op">−</span>
            <span class="f red">Траты {money(summary.total_spent - saved)}</span>
            <span class="op">−</span>
            <span class="f gold">Отложено {money(saved)}</span>
          </div>

          <div class="hero-foot">
            <div>
              <div class="k">Можно тратить в день</div>
              <div class="num v green">{money(perDay)} ₽</div>
            </div>
            <div>
              <div class="k">Тратите сейчас в день</div>
              <div class="num v yellow">{money(pace.perDaySoFar)} ₽</div>
            </div>
            {#if paceDelta > 3}
              <span class="chip yellow"><i class="ti ti-trending-up"></i>Темп выше плана на {paceDelta}%</span>
            {:else}
              <span class="chip green"><i class="ti ti-check"></i>Идёте в графике</span>
            {/if}
          </div>
        {/if}
      </section>

      <!-- KPI tiles -->
      <section class="col grid-tiles">
        <div class="card tile">
          <div class="row"><span class="k">Доход за месяц</span><i class="ti ti-arrow-down-left green"></i></div>
          <div class="num v green">{money(summary.income_fact)} ₽</div>
          {#if summary.salary_diff !== null && summary.salary_diff !== undefined}
            <div class="k">{summary.salary_diff >= 0 ? '+' : '−'}{money(Math.abs(summary.salary_diff))} ₽ к прошлому месяцу</div>
          {/if}
          {#if $showHelp}<div class="hint">Всё, что фактически пришло на счета в этом месяце.</div>{/if}
        </div>

        <div class="card tile">
          <div class="row"><span class="k">Потрачено</span><i class="ti ti-arrow-up-right red"></i></div>
          <div class="num v red">{money(summary.total_spent)} ₽</div>
          <div class="k">прогноз к концу месяца {money(pace.projected)} ₽</div>
          {#if $showHelp}<div class="hint">Сумма расходных операций с 1-го числа, включая обязательные платежи.</div>{/if}
        </div>

        <div class="card tile">
          <div class="row"><span class="k">Отложено</span><i class="ti ti-pig-money gold"></i></div>
          <div class="num v gold">{money(saved)} ₽</div>
          <div class="k">цель месяца {money((summary.income_fact * summary.savings_target_rate) / 100)} ₽</div>
          {#if $showHelp}<div class="hint">Переводы в накопления. Это не расход — деньги остаются вашими.</div>{/if}
        </div>

        <div class="card tile">
          <div class="row"><span class="k">Норма сбережений</span><i class="ti ti-target-arrow blue"></i></div>
          <div class="num v blue">{summary.savings_rate.toFixed(1)}%</div>
          <div class="k">цель {summary.savings_target_rate}%</div>
          {#if $showHelp}<div class="hint">Доля дохода, которую удалось не потратить. Главный показатель здоровья бюджета.</div>{/if}
        </div>
      </section>
    </div>

    <div class="cols stretch">
      <!-- 50/30/20 -->
      <section class="card col-wide">
        <div class="row">
          <h2 class="card-title">Правило 50/30/20</h2>
          <span class="dim small">от дохода {money(summary.income_fact)} ₽</span>
        </div>
        {#if $showHelp}
          <p class="explain">
            Половина дохода — на обязательное, треть — на желания, пятая часть — в накопления.
            Светлая риска на шкале показывает, где вы должны быть по календарю на сегодня.
          </p>
        {/if}
        <div class="stack meters">
          {#each summary.groups as g}
            <div>
              <div class="row">
                <span class="mname">{g.label} <span class="dim small">цель {g.percent}%</span></span>
                <span class="num small muted">{money(g.spent)} / {money(g.limit)} ₽</span>
              </div>
              <ProgressBar spent={g.spent} limit={g.limit} color={g.color} showPace={true} />
              <div class="small" style="color: var(--{g.color}); margin-top: 6px">
                {#if g.name === 'savings'}
                  {g.remaining > 0 ? `Не хватает ${money(g.remaining)} ₽ до цели месяца` : 'Цель месяца выполнена'}
                {:else}
                  {g.remaining > 0 ? `Свободно ещё ${money(g.remaining)} ₽` : `Перерасход ${money(-g.remaining)} ₽`}
                {/if}
              </div>
            </div>
          {/each}
        </div>
      </section>

      <!-- Category limits -->
      <section class="card col">
        <div class="row">
          <h2 class="card-title">Лимиты категорий</h2>
          <a href="#/plan" onclick={(e) => { e.preventDefault(); navigate('plan') }}>Настроить</a>
        </div>
        {#if catRows.length === 0}
          <p class="muted small" style="margin-top: 12px">
            Лимиты не заданы. Задайте их в разделе «План» — без лимитов не видно, где вы выходите за рамки.
          </p>
        {:else}
          <div class="stack cats">
            {#each catRows as c}
              <div class="cat">
                <span class="cat-ic {c.color}"><i class="ti {c.icon}"></i></span>
                <div class="cat-body">
                  <div class="row">
                    <span class="small">{c.name}</span>
                    <span class="num small muted">{money(c.spent)} / {money(c.limit)}</span>
                  </div>
                  <ProgressBar spent={c.spent} limit={c.limit} color={c.color} />
                </div>
                <span class="num cat-pct {c.color}">{c.pct}%</span>
              </div>
            {/each}
          </div>
        {/if}
      </section>
    </div>

    <div class="cols stretch">
      <!-- Recent -->
      <section class="card col-wide">
        <div class="row">
          <h2 class="card-title">Последние операции</h2>
          <a href="#/transactions" onclick={(e) => { e.preventDefault(); navigate('transactions') }}>Все операции</a>
        </div>
        {#if recent.length === 0}
          <p class="muted small" style="margin-top: 12px">Пока нет операций. Нажмите «Операция», чтобы добавить первую.</p>
        {:else}
          <div class="txs">
            {#each recent as t (t.id)}
              <div class="tx">
                <div class="tx-main">
                  <div class="small">{t.category_name ?? (t.type === 'income' ? 'Доход' : 'Без категории')}</div>
                  <div class="dim tiny">
                    {formatDate(t.date)}{t.user_name ? ` · ${t.user_name}` : ''}{t.comment ? ` · ${t.comment}` : ''}
                  </div>
                </div>
                <span class="num amt" class:income={t.type === 'income'}>
                  {t.type === 'income' ? '+' : '−'} {money(t.amount)} ₽
                </span>
                <button class="tx-edit" aria-label="Изменить" onclick={() => openEdit(t)}><i class="ti ti-pencil"></i></button>
                <button class="tx-del" aria-label="Удалить" onclick={() => del(t)}><i class="ti ti-trash"></i></button>
              </div>
            {/each}
          </div>
        {/if}
      </section>

      <!-- Debts + planned -->
      <section class="col stack">
        {#if summary.funds.length}
          <div class="card">
            <h2 class="card-title">Накопления и цели</h2>
            {#if $showHelp}<p class="explain">Сколько собрано по каждой цели и сколько осталось.</p>{/if}
            <div class="stack" style="margin-top: 12px">
              {#each summary.funds as f}
                <div>
                  <div class="row">
                    <span class="small">{f.name}</span>
                    <span class="num small muted">{money(f.current_amount)} / {money(f.target_amount)}</span>
                  </div>
                  <ProgressBar spent={f.current_amount} limit={f.target_amount} color="blue" />
                  {#if f.monthly_contribution > 0 && f.target_amount > f.current_amount}
                    <div class="dim tiny" style="margin-top: 6px">
                      При {money(f.monthly_contribution)} ₽ в месяц — ещё
                      {Math.ceil((f.target_amount - f.current_amount) / f.monthly_contribution)} мес.
                    </div>
                  {/if}
                </div>
              {/each}
            </div>
          </div>
        {/if}

        {#if summary.debts.length}
          <div class="card">
            <h2 class="card-title">Долги</h2>
            <div class="stack" style="margin-top: 12px">
              {#each summary.debts as d}
                <div>
                  <div class="row">
                    <span class="small">{d.name} <span class="dim tiny">{d.interest_rate > 0 ? `${d.interest_rate}%` : 'без %'}</span></span>
                    <span class="num small muted">осталось {money(d.remaining)}</span>
                  </div>
                  <ProgressBar spent={d.total_amount - d.remaining} limit={d.total_amount} color="blue" />
                  {#if d.priority_label}
                    <div class="tiny" style="color: var(--yellow); margin-top: 6px">{d.priority_label}: ставка выше — гасить первым</div>
                  {/if}
                </div>
              {/each}
            </div>
          </div>
        {/if}

        {#if plan?.planned_expenses?.length}
          <div class="card">
            <h2 class="card-title">Крупные расходы впереди</h2>
            <div class="stack" style="margin-top: 12px">
              {#each plan.planned_expenses as e}
                <div class="row">
                  <span class="small">{e.description}{#if e.expected_date}<span class="dim tiny"> · {formatDate(e.expected_date)}</span>{/if}</span>
                  <span class="num small">{money(e.amount)} ₽</span>
                </div>
              {/each}
            </div>
          </div>
        {/if}
      </section>
    </div>
  </div>
{/if}

<BottomSheet open={!!editingTx} title="Изменить операцию" onclose={() => (editingTx = null)}>
  {#snippet children()}
    {#if editingTx}<TxForm existing={editingTx} onsubmitted={onEdited} />{/if}
  {/snippet}
</BottomSheet>

<style>
  .hero {
    background: linear-gradient(155deg, #1b2740 0%, var(--bg-surface) 62%);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: var(--radius-xl);
    padding: var(--space-5) var(--space-6);
    box-shadow: var(--shadow-card);
    display: flex;
    flex-direction: column;
  }
  .hero-top { display: flex; align-items: center; gap: var(--space-2); }
  .hero-top .section-label { margin-bottom: 0; }
  .hero-amount { font-size: clamp(38px, 4.4vw, 52px); font-weight: 600; letter-spacing: -0.02em; margin: 8px 0 2px; }

  /* Переворот главного числа: рубли на лицевой стороне, кошелёк USDC на обратной.
     Обе стороны лежат в одной grid-ячейке, поэтому высота карточки не прыгает. */
  .flip {
    align-self: flex-start;
    padding: 0; border: none; background: none; text-align: left;
    perspective: 900px; cursor: pointer;
  }
  .flip-inner {
    display: grid;
    transform-style: preserve-3d;
    transition: transform 0.55s cubic-bezier(0.34, 1.1, 0.4, 1);
  }
  .flip.flipped .flip-inner { transform: rotateX(180deg); }
  /* flex-wrap: длинный баланс (7 знаков + тикер) переносится, а не вылезает за карточку. */
  .face {
    grid-area: 1 / 1; backface-visibility: hidden;
    display: flex; align-items: baseline; flex-wrap: wrap; gap: 8px;
  }
  .face.back { transform: rotateX(180deg); color: var(--blue); }
  .ticker { font-size: 0.42em; font-weight: 600; letter-spacing: 0.04em; color: var(--text-secondary); }
  .frac { font-size: 0.55em; color: var(--text-secondary); }
  .flip-hint { font-size: 17px; color: var(--text-muted); align-self: center; }
  .flip:hover .flip-hint { color: var(--blue); }
  .wallet-err { color: var(--red); }
  /* Текст вместо суммы: моно-шрифт и 19px тут были бы тяжеловесны. */
  .vtext { font-size: 15px; font-weight: 500; }
  /* .chip рассчитан на span: у button остаётся рамка агента, и палец требует
     цели повыше, чем 26px чипа. */
  .hero-foot .wrefresh { border: none; min-height: 36px; padding: 0 14px; }
  .hero-foot .wrefresh:disabled { opacity: 0.6; }

  @media (prefers-reduced-motion: reduce) {
    .flip-inner { transition: none; }
  }

  .formula { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-top: var(--space-4); font-size: 12.5px; }
  .formula .f { padding: 6px 11px; border-radius: 10px; }
  .formula .green { background: rgba(62, 207, 142, 0.1); color: var(--green); }
  .formula .red { background: rgba(240, 104, 106, 0.1); color: var(--red); }
  .formula .gold { background: rgba(216, 162, 74, 0.12); color: var(--gold); }
  .formula .op { align-self: center; color: var(--text-muted); }
  /* На узких экранах формула не влезает в строку — раскладываем построчно. */
  @media (max-width: 560px) {
    .formula { flex-direction: column; align-items: stretch; gap: 6px; margin-bottom: var(--space-2); }
    .formula .op { display: none; }
    .formula .f { text-align: left; }
  }

  .hero-foot {
    display: flex; flex-wrap: wrap; gap: var(--space-3); align-items: center;
    margin-top: auto; padding-top: var(--space-4);
    border-top: 1px solid rgba(255, 255, 255, 0.07);
  }
  .hero-foot > div { flex: 1 1 140px; }

  .k { font-size: 11.5px; color: var(--text-secondary); }
  .v { font-size: 19px; font-weight: 600; margin-top: 2px; }
  .tile .v { font-size: 23px; margin: 7px 0 4px; }
  .hint {
    font-size: 11.5px; line-height: 1.45; color: var(--text-muted);
    margin-top: 8px; padding-top: 8px; border-top: 1px solid rgba(255, 255, 255, 0.05);
  }
  .card.tile { padding: var(--space-4); border-radius: var(--radius-md); }

  .green { color: var(--green); }
  .red { color: var(--red); }
  .gold { color: var(--gold); }
  .blue { color: var(--blue); }
  .yellow { color: var(--yellow); }

  .small { font-size: var(--text-sm); }
  .tiny { font-size: var(--text-xs); }

  .meters { margin-top: var(--space-4); gap: var(--space-4); }
  .mname { font-size: 14px; font-weight: 500; }

  .cats { margin-top: var(--space-4); }
  .cat { display: grid; grid-template-columns: 26px 1fr 40px; align-items: center; gap: 11px; }
  .cat-ic { width: 26px; height: 26px; border-radius: 8px; display: grid; place-items: center; font-size: 15px; }
  .cat-ic.green { background: var(--green-bg); color: var(--green); }
  .cat-ic.yellow { background: var(--yellow-bg); color: var(--yellow); }
  .cat-ic.red { background: var(--red-bg); color: var(--red); }
  .cat-body { min-width: 0; display: flex; flex-direction: column; gap: 6px; }
  .cat-pct { font-size: 12px; font-weight: 600; text-align: right; }
  .cat-pct.green { color: var(--green); }
  .cat-pct.yellow { color: var(--yellow); }
  .cat-pct.red { color: var(--red); }

  .txs { margin-top: var(--space-2); }
  .tx { display: flex; align-items: center; gap: var(--space-3); padding: 11px 0; border-bottom: 1px solid var(--line); }
  .tx:last-child { border-bottom: none; }
  .tx-main { flex: 1; min-width: 0; }
  .amt { font-size: 14px; font-weight: 500; white-space: nowrap; }
  .amt.income { color: var(--green); }
  .tx-edit {
    width: 32px; height: 32px; flex: 0 0 32px; border: none; border-radius: 9px;
    background: transparent; color: var(--text-muted); display: grid; place-items: center;
  }
  .tx-edit:hover { background: var(--bg-elevated); color: var(--text-primary); }
  .tx-del {
    width: 32px; height: 32px; flex: 0 0 32px; border: none; border-radius: 9px;
    background: transparent; color: var(--text-muted); display: grid; place-items: center;
  }
  .tx-del:hover { background: var(--red-bg); color: var(--red); }
</style>
