<script lang="ts">
  interface Props {
    label?: string
  }
  let { label = 'Загрузка…' }: Props = $props()
</script>

<div class="loader-wrap">
  <svg class="cat" viewBox="0 0 120 110" role="img" aria-label={label}>
    <ellipse class="tail" cx="94" cy="80" rx="5" ry="20" />
    <g class="paw paw-l"><ellipse cx="46" cy="94" rx="9" ry="7" /></g>
    <g class="paw paw-r"><ellipse cx="74" cy="94" rx="9" ry="7" /></g>
    <g class="body-group">
      <ellipse class="body" cx="60" cy="66" rx="26" ry="21" />
      <circle class="head" cx="60" cy="36" r="19" />
      <polygon class="ear" points="42,26 38,8 54,22" />
      <polygon class="ear" points="78,26 82,8 66,22" />
      <circle class="eye" cx="52" cy="35" r="2.6" />
      <circle class="eye" cx="68" cy="35" r="2.6" />
      <path class="mouth" d="M55 43 Q60 47 65 43" />
    </g>
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
  .cat {
    width: 84px;
    height: 77px;
    overflow: visible;
  }
  .label {
    color: var(--text-muted);
    font-size: var(--text-sm);
  }
  .body-group {
    transform-origin: 60px 90px;
    animation: bob 0.9s ease-in-out infinite;
  }
  .body, .head {
    fill: var(--bg-elevated);
    stroke: var(--gold);
    stroke-width: 1.5;
  }
  .ear {
    fill: var(--bg-elevated);
    stroke: var(--gold);
    stroke-width: 1.5;
    stroke-linejoin: round;
  }
  .eye {
    fill: var(--text-primary);
  }
  .mouth {
    fill: none;
    stroke: var(--gold);
    stroke-width: 1.5;
    stroke-linecap: round;
  }
  .tail {
    fill: var(--bg-elevated);
    stroke: var(--gold);
    stroke-width: 1.5;
    transform-origin: 94px 62px;
    animation: wag 0.6s ease-in-out infinite;
  }
  .paw {
    transform-origin: center;
  }
  .paw ellipse {
    fill: var(--bg-elevated);
    stroke: var(--gold);
    stroke-width: 1.5;
  }
  .paw-l {
    animation: step 0.9s ease-in-out infinite;
  }
  .paw-r {
    animation: step 0.9s ease-in-out infinite;
    animation-delay: 0.45s;
  }

  @keyframes bob {
    0%, 100% { transform: translateY(0) rotate(0deg); }
    50% { transform: translateY(-6px) rotate(-3deg); }
  }
  @keyframes wag {
    0%, 100% { transform: rotate(-18deg); }
    50% { transform: rotate(18deg); }
  }
  @keyframes step {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-4px); }
  }

  @media (prefers-reduced-motion: reduce) {
    .body-group, .tail, .paw-l, .paw-r {
      animation: none;
    }
  }
</style>
