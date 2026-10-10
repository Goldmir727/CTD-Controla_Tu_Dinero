<script setup lang="ts">
/** Envoltura de ECharts con imports modulares (no el bundle completo) para no
 *  engordar la PWA. Lee el tema, se redimensiona sola y respeta el modo lite. */
import { onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import * as echarts from 'echarts/core'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { animacionesOff } from '../composables/usePerf'
import { useTema } from '../composables/useTema'
import { coloresTexto } from '../utils/paleta'

// Solo se registran los tipos y componentes que la app usa: ECharts trae muchos mas
// y cada uno suma al bundle. Agregar uno aqui obliga a sumarlo tambien alli.
echarts.use([BarChart, LineChart, PieChart, GridComponent,
  LegendComponent, TooltipComponent, CanvasRenderer])

const props = defineProps<{ opcion: Record<string, unknown>; alto?: number }>()
const emit = defineEmits<{ (e: 'click', p: unknown): void }>()

const el = ref<HTMLElement | null>(null)
// shallowRef: ECharts guarda estado mutable enorme; reactive lo proxy-ea todo.
const inst = shallowRef<echarts.ECharts | null>(null)
const { tema } = useTema()
let obs: ResizeObserver | null = null

function pintar() {
  if (!inst.value) return
  // echarts/core no exporta EChartsOption (solo el bundle completo); el tipo
  // estructural correcto para el uso modular es EChartsCoreOption.
  inst.value.setOption(ajustarEjes(props.opcion) as echarts.EChartsCoreOption, {
    notMerge: true,
    lazyUpdate: true
  })
}

function ajustarEjes(op: Record<string, unknown>) {
  const c = coloresTexto(tema.value === 'dark')
  // ECharts no lee variables CSS del host, asi que se inyectan los colores aqui.
  const base: Record<string, unknown> = {
    animation: animacionesOff() ? false : undefined,
    textStyle: { color: c.texto, fontFamily: 'inherit' },
    ...op
  }
  if (base.animation === undefined) delete base.animation
  if (base.tooltip) {
    base.tooltip = {
      backgroundColor: c.superficie,
      borderColor: c.linea,
      textStyle: { color: c.texto },
      ...(base.tooltip as object)
    }
  }
  if (base.legend) {
    base.legend = { textStyle: { color: c.suave }, ...(base.legend as object) }
  }
  if (base.xAxis || base.yAxis) {
    const eje = {
      axisLine: { lineStyle: { color: c.linea } },
      axisLabel: { color: c.suave },
      splitLine: { lineStyle: { color: c.linea, type: 'dashed' } }
    }
    base.xAxis = base.xAxis ? [{ ...eje, ...(base.xAxis as object) }] : eje
    base.yAxis = base.yAxis ? [{ ...eje, ...(base.yAxis as object) }] : eje
  }
  return base
}

onMounted(() => {
  if (!el.value) return
  inst.value = echarts.init(el.value, undefined, { renderer: 'canvas' })
  inst.value.on('click', (p) => emit('click', p))
  pintar()
  obs = new ResizeObserver(() => inst.value?.resize())
  obs.observe(el.value)
})

onBeforeUnmount(() => {
  obs?.disconnect()
  inst.value?.dispose()
  inst.value = null
})

watch(() => props.opcion, pintar, { deep: true })
// Sin .value no seeria reactivo: compararia el objeto ref, que nunca cambia de identidad.
watch(() => tema.value, pintar)
</script>

<template>
  <div ref="el" class="grafico" :style="{ height: (alto ?? 240) + 'px' }"
       :data-lite="animacionesOff() ? '1' : '0'" />
</template>

<style scoped>
.grafico {
  width: 100%;
  min-height: 120px;
}
</style>
