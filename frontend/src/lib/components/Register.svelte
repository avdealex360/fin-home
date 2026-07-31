<script lang="ts">
  import { api } from '../api'
  import { authenticated, me, navigate } from '../stores'
  import Loader from './Loader.svelte'

  interface Props {
    token: string
  }
  let { token }: Props = $props()

  let info = $state<{ valid: boolean; mode: 'join' | 'create'; workspace_name: string | null } | null>(null)
  let invalid = $state(false)

  let username = $state('')
  let password = $state('')
  let password2 = $state('')
  let workspaceName = $state('')
  let busy = $state(false)
  let error = $state('')

  api.inviteInfo(token)
    .then((i) => (info = i))
    .catch(() => (invalid = true))

  let canSubmit = $derived(
    username.trim().length >= 3 && password.length >= 8 && password === password2,
  )

  async function submit(e: Event) {
    e.preventDefault()
    if (!canSubmit || !info) return
    busy = true
    error = ''
    try {
      await api.register({
        token,
        username: username.trim(),
        password,
        workspace_name: info.mode === 'create' ? workspaceName.trim() || undefined : undefined,
      })
      const s = await api.authMe()
      me.set(s)
      authenticated.set(true)
      navigate('dashboard')
    } catch (err) {
      error = (err as Error).message || 'Не удалось зарегистрироваться'
    } finally {
      busy = false
    }
  }
</script>

<div class="register">
  <div class="card box">
    <div class="brand">
      <div class="logo"><i class="ti ti-coins"></i></div>
      <span class="name">fin-home</span>
    </div>

    {#if invalid}
      <h1>Инвайт не действует</h1>
      <p class="dim">Ссылка не найдена, уже использована или истекла. Попросите новую у того, кто вас пригласил.</p>
      <a class="btn btn-secondary" href="#/">На главную</a>
    {:else if !info}
      <Loader />
    {:else}
      <h1>Регистрация</h1>
      {#if info.mode === 'join'}
        <p class="dim">Вас пригласили в пространство «{info.workspace_name}» — бюджет будет общим с его участниками.</p>
      {:else}
        <p class="dim">Вы получите собственное пространство с отдельным бюджетом — его не видит никто, кроме вас.</p>
      {/if}

      <form onsubmit={submit}>
        <input class="input" type="text" placeholder="Логин (мин. 3 символа)"
               autocomplete="username" bind:value={username} />
        <input class="input" type="password" placeholder="Пароль (мин. 8 символов)"
               autocomplete="new-password" bind:value={password} />
        <input class="input" type="password" placeholder="Пароль ещё раз"
               autocomplete="new-password" bind:value={password2} />
        {#if password2 && password !== password2}
          <p class="error">Пароли не совпадают</p>
        {/if}
        {#if info.mode === 'create'}
          <input class="input" type="text" placeholder="Название пространства (например «Наша семья»)"
                 bind:value={workspaceName} />
        {/if}
        {#if error}<p class="error">{error}</p>{/if}
        <button class="btn btn-primary" type="submit" disabled={busy || !canSubmit}>
          {busy ? 'Создаём…' : 'Создать аккаунт'}
        </button>
      </form>
    {/if}
  </div>
</div>

<style>
  .register {
    min-height: 100dvh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: var(--space-6) var(--space-4);
  }
  .box { max-width: 420px; width: 100%; padding: var(--space-6); }
  .brand { display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--space-5); }
  .logo {
    width: 40px; height: 40px; border-radius: var(--radius-sm);
    background: var(--blue-bg); color: var(--blue);
    display: flex; align-items: center; justify-content: center;
  }
  .logo i { font-size: 24px; }
  .name { font-weight: 700; }
  h1 { margin: 0 0 var(--space-2); font-size: var(--text-2xl); }
  .dim { font-size: var(--text-sm); margin: 0 0 var(--space-4); }
  form { display: flex; flex-direction: column; gap: var(--space-3); }
  .error { color: var(--red); font-size: var(--text-sm); margin: 0; }
</style>
