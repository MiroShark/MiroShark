<template>
  <div class="interaction-network">
    <!-- Header -->
    <div class="net-header">
      <div class="net-title">
        <span class="net-icon">⬡</span>
        <span class="net-label">INTERACTION NETWORK</span>
      </div>
      <button
        class="net-export-btn"
        :disabled="!hasData"
        @click="downloadPNG"
        title="Download graph as PNG"
      >
        Export PNG ↓
      </button>
    </div>

    <!-- Legend -->
    <div class="net-legend">
      <span class="legend-item"><span class="legend-dot bullish-dot"></span>Bullish</span>
      <span class="legend-item"><span class="legend-dot neutral-dot"></span>Neutral</span>
      <span class="legend-item"><span class="legend-dot bearish-dot"></span>Bearish</span>
      <span class="legend-sep">|</span>
      <span class="legend-item"><span class="legend-line twitter-line"></span>Twitter</span>
      <span class="legend-item"><span class="legend-line reddit-line"></span>Reddit</span>
      <span class="legend-item"><span class="legend-line cross-line"></span>Cross-platform</span>
    </div>

    <!-- Platform filter -->
    <div v-if="hasData" class="net-filters">
      <label class="filter-check" v-for="p in availablePlatforms" :key="p">
        <input type="checkbox" :value="p" v-model="activePlatforms" />
        <span>{{ p === 'twitter' ? 'X' : p === 'reddit' ? 'Reddit' : 'Polymarket' }}</span>
      </label>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="net-state">
      <div class="pulse-ring"></div>
      <span>Computing interaction network...</span>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="net-state net-error-state">{{ error }}</div>

    <!-- No data -->
    <div v-else-if="!hasData" class="net-state">
      <span>No interaction data available.</span>
      <span class="net-hint">Run a simulation to generate agent interactions.</span>
    </div>

    <!-- Graph -->
    <div v-else class="net-graph-wrap">
      <svg
        ref="svgRef"
        :viewBox="`0 0 ${W} ${H}`"
        preserveAspectRatio="xMidYMid meet"
        class="net-svg"
        xmlns="http://www.w3.org/2000/svg"
        @mousemove="onMouseMove"
        @mouseleave="hoveredNode = null"
      >
        <!-- Edges -->
        <line
          v-for="(e, i) in visibleEdges"
          :key="'e' + i"
          :x1="nodePos[e.source]?.x || 0"
          :y1="nodePos[e.source]?.y || 0"
          :x2="nodePos[e.target]?.x || 0"
          :y2="nodePos[e.target]?.y || 0"
          :stroke="edgeColor(e)"
          :stroke-width="edgeWidth(e)"
          :opacity="hoveredNode ? (e.source === hoveredNode || e.target === hoveredNode ? 0.8 : 0.08) : 0.35"
          stroke-linecap="round"
        />

        <!-- Nodes -->
        <g
          v-for="n in visibleNodes"
          :key="'n' + n.id"
          :transform="`translate(${nodePos[n.id]?.x || 0},${nodePos[n.id]?.y || 0})`"
          class="net-node"
          :opacity="hoveredNode ? (n.id === hoveredNode || isNeighbor(n.id) ? 1 : 0.15) : 1"
          @mouseenter="hoveredNode = n.id"
        >
          <circle
            :r="nodeRadius(n)"
            :fill="nodeColor(n)"
            :stroke="n.id === hoveredNode ? 'rgba(10,10,10,0.7)' : 'rgba(10,10,10,0.15)'"
            :stroke-width="n.id === hoveredNode ? 2 : 1"
          />
          <text
            v-if="nodeRadius(n) >= 6 || n.id === hoveredNode"
            :y="nodeRadius(n) + 10"
            text-anchor="middle"
            fill="rgba(10,10,10,0.5)"
            :font-size="n.id === hoveredNode ? 10 : 8"
            font-family="monospace"
          >{{ n.name.length > 12 ? n.name.slice(0, 11) + '…' : n.name }}</text>
        </g>

        <!-- Tooltip -->
        <g v-if="hoveredNode && nodePos[hoveredNode]" :transform="`translate(${tooltipX},${tooltipY})`">
          <rect
            x="-4" y="-14"
            :width="tooltipWidth + 8"
            height="52"
            rx="4"
            fill="rgba(250,250,250,0.95)"
            stroke="rgba(10,10,10,0.15)"
            stroke-width="1"
          />
          <text x="0" y="0" font-size="10" font-family="monospace" fill="rgba(10,10,10,0.8)" font-weight="bold">
            {{ hoveredNodeData?.name }}
          </text>
          <text x="0" y="13" font-size="9" font-family="monospace" fill="rgba(10,10,10,0.5)">
            {{ hoveredNodeData?.stance }} · {{ hoveredNodeData?.platforms?.join(', ') }}
          </text>
          <text x="0" y="26" font-size="9" font-family="monospace" fill="rgba(10,10,10,0.5)">
            In: {{ hoveredNodeData?.in_degree }} · Out: {{ hoveredNodeData?.out_degree }} · Rank #{{ hoveredNodeData?.rank }}
          </text>
          <text x="0" y="34" font-size="0" fill="transparent">pad</text>
        </g>
      </svg>
    </div>

    <!-- Insights Panel -->
    <div v-if="hasData && networkData?.insights" class="net-insights">
      <div v-if="networkData.insights.top_hub" class="insight-card">
        <span class="insight-label">Top Hub</span>
        <span class="insight-text">{{ networkData.insights.top_hub.description }}</span>
      </div>
      <div v-if="networkData.insights.top_bridge" class="insight-card">
        <span class="insight-label">Top Bridge</span>
        <span class="insight-text">{{ networkData.insights.top_bridge.description }}</span>
      </div>
      <div v-if="networkData.insights.echo_chamber" class="insight-card">
        <span class="insight-label">Echo Chamber</span>
        <span class="insight-text">{{ networkData.insights.echo_chamber.description }}</span>
      </div>
      <div class="insight-card stats-row">
        <span class="insight-stat">{{ networkData.insights.total_nodes }} agents</span>
        <span class="insight-stat">{{ networkData.insights.total_edges }} interactions</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { getInteractionNetwork } from '../api/simulation'

