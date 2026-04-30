<template>
  <div class="map-layout">
    <header class="map-topbar">
      <button class="back-btn" type="button" @click="goBack">← List view 📋</button>
      <div class="brand">DECISION MAP</div>
      <div class="topic">{{ tree?.question || 'Loading…' }}</div>
      <button class="back-btn" type="button" @click="goChat">Back to chat</button>
    </header>

    <div v-if="error" class="error">{{ error }}</div>
    <div v-if="loading && !tree" class="loading">Loading tree…</div>

    <main class="map-canvas-wrap" v-if="tree">
      <svg ref="svgEl" class="map-svg"></svg>
    </main>

    <aside v-if="selectedNode" class="detail-pane">
      <header class="detail-header">
        <span class="badge">{{ typeIcon(selectedNode.type) }}</span>
        <h3>{{ selectedNode.question }}</h3>
        <button type="button" class="close" @click="selectedNode = null">×</button>
      </header>

      <div v-if="selectedNode.summary" class="summary" v-html="renderSummary(selectedNode.summary)"></div>
      <div v-else class="muted">No synthesis yet — run Synthesize on this node from the list view.</div>

      <div v-if="selectedNode.evidence?.length" class="evidence-block">
        <h4>Sources ({{ fetchedEvidenceCount(selectedNode) }} fetched)</h4>
        <ul>
          <li v-for="(e, i) in selectedNode.evidence" :key="i">
            <a :href="e.url" target="_blank" rel="noopener noreferrer">{{ e.title || e.url }}</a>
            <span v-if="e.fetch_error" class="status err">⚠ {{ e.fetch_error }}</span>
          </li>
        </ul>
      </div>
    </aside>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as d3 from 'd3'
import { marked } from 'marked'
import { getSession } from '../api/seedChat.js'
import { extractEssence, truncate, fetchedEvidenceCount } from '../utils/treeEssence.js'

const route = useRoute()
const router = useRouter()

const sessionId = route.params.sessionId
const tree = ref(null)
const loading = ref(true)
const error = ref('')
const selectedNode = ref(null)
const svgEl = ref(null)

const NODE_WIDTH = 240
const NODE_HEIGHT = 110
const TYPE_COLORS = {
  central: '#4ade80',
  upstream: '#60a5fa',
  downstream: '#f59e0b',
  analogy: '#c084fc',
  free: '#9ca3af',
}

function typeIcon(type) {
  switch (type) {
    case 'central': return '🎯'
    case 'upstream': return '⬆'
    case 'downstream': return '⬇'
    case 'analogy': return '↔'
    default: return '✦'
  }
}

function renderSummary(md) {
  return marked.parse(md || '')
}

function goBack() {
  router.push({ name: 'DecisionTree', params: { sessionId } })
}

function goChat() {
  router.push({ name: 'SeedChat', query: { session: sessionId } })
}

async function loadTree() {
  loading.value = true
  error.value = ''
  try {
    const session = await getSession(sessionId)
    if (session?.tree) {
      tree.value = session.tree
      await nextTick()
      drawTree()
    } else {
      error.value = 'No tree on this session yet. Open list view first to initialise it.'
    }
  } catch (err) {
    error.value = err?.response?.data?.error || err.message
  } finally {
    loading.value = false
  }
}

