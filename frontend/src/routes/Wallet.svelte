<script lang="ts">
  // Кошелёк USDC — отдельный раздел, доступный любому участнику: адрес и ключ
  // Etherscan живут в пределах workspace, админ для этого не нужен.
  import { api, type User, type WalletStatus } from '../lib/api'
  import { showToast } from '../lib/stores'
  import { wallet } from '../lib/wallet'
  import { usdc, usdcRound, usdcParts, timeOnly } from '../lib/format'

  let w = $state<WalletStatus | null>(null)
  let users = $state<User[]>([])
  let form = $state({ address: '', etherscan_api_key: '', threshold: '', notify_user_id: 0 })
  let busy = $state(false)
  let tgUsers = $derived(users.filter((u) => u.telegram_id))
  let amount = $derived(usdcParts(w?.balance))

  async function load() {
    const [status, us] = await Promise.all([api.wallet(), api.users()])
    w = status
    wallet.set(status)
    users = us
    form.threshold = status.threshold > 0 ? String(status.threshold) : ''
    form.notify_user_id = status.notify_user_id ?? 0
  }
  load()

  async function save() {
    busy = true
    try {
      const body: any = { threshold: form.threshold, notify_user_id: form.notify_user_id }
      if (form.address.trim()) body.address = form.address.trim()
      if (form.etherscan_api_key) body.etherscan_api_key = form.etherscan_api_key
      w = await api.saveWallet(body)
      wallet.set(w)
      form.address = ''
      form.etherscan_api_key = ''
      showToast('Кошелёк сохранён')
    } catch (e) {
      showToast((e as Error).message)
    } finally {
      busy = false
    }
  }
  async function check() {
    busy = true
    try {
      w = await api.refreshWallet()
      wallet.set(w)
      showToast(w.error ? `Etherscan: ${w.error}` : `Баланс: ${usdc(w.balance)} USDC`)
    } catch (e) {
      showToast((e as Error).message)
    } finally {
      busy = false
    }
  }
  async function disable() {
    busy = true
    try {
      w = await api.saveWallet({ address: '' })
      wallet.set(w)
      showToast('Кошелёк отключён')
    } finally {
      busy = false
    }
  }
</script>

<div class="page">
  {#if w}
    <div class="cols">
      <section class="card col-wide">
        <h2 class="card-title">Настройки кошелька</h2>
        <p class="explain">
          Баланс USDC проверяется раз в 5 минут через Etherscan. Как только он поднимется
          выше порога, бот один раз за календарный месяц напишет, что зарплата пришла.
          На бюджет это не влияет: доход всё равно записывается операцией.
        </p>

        <div class="fields">
          <label class="field">
            <span>Адрес кошелька (Ethereum mainnet)</span>
            <input class="input" bind:value={form.address} spellcheck="false"
                   autocapitalize="off" autocomplete="off"
                   placeholder={w.address_set ? w.address : '0x…'} />
          </label>
          <label class="field">
            <span>Etherscan API-ключ</span>
            <input class="input" type="password" bind:value={form.etherscan_api_key}
                   placeholder={w.api_key_set ? 'задан ••••' : 'не задан'} />
          </label>
          <div class="pair">
            <label class="field">
              <span>Порог, USDC</span>
              <input class="input" bind:value={form.threshold} inputmode="decimal" placeholder="например 1000" />
            </label>
            <label class="field">
              <span>Кому писать</span>
              <select class="input" bind:value={form.notify_user_id}>
                <option value={0}>Всем с Telegram</option>
                {#each tgUsers as u}<option value={u.id}>{u.name}</option>{/each}
              </select>
            </label>
          </div>
        </div>

        {#if tgUsers.length === 0}
          <p class="explain warn">
            Ни у кого не привязан Telegram ID — уведомление писать некому.
            Привяжите его в «Ещё» → участники.
          </p>
        {/if}

        <div class="actions">
          <button class="btn btn-primary btn-sm" onclick={save} disabled={busy}>Сохранить</button>
          <button class="btn btn-secondary btn-sm" onclick={check} disabled={busy || !w.configured}>
            {busy ? 'Проверяю…' : 'Проверить сейчас'}
          </button>
          {#if w.address_set}
            <button class="btn btn-ghost btn-sm" onclick={disable} disabled={busy}>Отключить</button>
          {/if}
        </div>
      </section>

      <section class="card col">
        <h2 class="card-title">Сейчас на кошельке</h2>
        {#if w.error}
          <div class="num big red">—</div>
          <p class="explain warn">Etherscan: {w.error}</p>
        {:else if w.balance !== null}
          <div class="num big">
            {amount[0]}<span class="frac">{amount[1]}</span> <span class="ticker">USDC</span>
          </div>
        {:else}
          <div class="num big muted">—</div>
        {/if}

        <dl class="meta">
          <div><dt>Адрес</dt><dd class="num">{w.address || 'не задан'}</dd></div>
          <div><dt>Обновлено</dt><dd>{timeOnly(w.checked_at) || 'ещё не проверяли'}</dd></div>
          <div><dt>Порог</dt><dd>{w.threshold > 0 ? `${usdcRound(w.threshold)} USDC` : 'не задан'}</dd></div>
          <div><dt>Уведомление</dt><dd>{w.alert_month ? `отправлено за ${w.alert_month}` : 'ещё не отправляли'}</dd></div>
        </dl>

        {#if w.configured}
          <p class="explain">На Главной тап по большому числу перевернёт его на этот баланс.</p>
        {:else}
          <p class="explain">Заполните адрес и ключ — тогда на Главной появится переворот баланса.</p>
        {/if}
      </section>
    </div>
  {/if}
</div>

<style>
  .fields { display: flex; flex-direction: column; gap: var(--space-3); margin-top: var(--space-4); }
  .pair { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-3); }
  /* Порог и получатель встают в столбик, когда двум полям тесно. */
  @media (max-width: 560px) { .pair { grid-template-columns: 1fr; } }

  .actions { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-top: var(--space-4); }
  .actions .btn { flex: 1 1 auto; }

  .warn { color: var(--yellow); }

  .big { font-size: clamp(28px, 4vw, 38px); font-weight: 600; margin: var(--space-3) 0 var(--space-2); }
  .big.red { color: var(--red); }
  .ticker { font-size: 0.45em; font-weight: 600; color: var(--text-secondary); }
  .frac { font-size: 0.6em; color: var(--text-secondary); }

  .meta { display: flex; flex-direction: column; gap: 9px; margin: 0; }
  .meta > div { display: flex; justify-content: space-between; align-items: baseline; gap: var(--space-3); }
  dt { font-size: var(--text-xs); color: var(--text-secondary); }
  dd { margin: 0; font-size: var(--text-sm); text-align: right; overflow-wrap: anywhere; }
</style>