const props = defineProps({
  simulationId: { type: String, required: true },
  visible: { type: Boolean, default: false },
})

const loading = ref(false)
const error = ref('')
const networkData = ref(null)
const svgRef = ref(null)
const hoveredNode = ref(null)
const nodePos = ref({})

const W = 560
const H = 360

const hasData = computed(() =>
  networkData.value?.nodes?.length > 0
)

const availablePlatforms = computed(() => {
  if (!hasData.value) return []
  const ps = new Set()
  for (const n of networkData.value.nodes) {
    for (const p of n.platforms) ps.add(p)
  }
  return [...ps].sort()
})

const activePlatforms = ref([])

const visibleNodes = computed(() => {
  if (!hasData.value) return []
  if (!activePlatforms.value.length) return networkData.value.nodes
  return networkData.value.nodes.filter(n =>
    n.platforms.some(p => activePlatforms.value.includes(p))
  )
})

const visibleNodeIds = computed(() => new Set(visibleNodes.value.map(n => n.id)))

const visibleEdges = computed(() => {
  if (!hasData.value) return []
  const ids = visibleNodeIds.value
  return networkData.value.edges.filter(e =>
    ids.has(e.source) && ids.has(e.target)
  )
})

const hoveredNodeData = computed(() => {
  if (!hoveredNode.value || !hasData.value) return null
  return networkData.value.nodes.find(n => n.id === hoveredNode.value)
})

const neighborSet = computed(() => {
  if (!hoveredNode.value || !hasData.value) return new Set()
  const s = new Set()
  for (const e of networkData.value.edges) {
    if (e.source === hoveredNode.value) s.add(e.target)
    if (e.target === hoveredNode.value) s.add(e.source)
  }
  return s
})

const isNeighbor = (id) => id === hoveredNode.value || neighborSet.value.has(id)

const tooltipX = computed(() => {
  if (!hoveredNode.value || !nodePos.value[hoveredNode.value]) return 0
  const x = nodePos.value[hoveredNode.value].x
  return x > W - 160 ? x - 150 : x + 15
})

const tooltipY = computed(() => {
  if (!hoveredNode.value || !nodePos.value[hoveredNode.value]) return 0
  const y = nodePos.value[hoveredNode.value].y
  return y > H - 60 ? y - 50 : y + 5
})

const tooltipWidth = computed(() => {
  if (!hoveredNodeData.value) return 100
  return Math.max(hoveredNodeData.value.name.length * 7, 120)
})

const maxWeight = computed(() => {
  if (!hasData.value) return 1
  return Math.max(...networkData.value.edges.map(e => e.weight), 1)
})

const maxDegree = computed(() => {
  if (!hasData.value) return 1
  return Math.max(...networkData.value.nodes.map(n => n.total_degree), 1)
})

const nodeRadius = (n) => {
  const base = 4
  const scale = 12
  return base + (n.total_degree / maxDegree.value) * scale
}

