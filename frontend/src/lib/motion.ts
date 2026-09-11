/**
 * Small physics toolkit for gesture-driven UI (see .claude/skills/apple-design).
 *
 * Springs here are parameterised the Apple way — `response` (seconds to reach
 * the target, roughly) and `dampingRatio` (1 = no overshoot, <1 = bounce) —
 * instead of raw stiffness/damping. Every spring animates from its *current*
 * value and velocity, so it can be re-targeted or grabbed mid-flight without a
 * visible jump.
 */

export interface SpringOptions {
  /** Seconds to settle, approximately. Lower = snappier. */
  response?: number
  /** 1 = critically damped (no bounce). ~0.8 = slight overshoot for flicks. */
  dampingRatio?: number
}

export interface RetargetOptions extends SpringOptions {
  /** Initial velocity in units/s (e.g. px/s from a gesture). Defaults to the current velocity. */
  velocity?: number
}

/** Apple-style presets. Critically damped is the default for anything that was not thrown. */
export const SPRINGS = {
  /** Programmatic show/hide, reposition. */
  default: { response: 0.38, dampingRatio: 1 } as SpringOptions,
  /** Release of a dragged sheet/drawer — the gesture carried momentum, so a hint of bounce. */
  sheet: { response: 0.32, dampingRatio: 0.82 } as SpringOptions,
  /** Rotation / flip. */
  rotation: { response: 0.48, dampingRatio: 0.78 } as SpringOptions,
  /** Progress fills, subtle value changes. */
  gentle: { response: 0.55, dampingRatio: 1 } as SpringOptions,
}

const REST_DELTA = 0.05
const REST_VELOCITY = 0.5
const MAX_DT = 1 / 30

export class SpringValue {
  value: number
  velocity = 0
  target: number
  private response: number
  private dampingRatio: number
  private raf = 0
  private last = 0
  private onFrame: (v: number) => void
  private onSettle?: () => void

  constructor(initial: number, opts: SpringOptions, onFrame: (v: number) => void, onSettle?: () => void) {
    this.value = initial
    this.target = initial
    this.response = opts.response ?? 0.38
    this.dampingRatio = opts.dampingRatio ?? 1
    this.onFrame = onFrame
    this.onSettle = onSettle
  }

  /** Animate towards `target` from wherever the value is right now. */
  setTarget(target: number, opts: RetargetOptions = {}) {
    this.target = target
    if (opts.response !== undefined) this.response = opts.response
    if (opts.dampingRatio !== undefined) this.dampingRatio = opts.dampingRatio
    if (opts.velocity !== undefined) this.velocity = opts.velocity
    if (!this.raf) this.last = performance.now()
    // Always (re)schedule: a frame that was queued while the tab was hidden may
    // never have fired, and a stale handle must not block the new target.
    else cancelAnimationFrame(this.raf)
    this.raf = requestAnimationFrame(this.tick)
  }

  /** Jump instantly (e.g. while the finger drives the value 1:1). Kills momentum. */
  snap(value: number) {
    this.stop()
    this.value = value
    this.target = value
    this.velocity = 0
    this.onFrame(value)
  }

  /** Freeze mid-flight, keeping the presentation value where it is. */
  stop() {
    if (this.raf) cancelAnimationFrame(this.raf)
    this.raf = 0
  }

  get animating() {
    return this.raf !== 0
  }

  private tick = (now: number) => {
    let dt = Math.min((now - this.last) / 1000, MAX_DT)
    this.last = now
    if (dt <= 0) dt = 1 / 60

    // Damped harmonic oscillator, semi-implicit Euler with a fixed sub-step
    // so a slow frame does not blow the integration up.
    const omega = (2 * Math.PI) / this.response
    const k = omega * omega
    const c = 2 * this.dampingRatio * omega
    const steps = Math.ceil(dt / (1 / 240))
    const h = dt / steps
    for (let i = 0; i < steps; i++) {
      const acc = -k * (this.value - this.target) - c * this.velocity
      this.velocity += acc * h
      this.value += this.velocity * h
    }

    const settled =
      Math.abs(this.value - this.target) < REST_DELTA && Math.abs(this.velocity) < REST_VELOCITY
    if (settled) {
      this.value = this.target
      this.velocity = 0
      this.raf = 0
      this.onFrame(this.value)
      this.onSettle?.()
      return
    }
    this.onFrame(this.value)
    this.raf = requestAnimationFrame(this.tick)
  }
}

/** Velocity estimate from the last ~100 ms of pointer samples. */
export class VelocityTracker {
  private samples: { p: number; t: number }[] = []

  reset() {
    this.samples = []
  }
  push(p: number, t = performance.now()) {
    this.samples.push({ p, t })
    // keep a short window only
    const cutoff = t - 120
    while (this.samples.length > 2 && this.samples[0].t < cutoff) this.samples.shift()
  }
  /** units per second */
  velocity(): number {
    if (this.samples.length < 2) return 0
    const a = this.samples[0]
    const b = this.samples[this.samples.length - 1]
    const dt = (b.t - a.t) / 1000
    if (dt <= 0) return 0
    return (b.p - a.p) / dt
  }
}

/** Where a flick would come to rest, UIScrollView-style deceleration. */
export function project(velocity: number, decelerationRate = 0.998): number {
  return ((velocity / 1000) * decelerationRate) / (1 - decelerationRate)
}

/** Progressive resistance past a boundary. Sign-preserving. */
export function rubberband(overshoot: number, dimension: number, constant = 0.55): number {
  const abs = Math.abs(overshoot)
  const r = (abs * dimension * constant) / (dimension + constant * abs)
  return overshoot < 0 ? -r : r
}

export function clamp(v: number, lo: number, hi: number) {
  return Math.min(hi, Math.max(lo, v))
}

/** Reduced-motion: swap slides/springs for short cross-fades. */
export function prefersReducedMotion(): boolean {
  return typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches
}
