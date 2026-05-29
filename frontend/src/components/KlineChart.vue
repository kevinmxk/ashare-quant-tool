<template>
  <div ref="chartRef" class="w-full rounded-xl border border-line bg-panel overflow-hidden" :style="{ height: height + 'px' }"></div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import type { BarDataPoint } from '../api/types'

const props = defineProps<{
  data: BarDataPoint[]
  height?: number
}>()

const chartRef = ref<HTMLDivElement | null>(null)
let chartInstance: echarts.ECharts | null = null

function initChart() {
  if (!chartRef.value) return
  if (chartInstance) {
    chartInstance.dispose()
  }
  chartInstance = echarts.init(chartRef.value, 'dark')
  renderChart()
}

function renderChart() {
  if (!chartInstance || !props.data.length) return

  const dates = props.data.map(d => d.date)
  const klineData = props.data.map(d => [d.open, d.close, d.low, d.high])
  const volumes = props.data.map(d => d.volume)

  // MA20
  const ma20: (number | null)[] = []
  for (let i = 0; i < props.data.length; i++) {
    if (i < 19) {
      ma20.push(null)
      continue
    }
    let sum = 0
    for (let j = 0; j < 20; j++) {
      sum += props.data[i - j].close
    }
    ma20.push(parseFloat((sum / 20).toFixed(2)))
  }

  const option: echarts.EChartsOption = {
    backgroundColor: 'transparent',
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: '#161b22',
      borderColor: '#21262d',
      textStyle: { color: '#e6edf3', fontSize: 12 },
    },
    grid: [
      { left: '3%', right: '3%', top: '4%', height: '62%' },
      { left: '3%', right: '3%', top: '72%', height: '22%' },
    ],
    xAxis: [
      {
        type: 'category',
        data: dates,
        gridIndex: 0,
        axisLine: { lineStyle: { color: '#21262d' } },
        axisLabel: { color: '#8b949e', fontSize: 10 },
        axisTick: { show: false },
      },
      {
        type: 'category',
        data: dates,
        gridIndex: 1,
        axisLine: { show: false },
        axisLabel: { show: false },
        axisTick: { show: false },
      },
    ],
    yAxis: [
      {
        scale: true,
        gridIndex: 0,
        splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
        axisLabel: { color: '#8b949e', fontSize: 10 },
        axisLine: { show: false },
        axisTick: { show: false },
      },
      {
        scale: true,
        gridIndex: 1,
        splitLine: { show: false },
        axisLabel: { color: '#8b949e', fontSize: 10 },
        axisLine: { show: false },
        axisTick: { show: false },
      },
    ],
    dataZoom: [{ type: 'inside', xAxisIndex: [0, 1], start: 0, end: 100 }],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: klineData,
        itemStyle: {
          color: '#3fb950',
          color0: '#f85149',
          borderColor: '#3fb950',
          borderColor0: '#f85149',
        },
      },
      {
        name: 'MA20',
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: ma20,
        smooth: true,
        showSymbol: false,
        lineStyle: { color: '#58a6ff', width: 1.5 },
      },
      {
        name: '成交量',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumes,
        itemStyle: {
          color: (params: any) => {
            const idx = params.dataIndex
            const close = props.data[idx].close
            const open = props.data[idx].open
            return close >= open ? '#3fb950' : '#f85149'
          },
          opacity: 0.7,
        },
      },
    ],
  }

  chartInstance.setOption(option)
}

function handleResize() {
  chartInstance?.resize()
}

onMounted(() => {
  initChart()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chartInstance?.dispose()
})

watch(() => props.data, () => {
  renderChart()
}, { deep: true })
</script>
