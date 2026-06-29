<script lang="ts">
  import { api } from '../lib/api'
  import { period, dataVersion } from '../lib/stores'
  import { money, monthName } from '../lib/format'
  import Chart from '../lib/components/Chart.svelte'

  let data = $state<any>(null)

  $effect(() => {
    const { year, month } = $period
    void $dataVersion
    api.analytics(year, month).then((d) => (data = d))
  })

  let trendLabels = $derived(
    data?.monthly_trends?.map((t: any) => monthName(t.month).slice(0, 3)) ?? [],
  )
  let trendDatasets = $derived(
    data
      ? [
          { label: 'Доход', data: data.monthly_trends.map((t: any) => t.income), borderColor: '#4CAF72', backgroundColor: 'rgba(76,175,114,0.1)', tension: 0.3, fill: true },
          { label: 'Расход', data: data.monthly_trends.map((t: any) => t.expense), borderColor: '#D95F5F', backgroundColor: 'rgba(217,95,95,0.1)', tension: 0.3, fill: true },
          { label: 'Сбережения', data: data.monthly_trends.map((t: any) => t.savings), borderColor: '#C9943A', backgroundColor: 'transparent', tension: 0.3 },
        ]
      : [],
  )
  let hasTrend = $derived(
    data?.monthly_trends?.some((t: any) => t.income || t.expense) ?? false,
  )

  let maxTop = $derived(
    data?.top_categories?.length ? Math.max(...data.top_categories.map((t: any) => t.amount)) : 1,
  )
</script>

<div class="page-header"><h1>Аналитика</h1></div>

{#if !data}
  <div class="spinner-wrap">Загрузка…</div>
{:else}
  <div class="page">
    {#if hasTrend}
      <div>
        <div class="section-label">Динамика за 12 месяцев</div>
        <div class="card">
          <Chart type="line" labels={trendLabels} datasets={trendDatasets} height={220} />
        </div>
      </div>
    {/if}

    <div>
      <div class="section-label">Топ категорий</div>
      <div class="card stack">
        {#if data.top_categories.length === 0}
          <p class="muted">Нет расходов за месяц.</p>
        {/if}
        {#each data.top_categories as t}
          <div>
            <div class="row"><span>{t.name}</span><span class="num">{money(t.amount)} ₽</span></div>
            <div class="pbar"><div class="pbar-fill blue" style="width:{(t.amount / maxTop) * 100}%; background: var(--blue)"></div></div>
          </div>
        {/each}
      </div>
    </div>

    <div>
      <div class="section-label">План vs Факт</div>
      <div class="card stack">
        {#each data.plan_vs_fact.filter((c: any) => c.fact > 0 || c.plan > 0) as c}
          <div class="row">
            <span>{c.category_name}</span>
            <span class="num muted">{money(c.fact)} / {money(c.plan)}
              <span class={c.diff > 0 ? 'over' : 'under'}>
                {c.diff > 0 ? '+' : ''}{money(c.diff)}
              </span>
            </span>
          </div>
        {/each}
      </div>
    </div>

    {#if data.cascade?.length}
      <div>
        <div class="section-label">Сценарии</div>
        <div class="card stack">
          {#each data.cascade as s}
            <p class="muted">{s.suggestion}</p>
          {/each}
        </div>
      </div>
    {/if}

    {#if data.pair?.users?.length > 1}
      <div>
        <div class="section-label">Кто сколько тратит</div>
        <div class="card stack">
          {#each data.pair.users as u}
            <div class="row">
              <span>{u.user_name}</span>
              <span class="num">{money(u.total)} ₽{u.top_category ? ` · ${u.top_category}` : ''}</span>
            </div>
          {/each}
        </div>
      </div>
    {/if}
  </div>
{/if}

<style>
  .over { color: var(--red); }
  .under { color: var(--green); }
  .pbar { margin-top: 4px; }
</style>