function drawTree() {
  if (!svgEl.value || !tree.value) return

  const container = svgEl.value.parentElement
  const width = container.clientWidth
  const height = Math.max(800, container.clientHeight)

  const svg = d3.select(svgEl.value)
    .attr('width', width)
    .attr('height', height)
  svg.selectAll('*').remove()

  const root = d3.hierarchy(tree.value, d => d.children || [])

  // Vertical hierarchical layout, sized so the largest level fits horizontally
  const treeLayout = d3.tree()
    .nodeSize([NODE_WIDTH + 30, NODE_HEIGHT + 80])
    .separation((a, b) => a.parent === b.parent ? 1 : 1.3)

  treeLayout(root)

  // Compute extents to pan/zoom-fit
  let xMin = Infinity, xMax = -Infinity, yMin = Infinity, yMax = -Infinity
  root.each(d => {
    if (d.x < xMin) xMin = d.x
    if (d.x > xMax) xMax = d.x
    if (d.y < yMin) yMin = d.y
    if (d.y > yMax) yMax = d.y
  })

  const totalWidth = xMax - xMin + NODE_WIDTH + 80
  const totalHeight = yMax - yMin + NODE_HEIGHT + 80

  svg.attr('viewBox', `${xMin - NODE_WIDTH / 2 - 30} ${yMin - 30} ${totalWidth} ${totalHeight}`)
    .attr('preserveAspectRatio', 'xMidYMin meet')

  const g = svg.append('g')

  // Links
  g.append('g')
    .attr('fill', 'none')
    .attr('stroke', '#3a3a3a')
    .attr('stroke-width', 1.5)
    .selectAll('path')
    .data(root.links())
    .join('path')
    .attr('d', d => {
      const sourceX = d.source.x
      const sourceY = d.source.y + NODE_HEIGHT / 2
      const targetX = d.target.x
      const targetY = d.target.y - NODE_HEIGHT / 2
      const midY = (sourceY + targetY) / 2
      return `M ${sourceX} ${sourceY} C ${sourceX} ${midY}, ${targetX} ${midY}, ${targetX} ${targetY}`
    })

  // Nodes
  const node = g.append('g')
    .selectAll('g')
    .data(root.descendants())
    .join('g')
    .attr('class', 'node-group')
    .attr('transform', d => `translate(${d.x - NODE_WIDTH / 2}, ${d.y - NODE_HEIGHT / 2})`)
    .style('cursor', 'pointer')
    .on('click', (event, d) => {
      selectedNode.value = d.data
    })

  node.append('rect')
    .attr('width', NODE_WIDTH)
    .attr('height', NODE_HEIGHT)
    .attr('rx', 6)
    .attr('fill', '#161616')
    .attr('stroke', d => TYPE_COLORS[d.data.type] || TYPE_COLORS.free)
    .attr('stroke-width', 1.5)

  // Type icon
  node.append('text')
    .attr('x', 12)
    .attr('y', 22)
    .attr('font-size', 14)
    .attr('fill', '#ddd')
    .text(d => typeIcon(d.data.type))

  // Question (truncated)
  node.append('text')
    .attr('x', 32)
    .attr('y', 22)
    .attr('font-size', 12)
    .attr('font-weight', 600)
    .attr('fill', '#eee')
    .text(d => truncate(d.data.question || '', 30))

  // Essence (truncated, multi-line via tspan)
  const essenceText = node.append('text')
    .attr('x', 12)
    .attr('y', 50)
    .attr('font-size', 11)
    .attr('fill', '#bbb')

  essenceText.each(function(d) {
    const essence = extractEssence(d.data.summary)
    const lines = wrapText(truncate(essence, 200), 38)
    const sel = d3.select(this)
    lines.slice(0, 3).forEach((line, i) => {
      sel.append('tspan')
        .attr('x', 12)
        .attr('dy', i === 0 ? 0 : 13)
        .text(line)
    })
    if (!essence) {
      sel.append('tspan')
        .attr('x', 12)
        .attr('dy', 0)
        .attr('font-style', 'italic')
        .attr('fill', '#666')
        .text('(not yet synthesised)')
    }
  })

  // Stats footer
  node.append('text')
    .attr('x', 12)
    .attr('y', NODE_HEIGHT - 12)
    .attr('font-size', 10)
    .attr('fill', '#888')
    .text(d => {
      const fetched = fetchedEvidenceCount(d.data)
      const total = d.data.evidence?.length || 0
      const childCount = d.data.children?.length || 0
      const parts = []
      if (total > 0) parts.push(`${fetched}/${total} sources`)
      if (childCount > 0) parts.push(`${childCount} children`)
      return parts.join(' · ')
    })

  // Selected highlight
  watch(selectedNode, (sel) => {
    node.select('rect')
      .attr('stroke-width', d => d.data === sel ? 3 : 1.5)
      .attr('fill', d => d.data === sel ? '#1a1a1a' : '#161616')
  })
}

