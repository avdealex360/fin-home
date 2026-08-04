<script lang="ts">
  import { api, type Transaction } from './lib/api'
  import { authenticated, me, route, showToast, invalidate, period } from './lib/stores'
  import { money, monthName } from './lib/format'
  import BottomNav from './lib/components/BottomNav.svelte'
  import SideNav from './lib/components/SideNav.svelte'
  import AppHeader from './lib/components/AppHeader.svelte'
  import Toast from './lib/components/Toast.svelte'
  import BottomSheet from './lib/components/BottomSheet.svelte'
  import TxForm from './lib/components/TxForm.svelte'
  import Onboarding from './lib/components/Onboarding.svelte'
  import Landing from './lib/components/Landing.svelte'
  import Register from './lib/components/Register.svelte'
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
  import Wallet from './routes/Wallet.svelte'
  import Admin from './routes/Admin.svelte'

  let onboarded = $state<boolean | null>(null)
  let bootError = $state<string | null>(null)
  // Kept in sync for the sidebar summary block.
  let summary = $state<any>(null)
  // Real family members shown as the sidebar subtitle.
  let usersLabel = $state('')

  function checkAuth() {
    bootError = null
    api.authMe()
      .then((s) => {
        me.set(s)
        authenticated.set(s.authenticated)
      })
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

  $effect(() => {
    if (!onboarded) return
    const { year, month } = $period
    api.dashboard(year, month).then((s) => (summary = s)).catch(() => {})
  })

  $effect(() => {
    if (!onboarded) return
    api.users()
      .then((us) => {
        const names = us.filter((u) => u.is_active).map((u) => u.name)
        usersLabel = names.length === 2 ? names.join(' и ') : names.join(', ')
      })
      .catch(() => {})
  })

  const TITLES: Record<string, { title: string; sub: string; period?: boolean }> = {
    dashboard: { title: 'Главная', sub: 'Сколько осталось и куда уходит' },
    transactions: { title: 'Операции', sub: 'История трат и доходов' },
    plan: { title: 'План месяца', sub: 'Лимиты, доходы и обязательные платежи' },
    deposit: { title: 'Калькулятор вклада', sub: 'Справочный расчёт капитализации — на бюджет не влияет', period: false },
    analytics: { title: 'Аналитика', sub: 'Куда уходят деньги и что будет к концу месяца' },
    more: { title: 'Настройки', sub: 'Семья, категории, интеграции' },
    faq: { title: 'Вопросы', sub: 'Как считаются цифры', period: false },
    categories: { title: 'Категории', sub: 'Названия, иконки и группы', period: false },
    integrations: { title: 'Интеграции', sub: 'Telegram-бот и AI', period: false },
    wallet: { title: 'Кошелёк USDC', sub: 'Баланс ERC-20 и уведомление о зарплате', period: false },
    admin: { title: 'Админка', sub: 'Пространства, аккаунты и инвайты', period: false },
  }
  let head = $derived(TITLES[$route] ?? TITLES.dashboard)

  // "#/register/<token>" — invite registration, reachable while logged out.
  let inviteToken = $derived($route.startsWith('register/') ? $route.slice('register/'.length) : null)

  let daysLeft = $derived.by(() => {
    const now = new Date()
    const dim = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate()
    return Math.max(dim - now.getDate(), 0)
  })

  let sheet = $state<'closed' | 'form'>('closed')

  function openAdd() {
    sheet = 'form'
  }
  function onSubmitted(tx: Transaction) {
    invalidate()
    sheet = 'closed'
    showToast('Операция записана', async () => {
      await api.deleteTransaction(tx.id)
      invalidate()
    })
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
  {#if inviteToken}
    <Register token={inviteToken} />
  {:else}
    <Landing />
  {/if}
{:else if onboarded === null}
  <Loader />
{:else if !onboarded}
  <Onboarding ondone={() => (onboarded = true)} />
{:else}
  <div class="app-layout">
    <SideNav
      onadd={openAdd}
      brandSub={usersLabel}
      freeAmount={summary ? money(summary.balance) : ''}
      perDay={summary && daysLeft > 0 ? money(summary.balance / daysLeft) : '0'}
      {daysLeft}
    />

    <div class="app-shell">
      <AppHeader
        title={head.title}
        subtitle={head.sub}
        showPeriod={head.period !== false}
        onadd={openAdd}
      />

      {#if $route === 'plan'}
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
      {:else if $route === 'wallet'}
        <Wallet />
      {:else if $route === 'integrations' && $me?.is_admin}
        <Integrations />
      {:else if $route === 'admin' && $me?.is_admin}
        <Admin />
      {:else}
        <Dashboard />
      {/if}
    </div>
  </div>

  <BottomNav onadd={openAdd} />

  <BottomSheet open={sheet === 'form'} title="Новая операция" onclose={() => (sheet = 'closed')}>
    {#snippet children()}
      <TxForm onsubmitted={onSubmitted} />
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
