<script lang="ts">
  import { api, type Integrations } from '../lib/api'
  import { showToast } from '../lib/stores'

  let s = $state<Integrations | null>(null)
  let form = $state({
    tg_bot_token: '', yandex_api_key: '', yandex_folder_id: '', gigachat_auth_key: '',
    ai_primary_provider: 'yandex' as 'yandex' | 'gigachat', tg_bot_enabled: false,
  })
  let testing = $state(false)
  let testResult = $state<{ telegram: boolean; yandex: boolean; gigachat: boolean } | null>(null)

  async function load() {
    s = await api.integrations()
    form.ai_primary_provider = s.ai_primary_provider
    form.tg_bot_enabled = s.tg_bot_enabled
  }
  load()

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
    <p class="hint">
      Ключ Yandex используется и для распознавания голосовых сообщений боту
      (SpeechKit, до 30 секунд). Сервисному аккаунту в Yandex Cloud нужна
      дополнительная роль <code>ai.speechkit-stt.user</code>.
    </p>
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

  <p class="hint">
    Кошелёк USDC настраивается отдельно и доступен всем участникам:
    <a href="#/wallet">«Кошелёк USDC»</a>.
  </p>
  {/if}
</div>

<style>
  .wrap { display: flex; flex-direction: column; gap: 12px; padding-bottom: 40px; }
  .card { display: flex; flex-direction: column; gap: 10px; }
  label { display: flex; flex-direction: column; gap: 4px; font-size: 14px; }
  label.row { flex-direction: row; align-items: center; gap: 8px; }
  .row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  .hint { font-size: 12.5px; line-height: 1.45; color: var(--text-muted); margin: 0; }
</style>
