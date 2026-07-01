<script lang="ts">
  import { api } from '../api'
  import { authenticated } from '../stores'

  let username = $state('')
  let password = $state('')
  let busy = $state(false)
  let error = $state('')

  async function submit(e: Event) {
    e.preventDefault()
    if (!username || !password) return
    busy = true
    error = ''
    try {
      await api.login(username, password)
      authenticated.set(true)
    } catch (err) {
      error = 'Неверный логин или пароль'
    } finally {
      busy = false
    }
  }
</script>

<div class="login">
  <div class="logo"><i class="ti ti-coins"></i></div>
  <h1>fin-home</h1>
  <form onsubmit={submit}>
    <input class="input" type="text" placeholder="Логин" autocomplete="username" bind:value={username} />
    <input class="input" type="password" placeholder="Пароль" autocomplete="current-password" bind:value={password} />
    {#if error}<p class="error">{error}</p>{/if}
    <button class="btn btn-primary" type="submit" disabled={busy || !username || !password}>Войти</button>
  </form>
</div>

<style>
  .login {
    max-width: 360px;
    margin: 0 auto;
    min-height: 100dvh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--space-3);
    padding: var(--space-6);
    text-align: center;
  }
  .logo {
    width: 72px; height: 72px; border-radius: var(--radius-lg);
    background: var(--blue-bg); color: var(--blue);
    display: flex; align-items: center; justify-content: center;
  }
  .logo i { font-size: 40px; }
  form { display: flex; flex-direction: column; gap: var(--space-3); width: 100%; margin-top: var(--space-4); }
  .error { color: var(--red); font-size: var(--text-sm); margin: 0; }
</style>
