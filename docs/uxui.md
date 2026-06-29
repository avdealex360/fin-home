# UI/UX Design Spec — Семейный бюджет
**Версия:** 1.0 · **Дата:** июнь 2026  
**Стек:** FastAPI + Jinja2 + HTMX · **Целевое устройство:** мобильный телефон (primary), десктоп (secondary)
 
> **Как использовать этот документ.**  
> Передай его Cursor целиком как контекст перед любой задачей по вёрстке.  
> Каждый раздел — обязательное требование, не рекомендация.  
> Если Cursor предлагает отступить от спеки — отклоняй и ссылайся на конкретный пункт.
 
---
 
## 0. Философия дизайна
 
Приложение открывают в магазине, в метро, поздно вечером — одной рукой, при плохом свете, когда надо быстро записать трату или проверить остаток. Дизайн должен отвечать на вопрос **«как у нас дела?»** за 2 секунды и позволять **записать трату за 5 секунд**.
 
Три принципа, которые не нарушаются:
1. **Данные говорят сами.** Цвет прогресс-бара — это информация, не декорация. Размер числа — это его важность.
2. **Большой палец решает всё.** Всё главное — в нижней трети экрана. Ничего важного в верхних углах.
3. **Одна вещь на экране главная.** Остаток на дашборде. Сумма в форме добавления. Не конкурировать за внимание.
---
 
## 1. Дизайн-токены — единственный источник истины
 
> **Правило:** никаких хардкоженных цветов, размеров, отступов в шаблонах.  
> Всё через CSS-переменные из этого раздела. Исключений нет.
 
### 1.1 Файл `app/static/style.css` — полный листинг токенов
 
```css
:root {
  /* ─── Фоны ─────────────────────────────────────────── */
  --bg-base:        #0F1117;   /* основной фон страницы   */
  --bg-surface:     #181C26;   /* карточки, панели        */
  --bg-elevated:    #222736;   /* bottom sheet, модалки   */
  --bg-overlay:     rgba(0, 0, 0, 0.6); /* оверлей        */
 
  /* ─── Границы ──────────────────────────────────────── */
  --border:         #2A2F42;   /* разделители, рамки      */
  --border-strong:  #3D4460;   /* акцентные разделители   */
 
  /* ─── Текст ────────────────────────────────────────── */
  --text-primary:   #ECEEF4;   /* заголовки, суммы        */
  --text-secondary: #8B92A8;   /* подписи, детали         */
  --text-muted:     #4E566B;   /* метки, placeholder      */
 
  /* ─── Семантические цвета (состояния бюджета) ──────── */
  --green:          #4CAF72;   /* < 70% лимита — норма    */
  --green-bg:       #1A2E22;   /* фон зелёных элементов   */
  --green-border:   #2A4A35;
 
  --yellow:         #E0A040;   /* 70–90% — внимание       */
  --yellow-bg:      #2C2210;
  --yellow-border:  #4A3820;
 
  --red:            #D95F5F;   /* > 90% — превышение      */
  --red-bg:         #2C1A1A;
  --red-border:     #4A2828;
 
  /* ─── Акцентный цвет (кнопки, ссылки, active) ──────── */
  --blue:           #5B8DEF;
  --blue-bg:        #1A2240;
  --blue-border:    #2A3860;
  --blue-hover:     #7AA5F5;
 
  /* ─── Золотой (вклад, накопления) ──────────────────── */
  --gold:           #C9943A;
  --gold-bg:        #2A2010;
  --gold-border:    #3D3018;
 
  /* ─── Spacing — кратен 4px ─────────────────────────── */
  --space-1:  4px;
  --space-2:  8px;
  --space-3:  12px;
  --space-4:  16px;
  --space-5:  20px;
  --space-6:  24px;
  --space-8:  32px;
  --space-10: 40px;
 
  /* ─── Типографика ──────────────────────────────────── */
  --font-mono:  'JetBrains Mono', 'Fira Code', monospace;
  --font-body:  'Inter', system-ui, -apple-system, sans-serif;
 
  --text-xs:   11px;
  --text-sm:   13px;
  --text-base: 15px;
  --text-lg:   17px;
  --text-xl:   22px;
  --text-2xl:  28px;
  --text-3xl:  36px;
 
  /* ─── Радиусы ──────────────────────────────────────── */
  --radius-sm:  8px;
  --radius-md:  12px;
  --radius-lg:  16px;
  --radius-xl:  20px;
  --radius-full: 9999px;
 
  /* ─── Тени ─────────────────────────────────────────── */
  --shadow-card: 0 1px 3px rgba(0,0,0,0.3);
  --shadow-fab:  0 4px 16px rgba(91,141,239,0.35);
  --shadow-sheet: 0 -8px 32px rgba(0,0,0,0.5);
 
  /* ─── Transitions ───────────────────────────────────── */
  --transition-fast: 120ms ease;
  --transition-base: 200ms ease;
  --transition-slow: 350ms ease;
 
  /* ─── Layout ────────────────────────────────────────── */
  --nav-height:     64px;
  --safe-bottom:    env(safe-area-inset-bottom, 0px);
  --page-padding:   var(--space-5);   /* 20px боковые поля */
  --card-padding:   var(--space-4);   /* 16px внутри карточки */
}
 
/* ─── Базовый сброс ──────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
 
html { font-size: 16px; -webkit-text-size-adjust: 100%; }
 
body {
  background: var(--bg-base);
  color: var(--text-primary);
  font-family: var(--font-body);
  font-size: var(--text-base);
  line-height: 1.5;
  min-height: 100dvh;
  overflow-x: hidden;
}
 
/* ─── Числа всегда моноширинные ─────────────────────── */
.num, [data-num], .amount, .balance, .progress-label {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.01em;
}
```
 
