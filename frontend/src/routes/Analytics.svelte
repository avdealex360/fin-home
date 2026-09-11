<script lang="ts">
  import { api, type MonthOutlook, type Transaction } from '../lib/api'
  import { period, dataVersion, showHelp } from '../lib/stores'
  import { money, monthName } from '../lib/format'
  import { monthPace, dailySpend, cumulative, firstWeekday, recurringSplit, buildInsights } from '../lib/insights'
  import Loader from '../lib/components/Loader.svelte'
  import Sparkline from '../lib/components/Sparkline.svelte'
  import CashFlowChart from '../lib/components/CashFlowChart.svelte'
  import ForecastChart from '../lib/components/ForecastChart.svelte'
  import Donut from '../lib/components/Donut.svelte'
  import DaysHeatmap from '../lib/components/DaysHeatmap.svelte'

  const PALETTE = ['#6a9bff', '#3ecf8e', '#f2b84b', '#d8a24a', '#f0686a', '#4f82ec', '#2fae76', '#7e879c']
  const PERIOD_LABELS: Record<string, string> = { month: 'Месяц', quarter: 'Квартал', year: 'Год' }

  let data = $state<any>(null)
  let monthTxs = $state<Transaction[]>([])
  let summary = $state<any>(null)
  let plan = $state<any>(null)
  let outlook = $state<MonthOutlook | null>(null)
  let periodType = $state<'month' | 'quarter' | 'year'>('month')

  $effect(() => {
    const { year, month } = $period
    void $dataVersion
    void periodType
    data = null
    load(year, month, periodType)
  })

  async function load(year: number, month: number, p: typeof periodType) {
    const [a, txs, s, pl, o] = await Promise.all([
      api.analytics(year, month, p),
      api.transactionsList({ year, month, limit: 500 }),
      api.dashboard(year, month),
      api.plan(year, month),
      api.outlook(year, month).catch(() => null),
    ])
    data = a
    monthTxs = txs.items
    summary = s
    plan = pl
    outlook = o
  }

  // ─── Pace & forecast ────────────────────────────────────────────────
  let hasPlanLimits = $derived(Boolean(plan?.limits?.length))
  let planLimit = $derived(
    hasPlanLimits
      ? plan.limits.reduce((s: number, l: any) => s + l.limit_amount, 0)
      : (summary?.income_fact ?? 0) * 0.8,
  )
  let pace = $derived(
    summary ? monthPace(summary.total_spent, planLimit, $period.year, $period.month) : null,
  )
  let daily = $derived(pace ? dailySpend(monthTxs, pace.daysInMonth) : [])
  let cumDaily = $derived(pace ? cumulative(daily, pace.day) : [])
  // Outlook is history-based; without a past month there is nothing to project.
  let hasOutlook = $derived(Boolean(outlook && outlook.history_months > 0))
  // The chart tracks all expenses (incl. savings transfers) like the plan does,
  // so the forecast line adds this month's savings back on top of the spend forecast.
  let forecastTotal = $derived(hasOutlook && outlook && pace && pace.daysLeft > 0 ? outlook.forecast_total + outlook.spent_savings : null)
  let vsPrev = $derived.by(() => {
    if (!outlook || !outlook.prev_same_day || outlook.day < 3) return null
    return Math.round(((outlook.spent - outlook.prev_same_day) / outlook.prev_same_day) * 100)
  })

  // ─── Trends ─────────────────────────────────────────────────────────
  let trends = $derived(data?.monthly_trends ?? [])
  let trendLabels = $derived(trends.map((t: any) => monthName(t.month).slice(0, 3).toLowerCase()))
  let hasTrend = $derived(trends.some((t: any) => t.income || t.expense))

  let statTiles = $derived.by(() => {
    if (!summary || !pace) return []
    const expenses = trends.map((t: any) => t.expense)
    const incomes = trends.map((t: any) => t.income)
    const prev = trends.length > 1 ? trends[trends.length - 2] : null
    const pct = (now: number, before: number) => (before > 0 ? ((now - before) / before) * 100 : 0)
    const dExp = prev ? pct(summary.total_spent, prev.expense) : 0
    const net = summary.income_fact - summary.total_spent
    const dNet = prev ? net - (prev.income - prev.expense) : 0
    return [
      {
        label: 'Расходы за месяц', value: `${money(summary.total_spent)} ₽`, color: 'var(--red)',
        spark: expenses, delta: `${dExp >= 0 ? '+' : '−'}${Math.abs(dExp).toFixed(1)}%`,
        deltaColor: dExp > 0 ? 'var(--red)' : 'var(--green)', note: 'к прошлому месяцу',
        hint: 'Сумма всех расходных операций за период.',
      },
      {
        label: 'Обычный день', value: `${money(outlook?.median_day ?? 0)} ₽`, color: 'var(--yellow)',
        spark: null,
        delta: forecastTotal !== null ? `итог ≈ ${money(forecastTotal)} ₽` : (outlook?.oneoffs_total ? `разовых ${money(outlook.oneoffs_total)} ₽` : ''),
        deltaColor: 'var(--text-secondary)', note: forecastTotal !== null ? 'по обычным месяцам' : '',
        hint: 'Медиана трат за день: аренда и крупные разовые покупки её не сдвигают, в отличие от среднего.',
      },
      {
        label: 'Норма сбережений', value: `${summary.savings_rate.toFixed(1)}%`, color: 'var(--blue)',
        spark: trends.map((t: any) => (t.income > 0 ? (t.savings / t.income) * 100 : 0)),
        delta: `цель ${summary.savings_target_rate}%`,
        deltaColor: summary.savings_rate >= summary.savings_target_rate ? 'var(--green)' : 'var(--red)',
        note: '', hint: 'Какую долю дохода удалось отложить. Здоровым считается 20% и выше.',
      },
      {
        label: 'Чистый поток', value: `${money(summary.income_fact - summary.total_spent)} ₽`, color: 'var(--green)',
        spark: trends.map((t: any) => t.income - t.expense),
        delta: `${dNet >= 0 ? '+' : '−'}${money(Math.abs(dNet))} ₽`,
        deltaColor: dNet >= 0 ? 'var(--green)' : 'var(--red)', note: 'к прошлому месяцу',
        hint: 'Доход минус расход — именно это остаётся в семье за месяц.',
      },
    ]
  })

  // ─── Structure ──────────────────────────────────────────────────────
  let topCats = $derived(data?.top_categories ?? [])
  // Real spend of the whole period — the backend sums it server-side, so the
  // donut centre and shares are honest even beyond the top-5 categories.
  let totalSpent = $derived(data?.expense_total ?? 0)
  let segments = $derived(
    topCats.map((t: any, i: number) => ({
      label: t.name,
      value: t.amount,
      color: t.name === 'Прочее' ? '#5b6478' : PALETTE[i % PALETTE.length],
    })),
  )

  // Regular vs variable per the outlook (present every past month, stable amount).
  // Fallback without history: a category with a limit in the plan counts as regular.
  let kindByCategory = $derived.by(() => {
    const out: Record<number, string> = {}
    for (const c of outlook?.categories ?? []) out[c.category_id] = c.kind
    if (!hasOutlook && plan?.limits) {
      for (const l of plan.limits) if (l.limit_amount > 0) out[l.category_id] = 'regular'
    }
    return out
  })
  let split = $derived(recurringSplit(monthTxs, kindByCategory))
  let splitTotal = $derived(split.recurring + split.variable || 1)

  let insights = $derived.by(() => {
    if (!pace) return []
    const cats = topCats.map((t: any) => {
      const pf = (data?.plan_vs_fact ?? []).find((c: any) => c.category_name === t.name)
      return { name: t.name, spent: t.amount, limit: pf?.plan ?? 0, avg3: pf?.avg3 ?? 0 }
    })
    return buildInsights({ categories: cats, txs: monthTxs, outlook, planLimit })
  })

  let pvf = $derived(
    (data?.plan_vs_fact ?? [])
      .filter((c: any) => c.fact > 0 || c.plan > 0)
      .sort((a: any, b: any) => Math.abs(b.diff) - Math.abs(a.diff)),
  )
  let maxDiff = $derived(Math.max(1, ...pvf.map((c: any) => Math.abs(c.diff))))
