<script lang="ts">
  import { api, type Integrations, type User, type WalletStatus } from '../lib/api'
  import { showToast } from '../lib/stores'
  import { wallet } from '../lib/wallet'
  import { usdc, timeOnly } from '../lib/format'

  let s = $state<Integrations | null>(null)
  let form = $state({
    tg_bot_token: '', yandex_api_key: '', yandex_folder_id: '', gigachat_auth_key: '',
    ai_primary_provider: 'yandex' as 'yandex' | 'gigachat', tg_bot_enabled: false,
  })
  let testing = $state(false)
  let testResult = $state<{ telegram: boolean; yandex: boolean; gigachat: boolean } | null>(null)

  // Кошелёк USDC: адрес приходит только маской, поэтому поле пустое, а маска — в placeholder.
  let w = $state<WalletStatus | null>(null)
  let users = $state<User[]>([])
  let wForm = $state({ address: '', etherscan_api_key: '', threshold: '', notify_user_id: 0 })
  let wBusy = $state(false)
  let tgUsers = $derived(users.filter((u) => u.telegram_id))

  async function load() {
    s = await api.integrations()
    form.ai_primary_provider = s.ai_primary_provider
    form.tg_bot_enabled = s.tg_bot_enabled
  }
  async function loadWalletCard() {
    const [status, us] = await Promise.all([api.wallet(), api.users()])
    w = status
    wallet.set(status)
    users = us
    wForm.threshold = status.threshold > 0 ? String(status.threshold) : ''
    wForm.notify_user_id = status.notify_user_id ?? 0
  }
  load()
  loadWalletCard()

  async function save() {
    const body: any = { ai_primary_provider: form.ai_primary_provider, tg_bot_enabled: form.tg_bot_enabled }
    for (const k of ['tg_bot_token', 'yandex_api_key', 'yandex_folder_id', 'gigachat_auth_key'] as const) {
      if (form[k]) body[k] = form[k]
    }
    await api.saveIntegrations(body)
    form.tg_bot_token = form.yandex_api_key = form.yandex_folder_id = form.gigachat_auth_key = ''
    await load()
    showToast('Сохранено')
  }
  async function test() {
    testing = true
    try { testResult = await api.testIntegrations() } finally { testing = false }
  }
  async function webhook() {
    const r = await api.setWebhook()
    showToast(r.ok ? 'Webhook установлен' : `Ошибка: ${r.error ?? 'не удалось'}`)
    await load()
  }

  async function saveWallet() {
    wBusy = true
    try {
      const body: any = { threshold: wForm.threshold, notify_user_id: wForm.notify_user_id }
      if (wForm.address.trim()) body.address = wForm.address.trim()
      if (wForm.etherscan_api_key) body.etherscan_api_key = wForm.etherscan_api_key
      w = await api.saveWallet(body)
      wallet.set(w)
      wForm.address = ''
      wForm.etherscan_api_key = ''
      showToast('Кошелёк сохранён')
    } catch (e) {
      showToast((e as Error).message)
    } finally {
      wBusy = false
    }
  }
  async function checkWallet() {
    wBusy = true
    try {
      w = await api.refreshWallet()
      wallet.set(w)
      showToast(w.error ? `Etherscan: ${w.error}` : `Баланс: ${usdc(w.balance)} USDC`)
    } catch (e) {
      showToast((e as Error).message)
    } finally {
      wBusy = false
    }
  }
  async function disableWallet() {
    wBusy = true
    try {
      w = await api.saveWallet({ address: '' })
      wallet.set(w)
      showToast('Кошелёк отключён')
    } finally {
      wBusy = false
    }
  }

  function ph(isSet: boolean, mask = '') {
    return isSet ? (mask || 'задан ••••') : 'не задан'
  }
</script>