---
 
### 1.2 Подключение шрифтов
 
В `<head>` каждого шаблона:
 
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
```
 
---
 
## 2. Layout — структура страницы
 
### 2.1 Мобильный layout (основной)
 
```
┌────────────────────────────┐
│  status bar (нативный)     │  ← не трогать
├────────────────────────────┤
│  .page-header  48px        │  ← заголовок страницы
├────────────────────────────┤
│                            │
│  .page-content             │  ← скроллируемый контент
│  padding: 0 20px           │
│  padding-bottom: 80px      │  ← зазор под навигацию
│                            │
└────────────────────────────┘
│  .bottom-nav   64px        │  ← фиксированная навигация
│  + safe-area-bottom        │
└────────────────────────────┘
```
 
```css
.page-layout {
  display: flex;
  flex-direction: column;
  min-height: 100dvh;
}
 
.page-header {
  position: sticky;
  top: 0;
  z-index: 10;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--page-padding);
  background: var(--bg-base);
  border-bottom: 0.5px solid var(--border);
}
 
.page-content {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-4) var(--page-padding);
  padding-bottom: calc(var(--nav-height) + var(--safe-bottom) + var(--space-6));
  -webkit-overflow-scrolling: touch;
}
 
.bottom-nav {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 20;
  height: calc(var(--nav-height) + var(--safe-bottom));
  padding-bottom: var(--safe-bottom);
  background: var(--bg-surface);
  border-top: 0.5px solid var(--border);
  display: flex;
  align-items: flex-start;
  padding-top: var(--space-2);
}
```
 
### 2.2 Десктоп layout (secondary, max-width: 480px)
 
```css
@media (min-width: 768px) {
  body {
    background: var(--bg-base);
    display: flex;
    justify-content: center;
  }
  .page-layout {
    width: 100%;
    max-width: 480px;
    background: var(--bg-base);
    box-shadow: 0 0 0 0.5px var(--border);
    min-height: 100dvh;
  }
}
```
 
---
 
## 3. Компоненты — полная спека
 
### 3.1 Bottom Navigation
 
```html
<nav class="bottom-nav" aria-label="Основная навигация">
  <a href="/" class="nav-item active" aria-current="page">
    <svg class="nav-icon"><!-- home icon --></svg>
    <span class="nav-label">Главная</span>
  </a>
  <a href="/plan" class="nav-item">
    <svg class="nav-icon"><!-- calendar icon --></svg>
    <span class="nav-label">План</span>
  </a>
  <a href="/deposit" class="nav-item">
    <svg class="nav-icon"><!-- piggy-bank icon --></svg>
    <span class="nav-label">Вклад</span>
  </a>
  <a href="/analytics" class="nav-item">
    <svg class="nav-icon"><!-- chart icon --></svg>
    <span class="nav-label">Аналитика</span>
  </a>
  <a href="/settings" class="nav-item">
    <svg class="nav-icon"><!-- dots icon --></svg>
    <span class="nav-label">Ещё</span>
  </a>
</nav>
```
 
```css
.nav-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  text-decoration: none;
  color: var(--text-muted);
  font-size: var(--text-xs);
  font-weight: 500;
  padding: var(--space-1) 0;
  transition: color var(--transition-fast);
  position: relative;
}
 
.nav-item.active {
  color: var(--blue);
}
 
.nav-item.active::before {
  content: '';
  position: absolute;
  top: -1px;           /* поверх border-top навигации */
  left: 50%;
  transform: translateX(-50%);
  width: 24px;
  height: 2px;
  background: var(--blue);
  border-radius: var(--radius-full);
}
 
.nav-icon {
  width: 24px;
  height: 24px;
  stroke: currentColor;
  fill: none;
  stroke-width: 1.5;
}
 
.nav-label {
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.01em;
}
```
 
---
 
### 3.2 FAB (Floating Action Button)
 
```html
<!-- Вставить прямо перед </body>, вне .page-content -->
<button
  class="fab"
  aria-label="Добавить операцию"
  hx-get="/transaction/form"
  hx-target="#bottom-sheet-content"
  hx-trigger="click"
  onclick="openBottomSheet()"
>
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <line x1="12" y1="5" x2="12" y2="19"/>
    <line x1="5" y1="12" x2="19" y2="12"/>
  </svg>
</button>
```
 
```css
.fab {
  position: fixed;
  bottom: calc(var(--nav-height) + var(--safe-bottom) + var(--space-4));
  right: var(--page-padding);
  z-index: 15;
 
  width: 52px;
  height: 52px;
  border-radius: var(--radius-full);
  border: none;
  cursor: pointer;
 
  background: var(--blue);
  color: #fff;
 
  display: flex;
  align-items: center;
  justify-content: center;
 
  box-shadow: var(--shadow-fab);
  transition: transform var(--transition-fast), box-shadow var(--transition-fast);
}
 
.fab:active {
  transform: scale(0.93);
  box-shadow: 0 2px 8px rgba(91,141,239,0.25);
}
 
/* Скрыть FAB когда bottom sheet открыт */
.fab.hidden { opacity: 0; pointer-events: none; }
```
 
---
 
### 3.3 Bottom Sheet
 
```html
<!-- Вставить прямо перед </body> -->
<div class="sheet-overlay" id="sheet-overlay" onclick="closeBottomSheet()"></div>
 
