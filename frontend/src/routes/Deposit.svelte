<script lang="ts">
  import { api } from '../lib/api'
  import { dataVersion, showToast } from '../lib/stores'
  import { money, formatDate } from '../lib/format'
  import Chart from '../lib/components/Chart.svelte'

  let dep = $state<any>(null)
  let monthly = $state(15000)
  let targetDate = $state(`${new Date().getFullYear() + 2}-12-31`)
  let calc = $state<any>(null)

  $effect(() => {
    void $dataVersion
    api.deposit().then((d) => (dep = d))
  })

  async function runCalc() {
    calc = await api.depositCalc(monthly, targetDate)
  }
  async function saveBalance() {
    await api.updateDeposit({ balance: dep.balance, rate: dep.rate })
    showToast('Вклад обновлён')
  }
</script>

<div class="page-header"><h1>Вклад</h1></div>

{#if !dep}
  <div class="spinner-wrap">Загрузка…</div>
{:else}
  <div class="page">
    <div class="card stack">
      <div class="field">
        <label for="bal">Текущий баланс</label>
        <input id="bal" class="input num" inputmode="numeric" bind:value={dep.balance} />
      </div>
      <div class="field">
        <label for="rate">Ставка, % годовых</label>
        <input id="rate" class="input num" inputmode="decimal" bind:value={dep.rate} />
      </div>
      <button class="btn btn-secondary" onclick={saveBalance}>Сохранить</button>
    </div>

    <div class="card stack">
      <div class="section-label">Калькулятор с капитализацией</div>
      <div class="field">
        <label for="m">Ежемесячный взнос</label>
        <input id="m" class="input num" inputmode="numeric" bind:value={monthly} />
      </div>
      <div class="field">
        <label for="td">Цель к дате</label>
        <input id="td" class="input" type="date" bind:value={targetDate} />
      </div>
      <button class="btn btn-primary" onclick={runCalc}><i class="ti ti-calculator"></i> Рассчитать</button>
      {#if calc}
        <div class="result num">Итог: {money(calc.final_balance)} ₽</div>
        {#if calc.rows.length > 1}
          <Chart
            type="line"
            labels={calc.rows.map((r: any) => formatDate(r.date))}
            datasets={[{
              label: 'Баланс',
              data: calc.rows.map((r: any) => r.balance_after),
              borderColor: '#C9943A',
              backgroundColor: 'rgba(201,148,58,0.12)',
              tension: 0.3,
              fill: true,
              pointRadius: 0,
            }]}
            height={200}
          />
        {/if}
        <div class="rows">
          {#each calc.rows.slice(0, 12) as r}
            <div class="row small">
              <span class="muted">{formatDate(r.date)}</span>
              <span class="num">{money(r.balance_after)} ₽</span>
            </div>
          {/each}
        </div>
      {/if}
    </div>
  </div>
{/if}

<style>
  .result { font-size: var(--text-xl); color: var(--gold); }
  .rows { display: flex; flex-direction: column; gap: 6px; }
  .small { font-size: var(--text-sm); }
</style>
