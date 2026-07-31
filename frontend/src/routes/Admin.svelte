<script lang="ts">
  import { api, type AdminInvite, type AdminOverview } from '../lib/api'
  import { showToast } from '../lib/stores'
  import Loader from '../lib/components/Loader.svelte'

  let overview = $state<AdminOverview | null>(null)
  let invites = $state<AdminInvite[]>([])
  let error = $state('')

  // New-invite form
  let label = $state('')
  let workspaceId = $state<number | ''>('')
  let ttlDays = $state<number | ''>('')
  let creating = $state(false)

  async function load() {
    try {
      const [o, i] = await Promise.all([api.adminOverview(), api.adminInvites()])
      overview = o
      invites = i
    } catch (e) {
      error = (e as Error).message
    }
  }
  load()

  function inviteUrl(token: string) {
    return `${location.origin}/#/register/${token}`
  }

  async function copyInvite(inv: AdminInvite) {
    await navigator.clipboard.writeText(inviteUrl(inv.token))
    showToast('Ссылка скопирована')
  }

  async function createInvite() {
    creating = true
    try {
      const inv = await api.adminCreateInvite({
        label: label || undefined,
        workspace_id: workspaceId === '' ? null : workspaceId,
        ttl_days: ttlDays === '' ? null : ttlDays,
      })
      invites = [inv, ...invites]
      label = ''
      workspaceId = ''
      ttlDays = ''
      await copyInvite(inv)
    } catch (e) {
      showToast((e as Error).message)
    } finally {
      creating = false
    }
  }

  async function revoke(inv: AdminInvite) {
    if (!confirm('Отозвать инвайт?')) return
    await api.adminRevokeInvite(inv.id)
    invites = invites.filter((i) => i.id !== inv.id)
  }

  async function toggleAccount(accId: number, isActive: boolean) {
    try {
      await api.adminPatchAccount(accId, { is_active: !isActive })
      await load()
    } catch (e) {
      showToast((e as Error).message)
    }
  }

  async function resetPassword(accId: number, username: string) {
    const pwd = prompt(`Новый пароль для «${username}» (мин. 8 символов):`)
    if (!pwd) return
    try {
      await api.adminPatchAccount(accId, { password: pwd })
      showToast('Пароль обновлён')
    } catch (e) {
      showToast((e as Error).message)
    }
  }

  const fmtDate = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString('ru-RU') : '—')
  const inviteStatus = (inv: AdminInvite) => {
    if (inv.used_at) return { text: 'использован', cls: 'dim' }
    if (inv.expires_at && new Date(inv.expires_at) < new Date()) return { text: 'истёк', cls: 'red' }
    return { text: 'активен', cls: 'green' }
  }
</script>

{#if error}
  <div class="page"><div class="card"><p class="red">{error}</p></div></div>
{:else if !overview}
  <Loader />
{:else}
  <div class="page">
    <!-- Invites -->
    <section class="card">
      <h2 class="card-title">Инвайты</h2>
      <p class="dim small">
        Ссылка-приглашение одноразовая. Без привязки к пространству друг получит свой отдельный
        бюджет; с привязкой — войдёт в выбранное пространство.
      </p>
      <div class="invite-form">
        <input class="input" placeholder="Заметка (кому)" bind:value={label} />
        <select class="input" bind:value={workspaceId}>
          <option value="">Новое пространство</option>
          {#each overview.workspaces as w}
            <option value={w.id}>В «{w.name}»</option>
          {/each}
        </select>
        <select class="input" bind:value={ttlDays}>
          <option value="">Бессрочный</option>
          <option value={7}>7 дней</option>
          <option value={30}>30 дней</option>
        </select>
        <button class="btn btn-primary" onclick={createInvite} disabled={creating}>
          Создать и скопировать
        </button>
      </div>

      {#if invites.length}
        <div class="stack">
          {#each invites as inv}
            {@const st = inviteStatus(inv)}
            <div class="invite-row">
              <div class="invite-info">
                <span>{inv.label || 'Без заметки'}</span>
                <span class="small dim">
                  {inv.workspace_name ? `в «${inv.workspace_name}»` : 'новое пространство'}
                  · {fmtDate(inv.created_at)} · <span class={st.cls}>{st.text}</span>
                </span>
              </div>
              {#if !inv.used_at}
                <div class="row-actions">
                  <button class="btn btn-ghost" onclick={() => copyInvite(inv)} title="Скопировать ссылку">
                    <i class="ti ti-copy"></i>
                  </button>
                  <button class="btn btn-ghost red" onclick={() => revoke(inv)} title="Отозвать">
                    <i class="ti ti-trash"></i>
                  </button>
                </div>
              {/if}
            </div>
          {/each}
        </div>
      {/if}
    </section>

    <!-- Workspaces & accounts -->
    <section class="card">
      <h2 class="card-title">Пространства и аккаунты</h2>
      <div class="stack">
        {#each overview.workspaces as w}
          <div class="ws">
            <div class="row">
              <strong>{w.name}</strong>
              <span class="small dim">{w.tx_count} операций · с {fmtDate(w.created_at)}</span>
            </div>
            {#each w.accounts as a}
              <div class="acc-row">
                <span class:dim={!a.is_active}>
                  {a.username}
                  {#if a.is_admin}<span class="chip blue">admin</span>{/if}
                  {#if !a.is_active}<span class="chip">выключен</span>{/if}
                </span>
                <div class="row-actions">
                  <button class="btn btn-ghost" onclick={() => resetPassword(a.id, a.username)}
                          title="Сменить пароль">
                    <i class="ti ti-key"></i>
                  </button>
                  <button class="btn btn-ghost" onclick={() => toggleAccount(a.id, a.is_active)}
                          title={a.is_active ? 'Деактивировать' : 'Включить'}>
                    <i class="ti {a.is_active ? 'ti-user-off' : 'ti-user-check'}"></i>
                  </button>
                </div>
              </div>
            {/each}
          </div>
        {/each}
      </div>
    </section>
  </div>
{/if}

<style>
  .invite-form {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-2);
    margin: var(--space-3) 0 var(--space-4);
  }
  .invite-form .btn { grid-column: 1 / -1; }
  @media (min-width: 900px) {
    .invite-form { grid-template-columns: 2fr 1.5fr 1fr auto; }
    .invite-form .btn { grid-column: auto; }
  }

  .stack { display: flex; flex-direction: column; gap: var(--space-2); }

  .invite-row, .acc-row {
    display: flex; align-items: center; justify-content: space-between; gap: var(--space-3);
    padding: var(--space-2) 0;
    border-bottom: 1px solid var(--border);
  }
  .invite-row:last-child, .acc-row:last-child { border-bottom: none; }
  .invite-info { display: flex; flex-direction: column; gap: 2px; }
  .row-actions { display: flex; gap: var(--space-1); }

  .ws { padding: var(--space-2) 0; }
  .ws .row { margin-bottom: var(--space-1); }
  .acc-row { padding-left: var(--space-3); }

  .small { font-size: var(--text-sm); }
  .red { color: var(--red); }
  .green { color: var(--green); }
</style>