<div class="bottom-sheet" id="bottom-sheet" role="dialog" aria-modal="true" aria-label="Новая операция">
  <div class="sheet-handle" aria-hidden="true"></div>
  <div class="sheet-content" id="bottom-sheet-content">
    <!-- HTMX загружает форму сюда -->
  </div>
</div>
```
 
```css
.sheet-overlay {
  position: fixed;
  inset: 0;
  z-index: 25;
  background: var(--bg-overlay);
  opacity: 0;
  pointer-events: none;
  transition: opacity var(--transition-base);
}
 
.sheet-overlay.open {
  opacity: 1;
  pointer-events: auto;
}
 
.bottom-sheet {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 30;
 
  background: var(--bg-elevated);
  border-radius: var(--radius-xl) var(--radius-xl) 0 0;
  box-shadow: var(--shadow-sheet);
 
  max-height: 90dvh;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
 
  padding-bottom: calc(var(--safe-bottom) + var(--space-6));
 
  transform: translateY(100%);
  transition: transform var(--transition-slow);
}
 
.bottom-sheet.open {
  transform: translateY(0);
}
 
.sheet-handle {
  width: 36px;
  height: 4px;
  background: var(--border-strong);
  border-radius: var(--radius-full);
  margin: var(--space-3) auto var(--space-2);
}
 
.sheet-content {
  padding: 0 var(--page-padding) var(--space-4);
}
```
 
```javascript
// Добавить в base template или отдельный app.js
function openBottomSheet() {
  document.getElementById('bottom-sheet').classList.add('open');
  document.getElementById('sheet-overlay').classList.add('open');
  document.querySelector('.fab').classList.add('hidden');
  document.body.style.overflow = 'hidden';
}
 
function closeBottomSheet() {
  document.getElementById('bottom-sheet').classList.remove('open');
  document.getElementById('sheet-overlay').classList.remove('open');
  document.querySelector('.fab').classList.remove('hidden');
  document.body.style.overflow = '';
}
 
// Закрыть по Escape
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeBottomSheet();
});
```
 
---
 
### 3.4 Форма добавления операции (внутри Bottom Sheet)
 
```html
<div class="tx-form">
  <!-- Тип операции -->
  <div class="tx-type-tabs" role="tablist" aria-label="Тип операции">
    <button class="tx-type-tab active" role="tab" aria-selected="true" data-type="expense">Расход</button>
    <button class="tx-type-tab" role="tab" aria-selected="false" data-type="income">Доход</button>
    <button class="tx-type-tab" role="tab" aria-selected="false" data-type="transfer">Перевод</button>
  </div>
 
  <!-- Поле суммы -->
  <div class="amount-field">
    <div class="amount-display" id="amount-display">0</div>
    <div class="amount-currency">₽</div>
  </div>
 
  <!-- Быстрые суммы -->
  <div class="quick-amounts" role="group" aria-label="Быстрый ввод суммы">
    <button class="quick-amount-btn" data-amount="100">100</button>
    <button class="quick-amount-btn" data-amount="500">500</button>
    <button class="quick-amount-btn" data-amount="1000">1 000</button>
    <button class="quick-amount-btn" data-amount="5000">5 000</button>
  </div>
 
  <!-- Скрытый input для реального значения -->
  <input
    type="number"
    id="amount-input"
    name="amount"
    inputmode="decimal"
    min="0"
    step="0.01"
    class="visually-hidden"
    required
  >
 
  <!-- Категории — горизонтальный скролл -->
  <div class="section-label">Категория</div>
  <div class="category-scroll" role="listbox" aria-label="Категория">
    <!-- Генерируется Jinja2 -->
    {% for cat in categories %}
    <button
      class="category-chip {% if loop.first %}active{% endif %}"
      role="option"
      aria-selected="{{ 'true' if loop.first else 'false' }}"
      data-id="{{ cat.id }}"
    >
      <span class="category-icon">{{ cat.icon }}</span>
      <span class="category-name">{{ cat.name }}</span>
    </button>
    {% endfor %}
  </div>
 
  <!-- Кто платил -->
  <div class="section-label">Кто</div>
  <div class="who-picker" role="group" aria-label="Кто совершил операцию">
    <button class="who-btn active" data-user="1">{{ user1_name }}</button>
    <button class="who-btn" data-user="2">{{ user2_name }}</button>
  </div>
 
  <!-- Дата (по умолчанию сегодня) -->
  <div class="date-row">
    <span class="section-label" style="margin-bottom:0">Дата</span>
    <input type="date" name="date" value="{{ today }}" class="date-input">
  </div>
 
  <!-- Комментарий — скрытый по умолчанию -->
  <details class="comment-details">
    <summary class="comment-toggle">+ Добавить комментарий</summary>
    <input type="text" name="comment" placeholder="Необязательно" class="comment-input">
  </details>
 
  <!-- Кнопка сохранения -->
  <button
    type="submit"
    class="btn-primary btn-full"
    hx-post="/transactions"
    hx-target="#transactions-list"
    hx-swap="afterbegin"
    hx-on::after-request="closeBottomSheet()"
  >
    Записать
  </button>
</div>
```
 
```css
.tx-form { display: flex; flex-direction: column; gap: var(--space-4); }
 
/* Табы типа операции */
.tx-type-tabs {
  display: flex;
  background: var(--bg-surface);
  border-radius: var(--radius-md);
  padding: 3px;
  gap: 3px;
}
.tx-type-tab {
  flex: 1;
  padding: var(--space-2) 0;
  border: none;
  border-radius: calc(var(--radius-md) - 3px);
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast);
}
.tx-type-tab.active {
  background: var(--bg-elevated);
  color: var(--text-primary);
}
 