<div class="wrap">
  <a class="btn btn-ghost" href="#/more"><i class="ti ti-arrow-left"></i> Назад</a>
  <h2>Интеграции</h2>

  {#if s}
  <section class="card">
    <h3>Telegram-бот</h3>
    <label>Токен бота
      <input type="password" bind:value={form.tg_bot_token} placeholder={ph(s.tg_bot_token, s.tg_bot_token_mask)} />
    </label>
    <label class="row">
      <input type="checkbox" bind:checked={form.tg_bot_enabled} /> Бот включён
    </label>
    <button class="btn btn-ghost" onclick={webhook}>
      {s.webhook_set ? 'Переустановить webhook' : 'Установить webhook'}
    </button>
  </section>

  <section class="card">
    <h3>AI-провайдеры</h3>
    <label>YandexGPT — API-ключ
      <input type="password" bind:value={form.yandex_api_key} placeholder={ph(s.yandex_api_key)} />
    </label>
    <label>Yandex folder id
      <input type="password" bind:value={form.yandex_folder_id} placeholder={ph(s.yandex_folder_id)} />
    </label>
    <label>GigaChat — Authorization key
      <input type="password" bind:value={form.gigachat_auth_key} placeholder={ph(s.gigachat_auth_key)} />
    </label>
    <label>Основной провайдер
      <select bind:value={form.ai_primary_provider}>
        <option value="yandex">YandexGPT</option>
        <option value="gigachat">GigaChat</option>
      </select>
    </label>
  </section>

  <div class="row">
    <button class="btn btn-primary" onclick={save}>Сохранить</button>
    <button class="btn btn-ghost" onclick={test} disabled={testing}>
      {testing ? 'Проверяю…' : 'Проверить'}
    </button>
  </div>

  {#if testResult}
    <div class="card">
      <div>Telegram: {testResult.telegram ? '✅' : '❌'}</div>
      <div>YandexGPT: {testResult.yandex ? '✅' : '❌'}</div>
      <div>GigaChat: {testResult.gigachat ? '✅' : '❌'}</div>
    </div>
  {/if}
  {/if}

  {#if w}
  <section class="card">
    <h3>Кошелёк USDC (ERC-20)</h3>
    <p class="hint">
      Баланс проверяется раз в 5 минут через Etherscan. Как только он поднимется выше порога,
      бот один раз за календарный месяц напишет, что зарплата пришла. На бюджет это не влияет:
      доход всё равно записывается операцией. Ключ: etherscan.io → Profile → API Keys.
    </p>
    <label>Адрес кошелька (Ethereum mainnet)
      <input bind:value={wForm.address} spellcheck="false" autocapitalize="off"
             placeholder={w.address_set ? w.address : '0x…'} />
    </label>
    <label>Etherscan API-ключ
      <input type="password" bind:value={wForm.etherscan_api_key} placeholder={ph(w.api_key_set)} />
    </label>
    <div class="pair">
      <label>Порог, USDC
        <input bind:value={wForm.threshold} inputmode="decimal" placeholder="например 1000" />
      </label>
      <label>Кому писать
        <select bind:value={wForm.notify_user_id}>
          <option value={0}>Всем, у кого привязан Telegram</option>
          {#each tgUsers as u}<option value={u.id}>{u.name}</option>{/each}
        </select>
      </label>
    </div>
    {#if tgUsers.length === 0}
      <p class="hint warn">
        Ни у кого не привязан Telegram ID — писать будет некому. Привяжите в «Ещё» → участники.
      </p>
    {/if}

    <div class="row">
      <button class="btn btn-primary" onclick={saveWallet} disabled={wBusy}>Сохранить кошелёк</button>
      <button class="btn btn-ghost" onclick={checkWallet} disabled={wBusy || !w.configured}>
        {wBusy ? 'Проверяю…' : 'Проверить сейчас'}
      </button>
      {#if w.address_set}
        <button class="btn btn-ghost" onclick={disableWallet} disabled={wBusy}>Отключить</button>
      {/if}
    </div>

    <div class="wstat">
      {#if w.error}
        <span class="bad">Etherscan: {w.error}</span>
      {:else if w.balance !== null}
        Баланс: <b>{usdc(w.balance)} USDC</b>{w.checked_at ? ` · обновлено ${timeOnly(w.checked_at)}` : ''}
      {:else if w.configured}
        Баланс ещё не запрашивался — нажмите «Проверить сейчас».
      {:else}
        Заполните адрес и ключ, тогда на Главной появится переворот баланса.
      {/if}
      {#if w.alert_month}
        <span class="muted"> · уведомление за {w.alert_month} уже отправлено</span>
      {/if}
    </div>
  </section>
  {/if}
</div>

<style>
  .wrap { display: flex; flex-direction: column; gap: 12px; padding-bottom: 40px; }
  .card { display: flex; flex-direction: column; gap: 10px; }
  label { display: flex; flex-direction: column; gap: 4px; font-size: 14px; }
  label.row { flex-direction: row; align-items: center; gap: 8px; }
  .row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  .pair { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  @media (max-width: 520px) { .pair { grid-template-columns: 1fr; } }
  .hint { font-size: 12.5px; line-height: 1.45; color: var(--text-muted); margin: 0; }
  .hint.warn { color: var(--yellow); }
  .wstat { font-size: 13px; color: var(--text-secondary); }
  .bad { color: var(--red); }
</style>