const nodeColor = (n) => {
  const colors = {
    bullish: 'rgba(20,184,166,0.8)',
    bearish: 'rgba(239,68,68,0.8)',
    neutral: 'rgba(148,163,184,0.8)',
  }
  return colors[n.stance] || colors.neutral
}

const edgeColor = (e) => {
  if (e.is_cross_platform) return 'rgba(139,92,246,0.6)'
  const p = e.platforms?.[0]
  if (p === 'twitter') return 'rgba(59,130,246,0.5)'
  if (p === 'reddit') return 'rgba(249,115,22,0.5)'
  return 'rgba(148,163,184,0.4)'
}

const edgeWidth = (e) => {
  return 0.5 + (e.weight / maxWeight.value) * 3
}

const onMouseMove = () => {}

const runForceLayout = () => {
  if (!hasData.value) return

  const nodes = visibleNodes.value
  const edges = visibleEdges.value
  const n = nodes.length

  if (n === 0) return

  const pos = {}
  const vel = {}
  const cx = W / 2
  const cy = H / 2
  const pad = 30

  for (const node of nodes) {
    const angle = Math.random() * 2 * Math.PI
    const r = 60 + Math.random() * 80
    pos[node.id] = { x: cx + Math.cos(angle) * r, y: cy + Math.sin(angle) * r }
    vel[node.id] = { x: 0, y: 0 }
  }

  const iterations = 200
  const repulsionK = 3000
  const attractionK = 0.015
  const idealLen = Math.min(W, H) / (Math.sqrt(n) + 1)
  const damping = 0.85
  const maxForce = 10

  const edgeSet = new Set()
  for (const e of edges) {
    edgeSet.add(e.source + '|' + e.target)
    edgeSet.add(e.target + '|' + e.source)
  }

  for (let iter = 0; iter < iterations; iter++) {
    const temp = 1 - iter / iterations

    for (const a of nodes) {
      vel[a.id].x = 0
      vel[a.id].y = 0

      for (const b of nodes) {
        if (a.id === b.id) continue
        const dx = pos[a.id].x - pos[b.id].x
        const dy = pos[a.id].y - pos[b.id].y
        const dist = Math.sqrt(dx * dx + dy * dy) || 1
        const force = repulsionK / (dist * dist)
        const fx = (dx / dist) * Math.min(force, maxForce) * temp
        const fy = (dy / dist) * Math.min(force, maxForce) * temp
        vel[a.id].x += fx
        vel[a.id].y += fy
      }
    }

    for (const e of edges) {
      if (!pos[e.source] || !pos[e.target]) continue
      const dx = pos[e.target].x - pos[e.source].x
      const dy = pos[e.target].y - pos[e.source].y
      const dist = Math.sqrt(dx * dx + dy * dy) || 1
      const force = (dist - idealLen) * attractionK * (1 + Math.log(e.weight + 1) * 0.3)
      const fx = (dx / dist) * Math.min(force, maxForce)
      const fy = (dy / dist) * Math.min(force, maxForce)
      vel[e.source].x += fx * temp
      vel[e.source].y += fy * temp
      vel[e.target].x -= fx * temp
      vel[e.target].y -= fy * temp
    }

    // Gravity toward center
    for (const node of nodes) {
      const dx = cx - pos[node.id].x
      const dy = cy - pos[node.id].y
      vel[node.id].x += dx * 0.001
      vel[node.id].y += dy * 0.001
    }

    for (const node of nodes) {
      pos[node.id].x += vel[node.id].x * damping
      pos[node.id].y += vel[node.id].y * damping
      pos[node.id].x = Math.max(pad, Math.min(W - pad, pos[node.id].x))
      pos[node.id].y = Math.max(pad, Math.min(H - pad, pos[node.id].y))
    }
  }

  nodePos.value = { ...pos }
}

const load = async () => {
  if (!props.simulationId) return
  loading.value = true
  error.value = ''
  try {
    const res = await getInteractionNetwork(props.simulationId)
    if (res.success && res.data) {
      networkData.value = res.data
      activePlatforms.value = []
      await nextTick()
      runForceLayout()
    } else if (res.success && !res.data) {
      networkData.value = null
    } else {
      error.value = res.error || 'Failed to load interaction network.'
    }
  } catch (err) {
    error.value = err.message || 'Failed to load interaction network.'
  } finally {
    loading.value = false
  }
}