/* Поле суммы */
.amount-field {
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: var(--space-2);
  padding: var(--space-4) 0;
}
.amount-display {
  font-family: var(--font-mono);
  font-size: var(--text-3xl);
  font-weight: 500;
  color: var(--text-primary);
  min-width: 4ch;
  text-align: right;
}
.amount-currency {
  font-family: var(--font-mono);
  font-size: var(--text-xl);
  color: var(--text-secondary);
}
 
/* Быстрые суммы */
.quick-amounts {
  display: flex;
  gap: var(--space-2);
}
.quick-amount-btn {
  flex: 1;
  padding: var(--space-2) 0;
  border: 0.5px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-surface);
  color: var(--text-secondary);
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast), border-color var(--transition-fast);
}
.quick-amount-btn:active {
  background: var(--blue-bg);
  color: var(--blue);
  border-color: var(--blue-border);
}
 
/* Горизонтальный скролл категорий */
.category-scroll {
  display: flex;
  gap: var(--space-2);
  overflow-x: auto;
  padding-bottom: var(--space-2);
  scrollbar-width: none;
  -ms-overflow-style: none;
}
.category-scroll::-webkit-scrollbar { display: none; }
 
.category-chip {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: var(--space-2) var(--space-3);
  border: 0.5px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  cursor: pointer;
  transition: background var(--transition-fast), border-color var(--transition-fast);
  min-width: 64px;
}
.category-chip.active {
  background: var(--blue-bg);
  border-color: var(--blue-border);
}
.category-icon { font-size: 20px; }
.category-name {
  font-size: 10px;
  color: var(--text-secondary);
  white-space: nowrap;
  font-weight: 500;
}
.category-chip.active .category-name { color: var(--blue); }
 
/* Who picker */
.who-picker { display: flex; gap: var(--space-2); }
.who-btn {
  flex: 1;
  padding: var(--space-2) 0;
  border: 0.5px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-surface);
  color: var(--text-secondary);
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
}
.who-btn.active {
  background: var(--blue-bg);
  color: var(--blue);
  border-color: var(--blue-border);
}
 
/* Дата */
.date-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.date-input {
  background: var(--bg-surface);
  border: 0.5px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-family: var(--font-body);
  font-size: var(--text-sm);
  padding: var(--space-1) var(--space-3);
  color-scheme: dark;
}
 
/* Комментарий */
.comment-details { border-radius: var(--radius-sm); }
.comment-toggle {
  list-style: none;
  font-size: var(--text-sm);
  color: var(--blue);
  cursor: pointer;
  padding: var(--space-1) 0;
  user-select: none;
}
.comment-input {
  width: 100%;
  margin-top: var(--space-2);
  background: var(--bg-surface);
  border: 0.5px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-family: var(--font-body);
  font-size: var(--text-sm);
  padding: var(--space-2) var(--space-3);
}
.comment-input:focus { outline: none; border-color: var(--blue); }
```
 
---
 
### 3.5 Карточка / Card
 
```html
<div class="card">
  <!-- контент -->
</div>
 
<!-- С заголовком -->
<div class="card">
  <div class="card-header">
    <span class="card-title">Нужды</span>
    <span class="card-badge card-badge--yellow">83%</span>
  </div>
  <!-- тело карточки -->
</div>
```
 
```css
.card {
  background: var(--bg-surface);
  border: 0.5px solid var(--border);
  border-radius: var(--radius-md);
  padding: var(--card-padding);
}
 
.card + .card { margin-top: var(--space-2); }
 
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-3);
}
 
.card-title {
  font-size: var(--text-base);
  font-weight: 500;
  color: var(--text-primary);
}
 
.card-badge {
  font-size: var(--text-xs);
  font-weight: 500;
  padding: 2px 8px;
  border-radius: var(--radius-full);
}
.card-badge--green  { background: var(--green-bg);  color: var(--green);  }
.card-badge--yellow { background: var(--yellow-bg); color: var(--yellow); }
.card-badge--red    { background: var(--red-bg);    color: var(--red);    }
.card-badge--blue   { background: var(--blue-bg);   color: var(--blue);   }
.card-badge--gold   { background: var(--gold-bg);   color: var(--gold);   }
```
 
---
 
### 3.6 Progress Bar с Pace Indicator
 
Это ключевой уникальный элемент дизайна. Реализовать точно.
 
```html
<!--
  data-spent="38200"     — потрачено
  data-limit="55000"     — лимит
  data-day="15"          — текущий день месяца
  data-days-in-month="30" — дней в месяце
-->
<div class="progress-bar-wrap"
     data-spent="38200"
     data-limit="55000"
     data-day="15"
     data-days-in-month="30">
  <div class="progress-track">
    <div class="progress-fill" style="width: 69.5%"></div>  <!-- spent/limit*100 -->
    <div class="pace-line" style="left: 50%"></div>          <!-- day/days*100 -->
  </div>
</div>
```
 
```css
.progress-track {
  position: relative;
  height: 8px;
  background: var(--bg-elevated);
  border: 0.5px solid var(--border);
  border-radius: var(--radius-full);
  overflow: visible;  /* pace-line выходит за края */
}
 
.progress-fill {
  height: 100%;
  border-radius: var(--radius-full);
  transition: width var(--transition-slow), background-color var(--transition-base);
  /* Цвет задаётся через JS или data-атрибут */
}
 
