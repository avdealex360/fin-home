<script lang="ts">
  import { onMount, onDestroy } from 'svelte'
  import {
    Chart,
    LineController,
    BarController,
    LineElement,
    BarElement,
    PointElement,
    LinearScale,
    CategoryScale,
    Tooltip,
    Legend,
    Filler,
  } from 'chart.js'

  Chart.register(
    LineController, BarController, LineElement, BarElement, PointElement,
    LinearScale, CategoryScale, Tooltip, Legend, Filler,
  )

  interface Props {
    type: 'line' | 'bar'
    labels: string[]
    datasets: any[]
    height?: number
  }
  let { type, labels, datasets, height = 200 }: Props = $props()

  let canvas: HTMLCanvasElement
  let chart: Chart | null = null

  const css = (v: string) =>
    getComputedStyle(document.documentElement).getPropertyValue(v).trim()

  function build() {
    if (chart) chart.destroy()
    chart = new Chart(canvas, {
      type,
      data: { labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { intersect: false, mode: 'index' },
        plugins: {
          legend: {
            labels: { color: css('--text-secondary'), boxWidth: 12, font: { size: 11 } },
          },
        },
        scales: {
          x: {
            grid: { color: 'rgba(255,255,255,0.04)' },
            ticks: { color: css('--text-muted'), font: { size: 10 } },
          },
          y: {
            grid: { color: 'rgba(255,255,255,0.04)' },
            ticks: { color: css('--text-muted'), font: { size: 10 } },
          },
        },
      },
    })
  }

  onMount(build)
  onDestroy(() => chart?.destroy())

  // Rebuild when data changes.
  $effect(() => {
    void labels
    void datasets
    if (chart) build()
  })
</script>

<div class="chart-wrap" style="height: {height}px">
  <canvas bind:this={canvas}></canvas>
</div>

<style>
  .chart-wrap { position: relative; width: 100%; }
</style>