const downloadPNG = () => {
  const svg = svgRef.value
  if (!svg) return
  const serializer = new XMLSerializer()
  const svgStr = serializer.serializeToString(svg)
  const canvas = document.createElement('canvas')
  canvas.width = W * 2
  canvas.height = H * 2
  const ctx = canvas.getContext('2d')
  ctx.fillStyle = '#FAFAFA'
  ctx.fillRect(0, 0, canvas.width, canvas.height)
  const img = new Image()
  img.onload = () => {
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
    const a = document.createElement('a')
    a.download = `interaction-network-${props.simulationId}.png`
    a.href = canvas.toDataURL('image/png')
    a.click()
  }
  img.src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svgStr)))
}

watch(() => props.visible, (val) => { if (val) load() })
watch(() => props.simulationId, () => { if (props.visible) load() })
watch(activePlatforms, () => { nextTick(() => runForceLayout()) })
onMounted(() => { if (props.visible) load() })
</script>

<style scoped>
.interaction-network {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  font-family: var(--font-mono);
  background: var(--background);
}

/* Header */
.net-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(10,10,10,0.08);
  flex-shrink: 0;
}

.net-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.net-icon {
  color: #8b5cf6;
  font-size: 14px;
}

.net-label {
  font-size: 12px;
  letter-spacing: 3px;
  text-transform: uppercase;
  color: rgba(10,10,10,0.5);
}

.net-export-btn {
  background: none;
  border: 1px solid rgba(10,10,10,0.15);
  padding: 4px 10px;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 1px;
  cursor: pointer;
  color: rgba(10,10,10,0.5);
  transition: all 0.15s ease;
}

.net-export-btn:hover:not(:disabled) {
  border-color: #8b5cf6;
  color: #8b5cf6;
}

.net-export-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

/* Legend */
.net-legend {
  display: flex;
  gap: 12px;
  padding: 8px 16px;
  border-bottom: 1px solid rgba(10,10,10,0.05);
  flex-shrink: 0;
  flex-wrap: wrap;
  align-items: center;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  color: rgba(10,10,10,0.35);
  letter-spacing: 1px;
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.bullish-dot { background: rgba(20,184,166,0.8); }
.neutral-dot { background: rgba(148,163,184,0.8); }
.bearish-dot { background: rgba(239,68,68,0.8); }

.legend-sep {
  color: rgba(10,10,10,0.15);
  font-size: 10px;
}

.legend-line {
  width: 16px;
  height: 2px;
  border-radius: 1px;
}

.twitter-line { background: rgba(59,130,246,0.7); }
.reddit-line { background: rgba(249,115,22,0.7); }
.cross-line { background: rgba(139,92,246,0.7); }

/* Filters */
.net-filters {
  display: flex;
  gap: 12px;
  padding: 6px 16px;
  border-bottom: 1px solid rgba(10,10,10,0.05);
  flex-shrink: 0;
}

.filter-check {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  color: rgba(10,10,10,0.4);
  letter-spacing: 1px;
  cursor: pointer;
}

.filter-check input {
  accent-color: #8b5cf6;
}

/* States */
.net-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  gap: 8px;
  padding: 40px;
  font-size: 13px;
  color: rgba(10,10,10,0.35);
  letter-spacing: 1px;
  text-align: center;
}

.net-error-state { color: #dc2626; }

.net-hint {
  font-size: 11px;
  color: rgba(10,10,10,0.25);
}

.pulse-ring {
  width: 20px;
  height: 20px;
  border: 2px solid #8b5cf6;
  border-radius: 50%;
  animation: pulse 1.2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50%       { transform: scale(1.4); opacity: 0.4; }
}

/* Graph */
.net-graph-wrap {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 4px 8px;
  min-height: 0;
}

.net-svg {
  width: 100%;
  height: 100%;
  max-height: 380px;
  overflow: visible;
  cursor: crosshair;
}

.net-node {
  cursor: pointer;
  transition: opacity 0.15s ease;
}

/* Insights */
.net-insights {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 16px;
  border-top: 1px solid rgba(10,10,10,0.06);
  flex-shrink: 0;
  overflow-y: auto;
  max-height: 140px;
}

.insight-card {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.insight-label {
  font-size: 10px;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: rgba(10,10,10,0.35);
}

.insight-text {
  font-size: 11px;
  color: rgba(10,10,10,0.6);
  line-height: 1.4;
  letter-spacing: 0.3px;
}

.stats-row {
  flex-direction: row;
  gap: 16px;
  padding-top: 4px;
  border-top: 1px solid rgba(10,10,10,0.05);
}

.insight-stat {
  font-size: 10px;
  color: rgba(10,10,10,0.3);
  letter-spacing: 1px;
}
</style>
