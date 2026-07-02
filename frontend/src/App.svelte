<script lang="ts">
  import { api, type Transaction } from './lib/api'
  import { authenticated, route, showToast, invalidate } from './lib/stores'
  import BottomNav from './lib/components/BottomNav.svelte'
  import Toast from './lib/components/Toast.svelte'
  import BottomSheet from './lib/components/BottomSheet.svelte'
  import TxForm from './lib/components/TxForm.svelte'
  import AllocationSheet from './lib/components/AllocationSheet.svelte'
  import Onboarding from './lib/components/Onboarding.svelte'
  import Login from './lib/components/Login.svelte'
  import Loader from './lib/components/Loader.svelte'

  import Dashboard from './routes/Dashboard.svelte'
  import Plan from './routes/Plan.svelte'
  import Deposit from './routes/Deposit.svelte'
  import Analytics from './routes/Analytics.svelte'
  import More from './routes/More.svelte'
  import Faq from './routes/Faq.svelte'
  import Categories from './routes/Categories.svelte'
  import Transactions from './routes/Transactions.svelte'
  import Integrations from './routes/Integrations.svelte'

  let onboarded = $state<boolean | null>(null)
  let bootError = $state<string | null>(null)

  function checkAuth() {
    bootError = null
    api.authMe()
      .then((s) => authenticated.set(s.authenticated))
      .catch((e) => (bootError = (e as Error).message || 'Не удалось загрузить приложение'))
  }
  function checkOnboarding() {
    bootError = null
    api.onboardingStatus()
      .then((s) => (onboarded = s.onboarded))
      .catch((e) => (bootError = (e as Error).message || 'Не удалось загрузить приложение'))
  }
  function retryBoot() {
    if ($authenticated) checkOnboarding()
    else checkAuth()
  }
  checkAuth()

  $effect(() => {
    if ($authenticated) checkOnboarding()
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

{#if bootError}
  <div class="boot-error">
    <Loader label={bootError} />
    <button class="btn btn-primary" onclick={retryBoot}>Повторить</button>
  </div>
{:else if $authenticated === null}
  <Loader />
{:else if !$authenticated}
  <Login />
{:else if onboarded === null}
  <Loader />
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
    {:else if $route === 'faq'}
      <Faq />
    {:else if $route === 'categories'}
      <Categories />
    {:else if $route === 'transactions'}
      <Transactions />
    {:else if $route === 'integrations'}
      <Integrations />
    {:else}
      <Dashboard onAllocate={(id) => { allocTxId = id; sheet = 'allocate' }} />
    {/if}
  </div>

  <BottomNav onadd={openAdd} />

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

<style>
  .boot-error {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-4);
  }
</style>
