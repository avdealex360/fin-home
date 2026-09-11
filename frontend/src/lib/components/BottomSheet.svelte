<script lang="ts">
  import { untrack } from 'svelte'
  import { SpringValue, VelocityTracker, SPRINGS, project, rubberband, clamp, prefersReducedMotion } from '../motion'

  interface Props {
    open: boolean
    title?: string
    onclose: () => void
    children: import('svelte').Snippet
  }
  let { open, title = '', onclose, children }: Props = $props()

  const TAP_SLOP = 6
  /** Below this speed the release point decides; above it the direction of the flick does. */
  const FLICK_SPEED = 180
  const DESKTOP_MQ = '(min-width: 640px)'

  // `visible` outlives `open` so the sheet can animate out before unmounting.
  let visible = $state(false)
  let sheetH = $state(0)
  // Vertical offset from the resting (open) position, in px. 0 = open.
  let y = $state(0)
  let dragging = $state(false)
  let closing = false
  let desktop = $state(false)
  let reduced = $state(false)

  const spring = new SpringValue(0, SPRINGS.default, (v) => (y = v), onSettled)
  const tracker = new VelocityTracker()
  let grabOffset = 0
  let moved = 0

  /** Distance at which the sheet counts as gone. Desktop dialog "materialises" over a short rise. */
  let closedY = $derived(desktop ? Math.max(80, Math.round(sheetH * 0.25)) : Math.max(sheetH, 320))
  let progress = $derived(closedY > 0 ? clamp(1 - y / closedY, 0, 1) : 1)

  $effect(() => {
    const mq = matchMedia(DESKTOP_MQ)
    desktop = mq.matches
    reduced = prefersReducedMotion()
    const onChange = () => (desktop = mq.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  })

  // open → mount off-screen, then spring in. close → spring out, unmount on settle.
  // Only `open` is tracked here; geometry changes must not re-trigger the animation.
  $effect(() => {
    const isOpen = open
    untrack(() => {
      if (isOpen) {
        closing = false
        if (!visible) {
          visible = true
          // start fully off-screen; the real height is measured on the next frame
          spring.snap(closedY)
          requestAnimationFrame(() => {
            if (!visible) return
            spring.snap(Math.max(spring.value, closedY))
            spring.setTarget(0, reduced ? { response: 0.22, dampingRatio: 1 } : SPRINGS.default)
          })
        } else {
          spring.setTarget(0, SPRINGS.default)
        }
      } else if (visible && !closing) {
        dismiss(reduced ? { response: 0.2, dampingRatio: 1 } : SPRINGS.default)
      }
    })
  })

  function dismiss(opts: { response?: number; dampingRatio?: number; velocity?: number }) {
    closing = true
    spring.setTarget(closedY, opts)
  }
  function onSettled() {
    if (closing && spring.value >= closedY - 1) {
      visible = false
      closing = false
      y = 0
    }
  }

  function onKey(e: KeyboardEvent) {
    if (e.key === 'Escape' && open) onclose()
  }

  // ── Drag ──────────────────────────────────────────────────────────────
  function onDragStart(e: PointerEvent) {
    if (e.button !== 0 && e.pointerType === 'mouse') return
    e.preventDefault()
    try { (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId) } catch { /* synthetic / already-released pointer */ }
    // Grab wherever the sheet is right now — even mid-flight — and hold the offset.
    spring.stop()
    closing = false
    grabOffset = e.clientY - y
    moved = 0
    dragging = true
    tracker.reset()
    tracker.push(e.clientY, e.timeStamp)
  }
  function onDragMove(e: PointerEvent) {
    if (!dragging) return
    const raw = e.clientY - grabOffset
    moved = Math.max(moved, Math.abs(raw))
    tracker.push(e.clientY, e.timeStamp)
    // Above the resting point there is nothing more — resist instead of stopping hard.
    const next = raw < 0 ? rubberband(raw, sheetH || 400) : raw
    spring.snap(next)
  }
  function onDragEnd(e: PointerEvent) {
    if (!dragging) return
    dragging = false
    const v = tracker.velocity() // px/s, positive = downwards
    const tap = moved < TAP_SLOP

    let shouldClose: boolean
    // The parent already asked us to close — a grab mid-flight may delay it, not cancel it.
    if (tap || !open) shouldClose = true
    else if (Math.abs(v) > FLICK_SPEED) shouldClose = v > 0
    else shouldClose = y + project(v) > closedY * 0.5

    if (shouldClose) {
      // Hand the finger's velocity to the spring so there is no seam.
      dismiss({ ...SPRINGS.sheet, velocity: tap ? 0 : Math.max(v, 0) })
      if (open) onclose()
    } else {
      spring.setTarget(0, { ...SPRINGS.sheet, velocity: v })
    }
  }

  let transform = $derived.by(() => {
    if (reduced) return desktop ? 'translate3d(0, -50%, 0)' : 'none'
    if (desktop) {
      const s = 0.96 + 0.04 * progress
      return `translate3d(0, calc(-50% + ${y.toFixed(2)}px), 0) scale(${s.toFixed(4)})`
    }
    return `translate3d(0, ${y.toFixed(2)}px, 0)`
  })
  let sheetOpacity = $derived(desktop || reduced ? progress : 1)
</script>

<svelte:window on:keydown={onKey} />

{#if visible}
  <div class="overlay" style="opacity: {progress}" onclick={onclose} role="presentation"></div>
  <div
    bind:clientHeight={sheetH}
    class="sheet"
    class:dragging
    style="transform: {transform}; opacity: {sheetOpacity}"
    role="dialog"
    aria-modal="true"
    aria-label={title}
  >
    <div
      class="sheet-header"
      role="button"
      tabindex="0"
      aria-label="Закрыть"
      onpointerdown={onDragStart}
      onpointermove={onDragMove}
      onpointerup={onDragEnd}
      onpointercancel={onDragEnd}
      onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') onclose() }}
    >
      <div class="grabber"></div>
      {#if title}<h2 class="sheet-title">{title}</h2>{/if}
    </div>
    <div class="sheet-body">
      {@render children()}
    </div>
  </div>
{/if}

<style>
  .overlay {
    position: fixed;
    inset: 0;
    background: var(--bg-overlay);
    z-index: 40;
    will-change: opacity;
  }
  .sheet {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 50;
    max-width: var(--shell-w);
    margin: 0 auto;
    background: var(--bg-elevated);
    border-radius: var(--radius-xl) var(--radius-xl) 0 0;
    /* bright top edge = light catching the material */
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    box-shadow: var(--shadow-sheet);
    padding: var(--space-3) var(--space-4) calc(var(--space-6) + env(safe-area-inset-bottom));
    max-height: 92dvh;
    overflow-y: auto;
    will-change: transform, opacity;
    transform-origin: 50% 50%;
  }
  /* Desktop: present as a centred dialog that materialises (rise + scale + fade). */
  @media (min-width: 640px) {
    .sheet {
      top: 50%;
      bottom: auto;
      max-width: 520px;
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: var(--radius-xl);
      max-height: 88dvh;
    }
  }
  .sheet-header {
    padding: var(--space-3) 0;
    margin: -8px 0 var(--space-2);
    cursor: grab;
    touch-action: none;
    user-select: none;
    -webkit-user-select: none;
  }
  .sheet.dragging .sheet-header { cursor: grabbing; }
  .grabber {
    width: 40px;
    height: 4px;
    border-radius: 999px;
    background: var(--text-muted);
    margin: 0 auto var(--space-2);
    transition: background 120ms ease-out;
  }
  .sheet.dragging .grabber { background: var(--text-secondary); }
  .sheet-title {
    font-size: var(--text-lg);
    letter-spacing: -0.015em;
    margin: 0;
  }
  .sheet-body { display: flex; flex-direction: column; gap: var(--space-4); }

  @media (prefers-reduced-transparency: reduce) {
    .overlay { background: rgba(4, 6, 10, 0.85); }
  }
</style>