function wrapText(text, maxLineChars) {
  if (!text) return []
  const words = text.split(/\s+/)
  const lines = []
  let current = ''
  for (const word of words) {
    if ((current + ' ' + word).trim().length <= maxLineChars) {
      current = (current + ' ' + word).trim()
    } else {
      if (current) lines.push(current)
      current = word
    }
  }
  if (current) lines.push(current)
  return lines
}

onMounted(loadTree)

// Re-draw on tree changes (e.g., if user comes back after running synthesis)
watch(tree, async () => {
  await nextTick()
  drawTree()
})
</script>

<style scoped>
.map-layout {
  min-height: 100vh;
  background: #0a0a0a;
  color: #ddd;
  font-family: system-ui, sans-serif;
  display: flex;
  flex-direction: column;
}
.map-topbar {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.75rem 1.25rem;
  border-bottom: 1px solid #222;
}
.back-btn {
  background: transparent;
  border: 1px solid #333;
  color: #ddd;
  padding: 0.35rem 0.7rem;
  border-radius: 4px;
  cursor: pointer;
  font-family: inherit;
  font-size: 0.85rem;
}
.back-btn:hover { background: #1a1a1a; }
.brand { font-weight: bold; letter-spacing: 0.15em; }
.topic { color: #aaa; font-size: 0.9rem; flex: 1; }
.error { color: #f87171; padding: 0.5rem 1.25rem; }
.loading { color: #aaa; font-style: italic; padding: 0.5rem 1.25rem; }

.map-canvas-wrap {
  flex: 1;
  overflow: auto;
  padding: 2rem;
  min-height: 600px;
}
.map-svg {
  display: block;
  margin: 0 auto;
  min-width: 100%;
}

.detail-pane {
  position: fixed;
  right: 0;
  top: 0;
  bottom: 0;
  width: min(480px, 90vw);
  background: #111;
  border-left: 1px solid #2a2a2a;
  padding: 0;
  overflow-y: auto;
  box-shadow: -4px 0 16px rgba(0, 0, 0, 0.5);
}
.detail-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid #2a2a2a;
}
.detail-header .badge { font-size: 1.2rem; }
.detail-header h3 {
  flex: 1;
  margin: 0;
  font-size: 0.95rem;
  font-weight: 500;
}
.detail-header .close {
  background: transparent;
  color: #888;
  border: 0;
  font-size: 1.5rem;
  cursor: pointer;
  line-height: 1;
}

.detail-pane .summary {
  padding: 1rem;
  font-size: 0.85rem;
  line-height: 1.55;
  color: #e0e8f0;
}
.detail-pane .summary :deep(p) { margin: 0.5em 0; }
.detail-pane .summary :deep(a) { color: #80b4ff; }
.detail-pane .muted {
  padding: 1rem;
  color: #666;
  font-style: italic;
  font-size: 0.85rem;
}
.evidence-block {
  padding: 0.5rem 1rem 1rem;
  border-top: 1px solid #2a2a2a;
}
.evidence-block h4 {
  margin: 0.5rem 0;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #aaa;
}
.evidence-block ul {
  list-style: none;
  padding: 0;
  margin: 0;
  font-size: 0.8rem;
}
.evidence-block li {
  margin: 0.4rem 0;
  padding-left: 0.5rem;
  border-left: 2px solid #2a2a2a;
}
.evidence-block a { color: #80b4ff; text-decoration: none; }
.evidence-block a:hover { text-decoration: underline; }
.evidence-block .err {
  margin-left: 0.5rem;
  color: #f87171;
  font-size: 0.7rem;
}
</style>
