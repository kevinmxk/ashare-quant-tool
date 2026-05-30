<template>
  <div ref="chartRef" class="w-full h-full"></div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import type { BarDataPoint } from '../api/types'

const props = defineProps<{
  data: BarDataPoint[]
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

  const dates = props.data.map((d) => d.date)
  const klineData = props.data.map((d) => [d.open, d.close, d.low, d.high])
  const volumes = props.data.map((d) => d.volume)

  // 极简日期：月-日
  const shortDates = dates.map((d) => {
    const parts = d.split('-')
    return `${parts[1]}-${parts[2]}`
  })

  // A股标准：涨红跌绿
  const upColor = '#e74c3c'
  const downColor = '#27ae60'

  const option: echarts.EChartsOption = {
    backgroundColor: 'transparent',
    animation: true,
    animationDuration: 400,
    tooltip: { show: false },
    grid: [
      { left: 2, right: 2, top: 4, bottom: '24%' },
      { left: 2, right: 2, top: '78%', bottom: 0 },
    ],
    xAxis: [
      {
        type: 'category',
        data: shortDates,
        gridIndex: 0,
        boundaryGap: true,
        axisLine: { show: false },
        axisLabel: { show: false },
        axisTick: { show: false },
      },
      {
        type: 'category',
        data: shortDates,
        gridIndex: 1,
        boundaryGap: true,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          show: true,
          color: '#6e7681',
          fontSize: 8,
          interval: Math.floor(shortDates.length / 4),
        },
      },
    ],
    yAxis: [
      { type: 'value', show: false, scale: true, gridIndex: 0 },
      { type: 'value', show: false, gridIndex: 1 },
    ],
    series: [
      {
        type: 'candlestick',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: klineData,
        barWidth: '55%',
        itemStyle: {
          color: upColor,
          color0: downColor,
          borderColor: upColor,
          borderColor0: downColor,
        },
      },
      {
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumes,
        barWidth: '55%',
        itemStyle: {
          color: (params: any) => {
            const idx = params.dataIndex
            const close = props.data[idx].close
            const open = props.data[idx].open
            return close >= open ? 'rgba(231, 76, 60, 0.35)' : 'rgba(39, 174, 96, 0.35)'
          },
        },
      },
    ],
  }

  chartInstance.setOption(option)
}

let resizeObserver: ResizeObserver | null = null

onMounted(() => {
  initChart()
  if (chartRef.value) {
    resizeObserver = new ResizeObserver(() => {
      chartInstance?.resize()
    })
    resizeObserver.observe(chartRef.value)
  }
})

onUnmounted(() => {
  resizeObserver?.disconnect()
  chartInstance?.dispose()
})

watch(
  () => props.data,
  () => {
    renderChart()
  },
  { deep: true },
)
</script>