/* Состояния цвета заливки */
.progress-fill.state-ok     { background: var(--green);  }
.progress-fill.state-warn   { background: var(--yellow); }
.progress-fill.state-over   { background: var(--red);    }
 
/* Pace indicator — «где ты должен быть сегодня» */
.pace-line {
  position: absolute;
  top: -3px;
  bottom: -3px;      /* чуть выступает над треком */
  width: 1.5px;
  background: var(--text-muted);
  border-radius: var(--radius-full);
  transform: translateX(-50%);
}
 
/* Если бар правее pace — подсветить pace красным */
.progress-bar-wrap.over-pace .pace-line {
  background: var(--red);
  opacity: 0.7;
}
```
 
```javascript
// Инициализация прогресс-баров
document.querySelectorAll('.progress-bar-wrap').forEach(wrap => {
  const spent = parseFloat(wrap.dataset.spent);
  const limit = parseFloat(wrap.dataset.limit);
  const day = parseInt(wrap.dataset.day);
  const daysInMonth = parseInt(wrap.dataset.daysInMonth);
 
  const pct = Math.min((spent / limit) * 100, 100);
  const pace = (day / daysInMonth) * 100;
 
  const fill = wrap.querySelector('.progress-fill');
  fill.style.width = pct + '%';
 
  // Цвет по состоянию
  if (pct < 70)       fill.classList.add('state-ok');
  else if (pct < 90)  fill.classList.add('state-warn');
  else                fill.classList.add('state-over');
 
  // Pace indicator
  wrap.querySelector('.pace-line').style.left = pace + '%';
 
  // Если тратим быстрее плана
  if (pct > pace) wrap.classList.add('over-pace');
});
```
 
---
 
### 3.7 Section Label
 
```html
<div class="section-label">Бюджет</div>
```
 
```css
.section-label {
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.07em;
  margin: var(--space-5) 0 var(--space-2);
}
 
/* Первый section-label на странице без верхнего отступа */
.page-content > .section-label:first-child { margin-top: var(--space-2); }
```
 
---
 
### 3.8 Кнопки
 
```html
<!-- Основная действие (одна на экран) -->
<button class="btn btn-primary btn-full">Записать</button>
 
<!-- Вторичное действие -->
<button class="btn btn-secondary">Отмена</button>
 
<!-- Деструктивное -->
<button class="btn btn-danger">Удалить</button>
 
<!-- Ghost / outline -->
<button class="btn btn-ghost">Подробнее</button>
```
 
```css
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: 0 var(--space-5);
  height: 48px;
  border-radius: var(--radius-md);
  border: none;
  font-family: var(--font-body);
  font-size: var(--text-base);
  font-weight: 500;
  cursor: pointer;
  transition: opacity var(--transition-fast), transform var(--transition-fast);
  white-space: nowrap;
  -webkit-tap-highlight-color: transparent;
}
 
.btn:active { opacity: 0.8; transform: scale(0.98); }
.btn:disabled { opacity: 0.4; pointer-events: none; }
 
.btn-primary   { background: var(--blue);     color: #fff; }
.btn-secondary { background: var(--bg-surface); color: var(--text-primary); border: 0.5px solid var(--border); }
.btn-danger    { background: var(--red-bg);   color: var(--red); border: 0.5px solid var(--red-border); }
.btn-ghost     { background: transparent;    color: var(--blue); }
 
.btn-full { width: 100%; }
.btn-sm   { height: 36px; font-size: var(--text-sm); padding: 0 var(--space-3); }
```
 
---
 
### 3.9 Toast / Snackbar (для undo после удаления)
 
```html
<div class="toast" id="toast" role="status" aria-live="polite">
  <span class="toast-text">Операция удалена</span>
  <button class="toast-undo" onclick="undoDelete()">Отменить</button>
</div>
```
 
```css
.toast {
  position: fixed;
  bottom: calc(var(--nav-height) + var(--safe-bottom) + var(--space-3));
  left: var(--page-padding);
  right: var(--page-padding);
  z-index: 40;
 
  display: flex;
  align-items: center;
  justify-content: space-between;
 
  background: var(--bg-elevated);
  border: 0.5px solid var(--border-strong);
  border-radius: var(--radius-md);
  padding: var(--space-3) var(--space-4);
 
  font-size: var(--text-sm);
  color: var(--text-primary);
 
  transform: translateY(calc(100% + var(--space-4)));
  transition: transform var(--transition-slow);
  box-shadow: var(--shadow-card);
}
 
.toast.visible {
  transform: translateY(0);
}
 
.toast-undo {
  background: none;
  border: none;
  color: var(--blue);
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
  padding: 0;
}
```
 
---
 
### 3.10 Список операций со swipe-to-delete
 
```html
<ul class="tx-list" id="transactions-list">
  {% for tx in transactions %}
  <li class="tx-item" data-id="{{ tx.id }}">
    <div class="tx-item-inner">
      <div class="tx-icon">{{ tx.category.icon }}</div>
      <div class="tx-info">
        <span class="tx-category">{{ tx.category.name }}</span>
        <span class="tx-meta">{{ tx.date | format_date }} · {{ tx.user_name }}</span>
      </div>
      <div class="tx-amount {% if tx.type == 'income' %}tx-amount--income{% endif %}">
        {% if tx.type == 'expense' %}−{% else %}+{% endif %}
        <span class="num">{{ tx.amount | format_money }}</span> ₽
      </div>
    </div>
    <!-- Swipe action (показывается при свайпе) -->
    <button class="tx-delete-action"
            hx-delete="/transactions/{{ tx.id }}"
            hx-target="closest .tx-item"
            hx-swap="outerHTML swap:0.2s"
            aria-label="Удалить операцию">
      Удалить
    </button>
  </li>
  {% endfor %}
</ul>
```
 
```css
.tx-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
 
.tx-item {
  position: relative;
  overflow: hidden;
  border-radius: var(--radius-md);
}
 
.tx-item-inner {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  background: var(--bg-surface);
  border: 0.5px solid var(--border);
  border-radius: var(--radius-md);
  position: relative;
  z-index: 1;
  transition: transform var(--transition-base);
}
 
/* При свайпе влево смещается .tx-item-inner */
.tx-item.swiped .tx-item-inner {
  transform: translateX(-80px);
}
 
.tx-delete-action {
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  width: 80px;
  background: var(--red-bg);
  border: none;
  border-radius: 0 var(--radius-md) var(--radius-md) 0;
  color: var(--red);
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
}
 
.tx-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-sm);
  background: var(--bg-elevated);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
}
 
