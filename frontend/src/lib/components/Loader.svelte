<script lang="ts">
  interface Props {
    label?: string
  }
  let { label = 'Загрузка…' }: Props = $props()
</script>

<div class="loader-wrap">
  <svg class="spinner" viewBox="0 0 50 50" role="img" aria-label={label}>
    <circle class="track" cx="25" cy="25" r="20" fill="none" stroke-width="4" />
    <circle class="arc" cx="25" cy="25" r="20" fill="none" stroke-width="4" stroke-linecap="round" />
  </svg>
  <span class="label">{label}</span>
</div>

<style>
  .loader-wrap {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-10);
  }
  .spinner {
    width: 40px;
    height: 40px;
    animation: rotate 1s linear infinite;
  }
  .track {
    stroke: var(--bg-elevated);
  }
  .arc {
    stroke: var(--blue);
    stroke-dasharray: 90 150;
    stroke-dashoffset: 0;
    animation: dash 1.4s ease-in-out infinite;
  }
  .label {
    color: var(--text-muted);
    font-size: var(--text-sm);
  }

  @keyframes rotate {
    to { transform: rotate(360deg); }
  }
  @keyframes dash {
    0% { stroke-dasharray: 1 150; stroke-dashoffset: 0; }
    50% { stroke-dasharray: 90 150; stroke-dashoffset: -35; }
    100% { stroke-dasharray: 90 150; stroke-dashoffset: -124; }
  }

  @media (prefers-reduced-motion: reduce) {
    .spinner { animation-duration: 2s; }
    .arc { animation: none; stroke-dasharray: 90 150; }
  }
</style>
