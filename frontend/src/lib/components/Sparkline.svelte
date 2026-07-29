<script lang="ts">
  interface Props {
    values: number[]
    color?: string
    width?: number
    height?: number
  }
  let { values, color = 'var(--blue)', width = 90, height = 32 }: Props = $props()

  let d = $derived.by(() => {
    if (values.length < 2) return ''
    const min = Math.min(...values)
    const max = Math.max(...values)
    const range = max - min || 1
    return values
      .map((v, i) => {
        const x = 1 + (i * (width - 2)) / (values.length - 1)
        const y = height - 3 - ((v - min) / range) * (height - 6)
        return `${i ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`
      })
      .join(' ')
  })
</script>

<svg viewBox="0 0 {width} {height}" preserveAspectRatio="none" style="width:{width}px;height:{height}px">
  <path {d} fill="none" stroke={color} stroke-width="2" stroke-linejoin="round" stroke-linecap="round" opacity="0.75" />
</svg>