.tx-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
 
.tx-category {
  font-size: var(--text-base);
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
 
.tx-meta {
  font-size: var(--text-xs);
  color: var(--text-muted);
}
 
.tx-amount {
  font-family: var(--font-mono);
  font-size: var(--text-base);
  font-weight: 500;
  color: var(--red);
  white-space: nowrap;
  flex-shrink: 0;
}
 
.tx-amount--income { color: var(--green); }
```
 
---
 
### 3.11 Hero-блок дашборда
 
```html
<div class="hero-block">
  <p class="hero-label">Остаток в июне</p>
  <div class="hero-row">
    <span class="hero-amount num">47 320</span>
    <span class="hero-currency">₽</span>
  </div>
  <p class="hero-sub">Доход <span class="num">110 000</span> · Потрачено <span class="num">62 680</span></p>
  <div class="hero-chips">
    <span class="chip chip--green">Сбережения 21% ✓</span>
    <span class="chip chip--neutral">15-й день из 30</span>
  </div>
</div>
```
 
```css
.hero-block {
  padding: var(--space-5) var(--page-padding);
  background: var(--bg-surface);
  border-bottom: 0.5px solid var(--border);
  margin: 0 calc(-1 * var(--page-padding));  /* full-bleed */
}
 
.hero-label {
  font-size: var(--text-sm);
  color: var(--text-muted);
  margin-bottom: var(--space-1);
}
 
.hero-row {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  margin-bottom: var(--space-1);
}
 
.hero-amount {
  font-size: var(--text-3xl);
  font-weight: 500;
  color: var(--text-primary);
  line-height: 1.1;
}
 
.hero-currency {
  font-family: var(--font-mono);
  font-size: var(--text-xl);
  color: var(--text-secondary);
}
 
.hero-sub {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  margin-bottom: var(--space-3);
}
 
.hero-chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
 
/* Chips / Tags */
.chip {
  display: inline-flex;
  align-items: center;
  font-size: var(--text-xs);
  font-weight: 500;
  padding: 3px 10px;
  border-radius: var(--radius-full);
  border: 0.5px solid;
}
.chip--green   { background: var(--green-bg);  color: var(--green);  border-color: var(--green-border); }
.chip--yellow  { background: var(--yellow-bg); color: var(--yellow); border-color: var(--yellow-border); }
.chip--red     { background: var(--red-bg);    color: var(--red);    border-color: var(--red-border); }
.chip--blue    { background: var(--blue-bg);   color: var(--blue);   border-color: var(--blue-border); }
.chip--neutral { background: var(--bg-elevated); color: var(--text-secondary); border-color: var(--border); }
```
 
---
 
### 3.12 Карточка долга
 
```html
<div class="debt-card debt-card--urgent">
  <div class="debt-card-icon">💳</div>
  <div class="debt-card-info">
    <span class="debt-card-name">Кредитка Тинькофф</span>
    <span class="debt-card-detail">29% · льготный период</span>
  </div>
  <div class="debt-card-right">
    <span class="debt-card-amount num">44 000 ₽</span>
    <span class="debt-card-days chip chip--red">⚠ 12 дней</span>
  </div>
</div>
```
 
```css
.debt-card {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  background: var(--bg-surface);
  border: 0.5px solid var(--border);
  border-radius: var(--radius-md);
}
 
/* Левый акцент-бордер по приоритету */
.debt-card--urgent { border-left: 3px solid var(--red); }
.debt-card--ok     { border-left: 3px solid var(--green); }
 
.debt-card-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-sm);
  background: var(--bg-elevated);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
}
 
.debt-card-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
 
.debt-card-name {
  font-size: var(--text-base);
  font-weight: 500;
  color: var(--text-primary);
}
 
.debt-card-detail {
  font-size: var(--text-xs);
  color: var(--text-muted);
}
 
.debt-card-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  flex-shrink: 0;
}
 
.debt-card-amount {
  font-size: var(--text-base);
  font-weight: 500;
  color: var(--text-primary);
}
```
 
---
 
### 3.13 Блок советов
 
```html
<div class="advice-card advice-card--urgent">
  <div class="advice-icon">⚠</div>
  <div class="advice-body">
    <span class="advice-label">Срочно</span>
    <p class="advice-text">Погасите кредитку до 15 июля — осталось 12 дней льготного периода.</p>
  </div>
</div>
```
 
```css
.advice-card {
  display: flex;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  border: 0.5px solid;
}
 