</script>

{#if !data || !pace}
  <Loader />
{:else}
  <div class="page">
    <div class="tabs">
      {#each ['month', 'quarter', 'year'] as p}
        <button
          class="tab" class:active={periodType === p}
          aria-pressed={periodType === p}
          onclick={() => (periodType = p as typeof periodType)}
        >{PERIOD_LABELS[p]}</button>
      {/each}
    </div>

    <!-- Headline numbers -->
    <section class="grid-tiles">
      {#each statTiles as s}
        <div class="card tile">
          <div class="k">{s.label}</div>
          <div class="tile-main">
            <div class="num v" style="color: {s.color}">{s.value}</div>
            {#if s.spark}<Sparkline values={s.spark} color={s.color} />{/if}
          </div>
          <div class="tile-delta">
            <span style="color: {s.deltaColor}">{s.delta}</span>
            {#if s.note}<span class="dim">{s.note}</span>{/if}
          </div>
          {#if $showHelp}<div class="hint">{s.hint}</div>{/if}
        </div>
      {/each}
    </section>

    <div class="cols stretch">
      {#if hasTrend}
        <section class="card col-wide">
          <h2 class="card-title">Денежный поток за 12 месяцев</h2>
          {#if $showHelp}
            <p class="explain">
              Столбики — сколько пришло и сколько ушло за месяц. Золотая линия — разница между ними,
              то есть что реально осталось. Линия ниже нуля — месяц прожит в минус.
            </p>
          {/if}
          <CashFlowChart
            labels={trendLabels}
            income={trends.map((t: any) => t.income)}
            expense={trends.map((t: any) => t.expense)}
          />
        </section>
      {/if}

      {#if periodType === 'month'}
      <section class="card col">
        <h2 class="card-title">Прогноз до конца месяца</h2>
        {#if $showHelp}
          <p class="explain">
            Сплошная линия — потрачено нарастающим итогом. Серая — как шёл прошлый месяц.
            Пунктир — итог по вашим обычным месяцам: что по каждой категории обычно ещё
            уходит в оставшиеся дни. Темп «в день» здесь не используется.
          </p>
        {/if}
        <ForecastChart
          cumulative={cumDaily}
          prev={outlook?.prev_cumulative ?? []}
          {planLimit}
          {forecastTotal}
          daysInMonth={pace.daysInMonth}
        />
        <div class="axis">
          <span>1 {monthName($period.month).toLowerCase()}</span>
          <span>сегодня, {pace.day}-е</span>
          <span>{pace.daysInMonth}-е</span>
        </div>
        {#if forecastTotal !== null && outlook}
          {@const over = forecastTotal - planLimit}
          <div class="callout {over > 0 ? 'red' : 'green'}">
            По обычным месяцам итог ≈ <span class="num">{money(forecastTotal)} ₽</span>:
            {#if over > 0}
              на {money(over)} ₽ больше плана. Ещё обычно уходит ≈ {money(outlook.expected_remaining)} ₽.
            {:else}
              в рамках плана, запас {money(-over)} ₽.
            {/if}
          </div>
          {#if vsPrev !== null && outlook.prev_same_day}
            <p class="dim tiny" style="margin: 8px 0 0">
              К {outlook.day}-му: {money(outlook.spent)} ₽ против {money(outlook.prev_same_day)} ₽ в прошлом месяце
              ({vsPrev > 0 ? '+' : ''}{vsPrev}%).
            </p>
          {/if}
          {#if outlook.oneoffs.length}
            <p class="dim tiny" style="margin: 6px 0 0">
              Крупные разовые: {outlook.oneoffs.map((o) => `${o.category_name ?? 'без категории'} ${money(o.amount)}`).join(', ')} — всего {money(outlook.oneoffs_total)} ₽.
            </p>
          {/if}
        {:else if pace.daysLeft === 0}
          <div class="callout {summary.total_spent > planLimit ? 'red' : 'green'}">
            Месяц закрыт: {money(summary.total_spent)} ₽ при плане {money(planLimit)} ₽.
          </div>
        {:else}
          <div class="callout blue">
            Прогноз появится после первого полного месяца учёта — считать его по «темпу в день» нечестно:
            аренда и разовые покупки ломают такую оценку.
          </div>
        {/if}
        {#if !hasPlanLimits}
          <p class="dim tiny" style="margin: 8px 0 0">
            Лимиты в Плане не заданы — ориентиром служит 80% дохода месяца.
          </p>
        {/if}
      </section>
      {/if}
    </div>

    <div class="cols stretch">
      <section class="card col-wide">
        <h2 class="card-title">Структура расходов</h2>
        <div class="structure">
          <Donut {segments} total={totalSpent} caption="₽ за период" />
          <div class="legend">
            {#each segments as s}
              <div class="legend-row">
                <i style="background: {s.color}"></i>
                <span class="name">{s.label}</span>
                <span class="num dim">{totalSpent > 0 ? Math.round((s.value / totalSpent) * 100) : 0}%</span>
                <span class="num amt">{money(s.value)} ₽</span>
              </div>
            {/each}
          </div>
        </div>
        {#if $showHelp}
          <p class="explain">Доля каждой категории в расходах периода. Сумма в центре — общий расход.</p>
        {/if}
      </section>

      <section class="col stack">
        {#if periodType === 'month'}
        <div class="card">
          <h2 class="card-title">Обязательное и необязательное</h2>
          {#if $showHelp}
            <p class="explain">
              Регулярные — то, что придёт в следующем месяце в любом случае. Переменные — то,
              чем реально можно управлять.
            </p>
          {/if}
          <div class="split-bar">
            <i style="width: {(split.recurring / splitTotal) * 100}%; background: var(--blue)"></i>
            <i style="width: {(split.variable / splitTotal) * 100}%; background: var(--yellow)"></i>
          </div>
          <div class="stack" style="gap: 10px">
            <div class="row">
              <span class="small"><i class="dot" style="background: var(--blue)"></i>Регулярные</span>
              <span class="num small">{money(split.recurring)} ₽ · {Math.round((split.recurring / splitTotal) * 100)}%</span>
            </div>
            <div class="row">
              <span class="small"><i class="dot" style="background: var(--yellow)"></i>Переменные</span>
              <span class="num small">{money(split.variable)} ₽ · {Math.round((split.variable / splitTotal) * 100)}%</span>
            </div>
          </div>
        </div>

        {/if}

        {#if data.pair?.users?.length > 1}
          <div class="card">
            <h2 class="card-title">Кто сколько тратит</h2>
            <div class="stack" style="margin-top: 12px">
              {#each data.pair.users as u, i}
                <div>
                  <div class="row">
                    <span class="small">
                      {u.user_name}
                      {#if u.top_category}
                        <span class="dim tiny"> · больше всего на «{u.top_category}» — {money(u.top_amount)} ₽</span>
                      {/if}
                    </span>
                    <span class="num small">всего {money(u.total)} ₽</span>
                  </div>
                  <div class="pbar" style="margin-top: 7px">
                    <div class="pbar-fill" style="width: {(u.total / Math.max(1, ...data.pair.users.map((x: any) => x.total))) * 100}%; background: {PALETTE[i % PALETTE.length]}"></div>
                  </div>
                </div>
              {/each}
            </div>
          </div>
        {/if}
      </section>
    </div>

    {#if periodType === 'month'}
    <div class="cols stretch">
      <section class="card col">
        <h2 class="card-title">Траты по дням</h2>
        {#if $showHelp}
          <p class="explain">Чем ярче квадрат — тем больше потрачено в этот день. Так видно недельный ритм трат.</p>
        {/if}
        <DaysHeatmap
          values={daily}
          firstWeekday={firstWeekday($period.year, $period.month)}
          today={pace.day}
          monthLabel={monthName($period.month).toLowerCase()}
        />
      </section>

      <section class="card col">
        <h2 class="card-title">На что обратить внимание</h2>
        {#if $showHelp}
          <p class="explain">Автоматические наблюдения: то, что сильно выбивается из вашей обычной картины.</p>
        {/if}
        {#if insights.length === 0}
          <p class="muted small" style="margin-top: 12px">Аномалий не нашлось — месяц идёт ровно.</p>
        {:else}
          <div class="stack" style="margin-top: 12px; gap: 10px">
            {#each insights as ins}
              <div class="insight {ins.tone}">
                <i class="ti {ins.icon}"></i>
                <div>
                  <div class="ins-title">{ins.title}</div>
                  <div class="ins-text">{ins.text}</div>
                </div>
              </div>
            {/each}
          </div>
        {/if}
      </section>
    </div>
    {/if}

    <section class="card">
      <div class="row">
        <h2 class="card-title">План против факта</h2>
        <span class="dim small">
          {periodType === 'month' ? `${monthName($period.month)} ${$period.year}` : `${PERIOD_LABELS[periodType]} · ${$period.year}`}
        </span>
      </div>
      {#if $showHelp}
        <p class="explain">Полоса вправо от центра — потратили больше плана, влево — меньше.</p>
      {/if}
      <div class="table-scroll">
        <div class="table">
          <div class="thead">
            <span>Категория</span><span class="r">План</span><span class="r">Факт</span><span class="r">Разница</span><span>Отклонение</span>
          </div>
          {#each pvf as c}
            {@const over = c.diff > 0}
            {@const w = (Math.abs(c.diff) / maxDiff) * 50}
            <div class="trow">
              <span class="tname">{c.category_name}</span>
              <span class="num r dim">{money(c.plan)}</span>
              <span class="num r">{money(c.fact)}</span>
              <span class="num r bold" style="color: var(--{over ? 'red' : 'green'})">{over ? '+' : '−'}{money(Math.abs(c.diff))}</span>
              <span class="dev">
                <span class="dev-track">
                  <span class="dev-mid"></span>
                  <span class="dev-fill" style="left: {over ? 50 : 50 - w}%; width: {Math.max(w, 1)}%; background: var(--{over ? 'red' : 'green'})"></span>
                </span>
              </span>
            </div>
          {/each}
        </div>
      </div>
    </section>
  </div>
{/if}

<style>
  .tabs { display: flex; gap: var(--space-2); flex-wrap: wrap; }
  .tab {
    height: 36px; padding: 0 18px; border-radius: 999px;
    border: 1px solid var(--line); background: var(--bg-surface);
    color: var(--text-secondary); font-size: 13px; font-weight: 600;
  }
  .tab.active { background: rgba(106, 155, 255, 0.16); color: var(--blue); border-color: var(--blue-border); }

  .card.tile { padding: var(--space-4); border-radius: var(--radius-md); }
  .k { font-size: 12px; color: var(--text-secondary); }
  .tile-main { display: flex; align-items: flex-end; justify-content: space-between; gap: var(--space-3); margin-top: 8px; }
  .v { font-size: 24px; font-weight: 600; white-space: nowrap; }
  .tile-delta { display: flex; align-items: center; gap: 6px; margin-top: 8px; font-size: 11.5px; font-weight: 600; }
  .tile-delta .dim { font-weight: 400; }
  .hint {
    font-size: 11.5px; line-height: 1.45; color: var(--text-muted);
    margin-top: 8px; padding-top: 8px; border-top: 1px solid rgba(255, 255, 255, 0.05);
  }

  .axis { display: flex; justify-content: space-between; font-size: 10.5px; color: var(--text-muted); margin-top: 4px; }
  .callout { margin-top: var(--space-3); padding: 12px 13px; border-radius: var(--radius-md); font-size: 12.5px; line-height: 1.5; }
  .callout.red { background: var(--red-bg); color: var(--red); }
  .callout.green { background: var(--green-bg); color: var(--green); }
  .callout.blue { background: rgba(106, 155, 255, 0.1); color: var(--blue); }

  .structure { display: flex; flex-wrap: wrap; gap: var(--space-5); align-items: center; margin-top: var(--space-3); }
  .legend { flex: 1 1 200px; min-width: 190px; display: flex; flex-direction: column; gap: 9px; }
  .legend-row { display: flex; align-items: center; gap: 9px; font-size: 12.5px; }
  .legend-row i { width: 9px; height: 9px; flex: 0 0 9px; border-radius: 3px; }
  .legend-row .name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .legend-row .amt { font-size: 12px; }

  .split-bar { display: flex; height: 14px; border-radius: 999px; overflow: hidden; background: var(--bg-elevated); margin: var(--space-4) 0 var(--space-3); }
  .split-bar i { display: block; height: 100%; }
  .dot { width: 9px; height: 9px; border-radius: 3px; display: inline-block; margin-right: 8px; }

  .insight { display: flex; gap: 11px; padding: 12px 13px; border-radius: var(--radius-md); }
  .insight i { font-size: 18px; flex: 0 0 18px; }
  .insight.red { background: rgba(240, 104, 106, 0.1); color: var(--red); }
  .insight.yellow { background: rgba(242, 184, 75, 0.1); color: var(--yellow); }
  .insight.blue { background: rgba(106, 155, 255, 0.1); color: var(--blue); }
  .insight.green { background: rgba(62, 207, 142, 0.1); color: var(--green); }
  .ins-title { font-size: 13px; font-weight: 600; }
  .ins-text { font-size: 12px; line-height: 1.5; color: var(--text-secondary); margin-top: 3px; }

  .table-scroll { overflow-x: auto; margin-top: var(--space-3); }
  .table { min-width: 560px; }
  .thead, .trow { display: grid; grid-template-columns: 1.4fr 92px 92px 100px 1fr; gap: 12px; align-items: center; }
  .thead { padding: 8px 0; font-size: 11px; font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase; color: var(--text-muted); }
  .trow { padding: 10px 0; border-top: 1px solid var(--line); font-size: 13px; }
  .tname { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .r { text-align: right; }
  .bold { font-weight: 600; }
  .dev-track { position: relative; display: block; height: 6px; border-radius: 999px; background: var(--bg-elevated); }
  .dev-mid { position: absolute; top: 0; bottom: 0; left: 50%; width: 1px; background: rgba(255, 255, 255, 0.15); }
  .dev-fill { position: absolute; top: 0; bottom: 0; border-radius: 999px; }

  .small { font-size: var(--text-sm); }
  .tiny { font-size: var(--text-xs); }
</style>
