<script lang="ts">
  import { api } from '../api'
  import { authenticated, me } from '../stores'

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
      // Без этого $me остаётся «неавторизованным» до перезагрузки страницы, и
      // админские разделы («Телеграм-бот и AI», «Админка») не показываются.
      me.set(await api.authMe())
      authenticated.set(true)
    } catch (err) {
      error = 'Неверный логин или пароль'
    } finally {
      busy = false
    }
  }

  const FEATURES = [
    { icon: 'ti-percentage', title: 'Правило 50/30/20', text: 'Половина дохода — на нужды, треть — на желания, пятая часть — в накопления. Приложение следит за балансом само.' },
    { icon: 'ti-wallet', title: 'Учёт за секунды', text: 'Траты и доходы — в пару касаний с телефона или сообщением Telegram-боту: «кофе 360, магазин 1560».' },
    { icon: 'ti-chart-donut-4', title: 'План и аналитика', text: 'Лимиты по категориям, план против факта, прогноз до конца месяца и норма сбережений.' },
    { icon: 'ti-pig-money', title: 'Копилки и долги', text: 'Конверты на цели, контроль кредитов и рассрочек, калькулятор вклада с капитализацией.' },
  ]
</script>

<div class="landing">
  <div class="inner">
    <section class="pitch">
      <div class="brand">
        <div class="logo"><i class="ti ti-coins"></i></div>
        <span class="name">fin-home</span>
      </div>
      <h1>Семейный бюджет,<br />который ведёт себя сам</h1>
      <p class="tagline">
        Личный сервис учёта денег для семьи: быстрый ввод трат, понятный план месяца
        и честный ответ на вопрос «сколько ещё можно потратить».
      </p>

      <ul class="features">
        {#each FEATURES as f}
          <li>
            <i class="ti {f.icon}"></i>
            <div>
              <strong>{f.title}</strong>
              <p>{f.text}</p>
            </div>
          </li>
        {/each}
      </ul>
    </section>

    <section class="auth card">
      <h2>Вход</h2>
      <p class="dim">Сервис работает по приглашениям. Если у вас есть инвайт-ссылка — откройте её, чтобы создать аккаунт.</p>
      <form onsubmit={submit}>
        <input class="input" type="text" placeholder="Логин" autocomplete="username" bind:value={username} />
        <input class="input" type="password" placeholder="Пароль" autocomplete="current-password" bind:value={password} />
        {#if error}<p class="error">{error}</p>{/if}
        <button class="btn btn-primary" type="submit" disabled={busy || !username || !password}>
          {busy ? 'Входим…' : 'Войти'}
        </button>
      </form>
      <p class="foot dim">Данные хранятся на собственном сервере. Бюджеты пространств изолированы друг от друга.</p>
    </section>
  </div>
</div>

<style>
  .landing {
    min-height: 100dvh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: var(--space-6) var(--space-4);
    background:
      radial-gradient(1200px 500px at 80% -10%, rgba(106, 155, 255, 0.13), transparent 60%),
      radial-gradient(900px 420px at 0% 110%, rgba(62, 207, 142, 0.08), transparent 60%),
      var(--bg-base);
  }
  .inner {
    display: grid;
    grid-template-columns: 1fr;
    gap: var(--space-8);
    max-width: 1020px;
    width: 100%;
  }
  @media (min-width: 900px) {
    .inner { grid-template-columns: 1.25fr 1fr; align-items: center; gap: var(--space-10); }
  }

  .brand { display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--space-6); }
  .logo {
    width: 48px; height: 48px; border-radius: var(--radius-md);
    background: var(--blue-bg); color: var(--blue);
    display: flex; align-items: center; justify-content: center;
  }
  .logo i { font-size: 28px; }
  .name { font-weight: 700; font-size: var(--text-lg); letter-spacing: 0.2px; }

  h1 {
    font-size: clamp(28px, 4.5vw, 42px);
    line-height: 1.15;
    margin: 0 0 var(--space-4);
    letter-spacing: -0.5px;
  }
  .tagline { color: var(--text-secondary); font-size: var(--text-lg); margin: 0 0 var(--space-6); max-width: 46ch; }

  .features { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-4); }
  @media (min-width: 640px) { .features { grid-template-columns: 1fr 1fr; } }
  .features li { display: flex; gap: var(--space-3); align-items: flex-start; }
  .features i {
    font-size: 20px; color: var(--blue);
    background: var(--blue-bg); border-radius: var(--radius-sm);
    padding: 8px; flex-shrink: 0;
  }
  .features strong { display: block; margin-bottom: 2px; font-size: var(--text-base); }
  .features p { margin: 0; color: var(--text-secondary); font-size: var(--text-sm); }

  .auth { padding: var(--space-6); max-width: 420px; width: 100%; justify-self: center; }
  .auth h2 { margin: 0 0 var(--space-2); }
  .auth .dim { font-size: var(--text-sm); margin: 0 0 var(--space-4); }
  form { display: flex; flex-direction: column; gap: var(--space-3); }
  .error { color: var(--red); font-size: var(--text-sm); margin: 0; }
  .foot { font-size: var(--text-xs); margin: var(--space-6) 0 0; }
</style>