.advice-card--urgent { background: var(--red-bg);    border-color: var(--red-border); }
.advice-card--warn   { background: var(--yellow-bg); border-color: var(--yellow-border); }
.advice-card--info   { background: var(--blue-bg);   border-color: var(--blue-border); }
 
.advice-icon {
  font-size: 18px;
  flex-shrink: 0;
  margin-top: 1px;
}
 
.advice-body { display: flex; flex-direction: column; gap: 2px; }
 
.advice-label {
  font-size: var(--text-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
 
.advice-card--urgent .advice-label { color: var(--red); }
.advice-card--warn   .advice-label { color: var(--yellow); }
.advice-card--info   .advice-label { color: var(--blue); }
 
.advice-text {
  font-size: var(--text-sm);
  color: var(--text-primary);
  line-height: 1.5;
}
```
 
---
 
## 4. Страницы — структура шаблонов
 
### 4.1 Дашборд `/` — порядок блоков сверху вниз
 
```
1. .hero-block           — остаток, доход, потрачено, чипы
2. .section-label        — «БЮДЖЕТ»
3. .card                 — три строки 50/30/20 с progress-bar
4. .section-label        — «ДОЛГИ»
5. .debt-card × N        — по каждому долгу
6. .section-label        — «СОВЕТ»  (только если есть активные)
7. .advice-card × 1–2    — максимум 2 совета одновременно
8. .section-label        — «ПОСЛЕДНИЕ ОПЕРАЦИИ»
9. .tx-list              — последние 10 операций
```
 
### 4.2 Форма добавления операции (Bottom Sheet)
 
```
1. .tx-type-tabs         — Расход / Доход / Перевод
2. .amount-field         — большое поле суммы
3. .quick-amounts        — быстрые кнопки
4. .section-label        — «КАТЕГОРИЯ»
5. .category-scroll      — горизонтальный скролл
6. .section-label        — «КТО»
7. .who-picker           — две кнопки
8. .date-row             — дата
9. .comment-details      — скрытый комментарий
10. .btn-primary.btn-full — «Записать»
```
 
### 4.3 Страница плана `/plan`
 
```
1. .page-header          — «План» + переключатель ← июнь →
2. .section-label        — «ОЖИДАЕМЫЙ ДОХОД»
3. .card                 — поле ввода дохода + кнопка «Пересчитать»
4. .section-label        — «ЛИМИТЫ»
5. .card × N             — редактируемые лимиты категорий
6. .section-label        — «ПЛАНОВЫЕ РАСХОДЫ»
7. .card                 — список + форма добавления
8. .btn-primary.btn-full — «Сохранить план»
```
 
---
 
## 5. Анимации и микровзаимодействия
 
> **Принцип:** анимировать только то, что несёт информацию. Не анимировать для красоты.
 
### 5.1 Что анимировать
 
```css
/* 1. Прогресс-бары — плавное заполнение при загрузке страницы */
.progress-fill {
  width: 0;
  transition: width 600ms cubic-bezier(0.4, 0, 0.2, 1);
}
/* JS устанавливает финальную ширину через 50ms после загрузки */
 
/* 2. Новая операция — появление в списке */
.tx-item.htmx-added {
  animation: slideIn 200ms ease forwards;
}
@keyframes slideIn {
  from { opacity: 0; transform: translateY(-8px); }
  to   { opacity: 1; transform: translateY(0); }
}
 
/* 3. Удалённая операция — исчезновение */
.tx-item.htmx-swapping {
  animation: fadeOut 200ms ease forwards;
}
@keyframes fadeOut {
  to { opacity: 0; transform: translateX(-20px); }
}
 
/* 4. Toast — появление */
/* Управляется через .visible класс (см. 3.9) */
 
/* 5. Уважать prefers-reduced-motion */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```
 
### 5.2 Что НЕ анимировать
 
- Переходы между страницами (HTMX делает это нативно)
- Hover-эффекты на мобильных (нет hover на тачскрине)
- Появление иконок, текста, фонов
- Любые infinite-анимации или looping effects
---
 
## 6. Типографическая иерархия
 
| Роль | Элемент | Шрифт | Размер | Вес | Цвет |
|------|---------|-------|--------|-----|------|
| Главный остаток | `.hero-amount` | Mono | 36px | 500 | `--text-primary` |
| Суммы в карточках | `.amount`, `.num` | Mono | 17px | 500 | `--text-primary` |
| Заголовок карточки | `.card-title` | Inter | 15px | 500 | `--text-primary` |
| Основной текст | `p`, `.body` | Inter | 15px | 400 | `--text-primary` |
| Подписи | `.tx-meta`, `.detail` | Inter | 13px | 400 | `--text-secondary` |
| Section labels | `.section-label` | Inter | 11px | 600 | `--text-muted` |
| Чипы и бейджи | `.chip`, `.badge` | Inter | 11px | 500 | контекстный |
| Подписи навигации | `.nav-label` | Inter | 10px | 500 | контекстный |
 
---
 
## 7. Иконки
 
Использовать **Tabler Icons** (бесплатный, MIT, 5000+ иконок, stroke-based).
 
```html
<!-- Подключить в <head> -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@latest/tabler-icons.min.css">
 
<!-- Использование -->
<i class="ti ti-home"></i>
<i class="ti ti-plus"></i>
<i class="ti ti-chart-bar"></i>
<i class="ti ti-credit-card"></i>
<i class="ti ti-piggy-bank"></i>
<i class="ti ti-settings"></i>
<i class="ti ti-bulb"></i>       <!-- советы -->
<i class="ti ti-alert-triangle"> <!-- предупреждения -->
<i class="ti ti-circle-check">   <!-- успех -->
```
 
Размеры: навигация 24px, в карточках 20px, в тексте 16px.  
**Не использовать** эмодзи как иконки (рендерятся непредсказуемо на разных ОС).
 
---
 
## 8. Категории — иконки и цвета
 
```python
# Привязка категорий к иконкам и цветам
# Использовать как data в Jinja2 seed/settings
 
CATEGORY_ICONS = {
    # Нужды
    "Аренда жилья":          {"icon": "ti-home",           "color": "#5B8DEF"},
    "Продукты и быт":        {"icon": "ti-shopping-cart",  "color": "#4CAF72"},
    "Транспорт":             {"icon": "ti-car",            "color": "#5B8DEF"},
    "Здоровье и лекарства":  {"icon": "ti-heart-rate-monitor", "color": "#D95F5F"},
    "Кот — плановые":        {"icon": "ti-paw",            "color": "#C9943A"},
    "Кот — ветеринар":       {"icon": "ti-stethoscope",    "color": "#D95F5F"},
    "Связь и интернет":      {"icon": "ti-wifi",           "color": "#8B92A8"},
    "Яндекс Сплит":          {"icon": "ti-receipt",        "color": "#E0A040"},
    "Кредитка Тинькофф":     {"icon": "ti-credit-card",    "color": "#D95F5F"},
    # Желания
    "Рестораны и доставка":  {"icon": "ti-fork",           "color": "#E0A040"},
    "Подписки":              {"icon": "ti-brand-netflix",  "color": "#5B8DEF"},
    "Одежда и уход":         {"icon": "ti-hanger",         "color": "#C9943A"},
    "Спорт и хобби":         {"icon": "ti-activity",       "color": "#4CAF72"},
    "Подарки":               {"icon": "ti-gift",           "color": "#D95F5F"},
    "Прочее":                {"icon": "ti-dots",           "color": "#8B92A8"},
    # Сбережения
    "Подушка":               {"icon": "ti-shield",         "color": "#4CAF72"},
    "Вклад на машину":       {"icon": "ti-building-bank",  "color": "#C9943A"},
    "Погашение долгов":      {"icon": "ti-arrow-down-circle", "color": "#5B8DEF"},
    # Доход
    "Зарплата":              {"icon": "ti-briefcase",      "color": "#4CAF72"},
    "Доход партнёра":        {"icon": "ti-briefcase",      "color": "#4CAF72"},
    "Прочий доход":          {"icon": "ti-plus-circle",    "color": "#4CAF72"},
}
```
 
---
 
## 9. Форматирование данных
 
```python
# Jinja2 фильтры — добавить в main.py
 
@app.template_filter('format_money')
def format_money(value):
    """38200 → '38 200'"""
    return f"{int(value):,}".replace(',', '\u00a0')  # неразрывный пробел
 
@app.template_filter('format_date')
def format_date(value):
    """2026-06-15 → '15 июня'"""
    months = ['янв','фев','мар','апр','мая','июн','июл','авг','сен','окт','ноя','дек']
    return f"{value.day} {months[value.month - 1]}"
```
 
В шаблонах:
```html
<!-- Всегда оборачивать числа в .num -->
<span class="num">{{ tx.amount | format_money }}</span> ₽
 
<!-- Суммы в EUR -->
<span class="num">{{ amount_eur }}</span> €
<span class="text-secondary"> × {{ rate }} = </span>
<span class="num">{{ amount_rub | format_money }}</span> ₽
```
 
---
 
## 10. Запрещённые паттерны
 
> Если Cursor предлагает любое из ниже — отклоняй.
 
| Запрещено | Причина | Вместо |
|-----------|---------|--------|
| `bg-gray-100`, `text-blue-500` и любые Tailwind-дефолты | Не из нашей системы | CSS-переменные |
| Хардкоженные цвета: `color: #333`, `background: white` | Сломает тёмную тему | `var(--text-primary)` |
| `border-radius: 4px` или `8px` без переменной | Нарушает систему | `var(--radius-sm)` |
| `font-size: 14px` хардкод | Нарушает типографику | `var(--text-sm)` |
| Верхняя навигация `<nav>` в `<header>` | Thumb zone | `.bottom-nav` |
| `<form>` без `hx-*` атрибутов | Полная перезагрузка | HTMX атрибуты |
| `alert()`, `confirm()` | Ломает UX | Toast + Bottom Sheet |
| Inline styles `style="..."` | Не поддерживается темой | CSS-классы |
| `overflow: hidden` на `<body>` без `bottom-sheet.open` | Блокирует скролл | Только при открытом sheet |
| Внешние CSS-фреймворки (Bootstrap, Bulma) | Конфликт с нашей системой | Наш `style.css` |
 
---
 
## 11. Checklist перед коммитом
 
- [ ] Все цвета через `var(--*)`
- [ ] Все числа обёрнуты в `.num` с `font-family: var(--font-mono)`
- [ ] Суммы отформатированы через `| format_money`
- [ ] FAB присутствует на всех страницах где нужна быстрая запись
- [ ] Нижняя навигация на всех страницах
- [ ] Progress bars инициализированы JS-скриптом из раздела 3.6
- [ ] Нет хардкоженных цветов в новых CSS-правилах
- [ ] `inputmode="decimal"` на всех числовых полях
- [ ] `aria-label` на интерактивных элементах без текста
- [ ] Протестировано на 375px (iPhone SE) и 390px (iPhone 14)
 