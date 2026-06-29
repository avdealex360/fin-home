<script lang="ts">
  import { api, type Transaction } from './lib/api'
  import { route, showToast, invalidate } from './lib/stores'
  import BottomNav from './lib/components/BottomNav.svelte'
  import Fab from './lib/components/Fab.svelte'
  import Toast from './lib/components/Toast.svelte'
  import BottomSheet from './lib/components/BottomSheet.svelte'
  import TxForm from './lib/components/TxForm.svelte'
  import AllocationSheet from './lib/components/AllocationSheet.svelte'
  import Onboarding from './lib/components/Onboarding.svelte'

  import Dashboard from './routes/Dashboard.svelte'
  import Plan from './routes/Plan.svelte'
  import Deposit from './routes/Deposit.svelte'
  import Analytics from './routes/Analytics.svelte'
  import More from './routes/More.svelte'

  let onboarded = $state<boolean | null>(null)

  $effect(() => {
    api.onboardingStatus().then((s) => (onboarded = s.onboarded))
  })

  // Add-operation sheet state machine: closed -> form -> (income) allocate
  let sheet = $state<'closed' | 'form' | 'allocate'>('closed')
  let allocTxId = $state<number | null>(null)

  function openAdd() {
    allocTxId = null
    sheet = 'form'
  }
  function onSubmitted(tx: Transaction) {
    invalidate()
    if (tx.type === 'income') {
      allocTxId = tx.id
      sheet = 'allocate'
    } else {
      sheet = 'closed'
      showToast('Операция записана', async () => {
        await api.deleteTransaction(tx.id)
        invalidate()
      })
    }
  }
  function onAllocated() {
    sheet = 'closed'
    invalidate()
    showToast('Доход распределён')
  }
</script>

{#if onboarded === null}
  <div class="spinner-wrap">Загрузка…</div>
{:else if !onboarded}
  <Onboarding ondone={() => (onboarded = true)} />
{:else}
  <div class="app-shell">
    {#if $route === 'dashboard'}
      <Dashboard onAllocate={(id) => { allocTxId = id; sheet = 'allocate' }} />
    {:else if $route === 'plan'}
      <Plan />
    {:else if $route === 'deposit'}
      <Deposit />
    {:else if $route === 'analytics'}
      <Analytics />
    {:else if $route === 'more'}
      <More />
    {:else}
      <Dashboard onAllocate={(id) => { allocTxId = id; sheet = 'allocate' }} />
    {/if}
  </div>

  <Fab onclick={openAdd} />
  <BottomNav />

  <BottomSheet
    open={sheet === 'form'}
    title="Новая операция"
    onclose={() => (sheet = 'closed')}
  >
    {#snippet children()}
      <TxForm onsubmitted={onSubmitted} />
    {/snippet}
  </BottomSheet>

  <BottomSheet
    open={sheet === 'allocate'}
    title="Распределение дохода"
    onclose={() => (sheet = 'closed')}
  >
    {#snippet children()}
      {#if allocTxId}
        <AllocationSheet txId={allocTxId} ondone={onAllocated} />
      {/if}
    {/snippet}
  </BottomSheet>

  <Toast />
{/if}
