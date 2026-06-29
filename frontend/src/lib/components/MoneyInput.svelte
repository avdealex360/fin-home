<script lang="ts">
  interface Props {
    value: number
    quick?: number[]
  }
  let { value = $bindable(0), quick = [100, 500, 1000, 5000] }: Props = $props()

  // Keep a raw string so the user can type freely; sync number out on input.
  let raw = $state(value ? String(value) : '')

  function onInput(e: Event) {
    const el = e.target as HTMLInputElement
    raw = el.value.replace(',', '.').replace(/[^0-9.]/g, '')
    value = parseFloat(raw) || 0
  }
  function add(n: number) {
    value = (value || 0) + n
    raw = String(value)
  }
  function clear() {
    value = 0
    raw = ''
  }
</script>

<div class="money">
  <input
    class="money-field num"
    inputmode="decimal"
    placeholder="0"
    value={raw}
    oninput={onInput}
    aria-label="Сумма"
  />
  <span class="cur">₽</span>
</div>
<div class="quick">
  {#each quick as q}
    <button type="button" class="qbtn num" onclick={() => add(q)}>+{q}</button>
  {/each}
  <button type="button" class="qbtn clear" onclick={clear} aria-label="Очистить">
    <i class="ti ti-backspace"></i>
  </button>
</div>

<style>
  .money {
    display: flex;
    align-items: baseline;
    justify-content: center;
    gap: var(--space-2);
    padding: var(--space-2) 0;
  }
  .money-field {
    background: none;
    border: none;
    color: var(--text-primary);
    font-size: var(--text-3xl);
    font-weight: 500;
    text-align: center;
    width: 70%;
    padding: 0;
  }
  .money-field:focus { outline: none; }
  .cur { font-size: var(--text-xl); color: var(--text-secondary); }
  .quick {
    display: flex;
    gap: var(--space-2);
    justify-content: center;
    flex-wrap: wrap;
  }
  .qbtn {
    background: var(--bg-surface);
    border: none;
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    padding: 10px 14px;
    font-size: var(--text-sm);
  }
  .qbtn:active { background: var(--bg-base); }
  .clear { color: var(--text-muted); }
</style>
