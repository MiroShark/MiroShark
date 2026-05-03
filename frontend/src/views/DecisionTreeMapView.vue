<template>
  <div class="map-layout">
    <header class="map-topbar">
      <button class="back-btn" type="button" @click="goBack">← List view 📋</button>
      <div class="brand">DECISION MAP</div>
      <div class="topic">{{ tree?.question || 'Loading…' }}</div>
      <button class="back-btn" type="button" :disabled="!tree" @click="expandAll">Show all topics</button>
      <button class="back-btn" type="button" :disabled="!tree" @click="collapseToBranches">Viewpoints only</button>
      <button class="back-btn" type="button" :disabled="!tree" @click="resetView">Fit view</button>
      <button class="back-btn" type="button" @click="goChat">Back to chat</button>
    </header>

    <div class="map-help" v-if="tree">
      <span>Learning map: each viewpoint opens into plain-English topics, pros/cons, evidence checks, and examples.</span>
      <span>Drag to pan · scroll/pinch to zoom · click cards for detail · click node circles to collapse/expand.</span>
      <span class="legend-item upstream"><i></i>Context</span>
      <span class="legend-item downstream"><i></i>Downstream</span>
      <span class="legend-item analogy"><i></i>Analogy</span>
      <span class="legend-item central"><i></i>Central</span>
    </div>

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

      <div v-if="selectedNode.scores" class="score-grid">
        <div><span>Confidence</span><strong :style="{ color: confColor(selectedNode.scores.confidence) }">{{ selectedNode.scores.confidence }}</strong></div>
        <div><span>Contestedness</span><strong :style="{ color: contColor(selectedNode.scores.contestedness) }">{{ selectedNode.scores.contestedness }}</strong></div>
        <div><span>Salience</span><strong :style="{ color: salColor(selectedNode.scores.salience) }">{{ selectedNode.scores.salience }}</strong></div>
      </div>

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
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
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
const collapsedIds = ref(new Set())
let zoomBehaviour = null
let zoomRoot = null
let lastFitTransform = d3.zoomIdentity
let resizeObserver = null

const NODE_WIDTH = 238
const NODE_HEIGHT = 94
const TYPE_COLORS = {
  central: '#4ade80',
  upstream: '#60a5fa',
  downstream: '#f59e0b',
  analogy: '#c084fc',
  free: '#9ca3af',
}
const TYPE_TINTS = {
  central: '#0d2719',
  upstream: '#0d1c2f',
  downstream: '#2d210b',
  analogy: '#251535',
  free: '#181818',
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

function nodeId(node, fallback = '') {
  return node?.id || node?.node_id || node?.question || node?.label || fallback
}

function originalNode(node) {
  return node?.original || node
}

function displayType(node) {
  return node?.type || node?.original?.type || 'free'
}

function displayLabel(node) {
  return node?.label || node?.question || node?.original?.question || ''
}

function displayHeadline(node) {
  if (node?.displayKind === 'group') return node.summary || `${node.topicCount || 0} learning topics`
  const original = originalNode(node)
  return original?.scores?.stance_summary?.trim() || extractEssence(original?.summary)
}

function displayIcon(node) {
  if (node?.displayKind === 'group') return '📚'
  if (node?.displayKind === 'topic') return '•'
  return typeIcon(displayType(node))
}

function selectDisplayNode(node) {
  const original = originalNode(node)
  if (node?.displayKind === 'group') {
    selectedNode.value = {
      type: node.type,
      question: node.label,
      summary: node.summary,
      evidence: [],
      children: node.children || [],
    }
  } else {
    selectedNode.value = original
  }
}

function renderSummary(md) {
  return marked.parse(md || '')
}

function confColor(v) {
  if (v === 'high') return '#4ade80'
  if (v === 'medium') return '#facc15'
  return '#94a3b8'
}
function contColor(v) {
  if (v === 'settled') return '#4ade80'
  if (v === 'disputed') return '#f87171'
  return '#facc15'
}
function salColor(v) {
  if (v === 'high') return '#f59e0b'
  if (v === 'niche') return '#6b7280'
  return '#94a3b8'
}

function goBack() {
  router.push({ name: 'DecisionTree', params: { sessionId } })
}

function goChat() {
  router.push({ name: 'SeedChat', query: { session: sessionId } })
}

function visibleChildren(d) {
  const id = nodeId(d)
  if (collapsedIds.value.has(id)) return null
  return d.children || []
}

function hasChildren(d) {
  return (d?.children || []).length > 0
}

function toggleCollapsed(d) {
  if (!hasChildren(d.data)) return
  const next = new Set(collapsedIds.value)
  const id = nodeId(d.data, d.data.question)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  collapsedIds.value = next
  drawTree(false)
}

function expandAll() {
  collapsedIds.value = new Set()
  drawTree(true)
}

function collapseToBranches() {
  if (!tree.value) return
  const displayTree = buildEducationTree(tree.value)
  const next = new Set()
  walkTree(displayTree, (node, depth) => {
    if (depth >= 1 && hasChildren(node)) next.add(nodeId(node))
  })
  collapsedIds.value = next
  drawTree(true)
}

function walkTree(node, fn, depth = 0) {
  if (!node) return
  fn(node, depth)
  for (const child of node.children || []) walkTree(child, fn, depth + 1)
}


function buildEducationTree(source) {
  const root = {
    ...source,
    displayKind: 'issue',
    label: 'Core question',
    original: source,
  }
  root.children = (source.children || []).map((branch, idx) => buildViewpointNode(branch, idx))
  return root
}

function buildViewpointNode(branch, idx) {
  const groups = bucketLearningTopics(branch)
  return {
    ...branch,
    id: `viewpoint-${nodeId(branch, idx)}`,
    displayKind: 'viewpoint',
    label: viewpointTitle(branch),
    original: branch,
    children: groups,
  }
}

function bucketLearningTopics(branch) {
  const labels = groupLabelsFor(branch)
  const buckets = {
    pro: { key: 'pro', label: labels.pro, type: 'central', children: [] },
    con: { key: 'con', label: labels.con, type: 'downstream', children: [] },
    evidence: { key: 'evidence', label: 'Evidence to check', type: 'free', children: [] },
    example: { key: 'example', label: 'Examples & precedents', type: 'analogy', children: [] },
    affected: { key: 'affected', label: 'Who is affected', type: 'upstream', children: [] },
  }

  for (const child of branch.children || []) {
    const key = topicBucket(child, branch)
    buckets[key].children.push({
      ...child,
      id: `topic-${nodeId(branch)}-${nodeId(child)}`,
      displayKind: 'topic',
      label: educationTopicTitle(child),
      original: child,
      children: [],
    })
  }

  return Object.values(buckets)
    .filter(group => group.children.length > 0)
    .map(group => ({
      id: `group-${nodeId(branch)}-${group.key}`,
      displayKind: 'group',
      type: group.type,
      label: group.label,
      question: group.label,
      summary: `${group.children.length} topic${group.children.length === 1 ? '' : 's'} to learn so the user can explain this viewpoint in plain English.`,
      topicCount: group.children.length,
      original: branch,
      children: group.children,
    }))
}

function groupLabelsFor(branch) {
  const q = (branch.question || '').toLowerCase()
  if (q.includes('no tax')) return { pro: 'Case for no tax', con: 'Risks of no tax' }
  if (q.includes('lower rate') || q.includes('reduced')) return { pro: 'Why compromise appeals', con: 'Trade-offs & objections' }
  if (q.includes('25%') || q.includes('windfall tax')) return { pro: 'Case for this option', con: 'Risks & objections' }
  if (q.includes('broader framing')) return { pro: 'Principles behind the debate', con: 'Trade-offs to weigh' }
  if (q.includes('where has') || q.includes('elsewhere')) return { pro: 'What worked elsewhere', con: 'What backfired elsewhere' }
  if (q.includes('claim accurate')) return { pro: 'Evidence supporting claim', con: 'Evidence against claim' }
  return { pro: 'Arguments for', con: 'Arguments against' }
}

function topicBucket(topic, branch) {
  const q = `${topic.question || ''} ${topic.summary || ''} ${topic.scores?.stance_summary || ''}`.toLowerCase()
  if (/norway|uk |united kingdom|italy|spain|elsewhere|precedent|historical|comparable|rsp[st]|mrrt|prrt/.test(q)) return 'example'
  if (/household|manufacturer|company|woodside|santos|chevron|shell|electorate|citizen|future generation|trading partner|producer|who |whose /.test(q)) return 'affected'
  if (/evidence|accurate|projected|quantif|how much|polling|operational|proportion|rating|bond|analyst|what constitutes|definition/.test(q)) return 'evidence'
  if (/risk|credit|flight|flee|deter|deferral|capex|investment certainty|sovereign|price|bill|forgo|political consequences|retrospective|objection/.test(q)) return branch.question?.toLowerCase().includes('no tax') ? 'pro' : 'con'
  if (/revenue|fund|relief|public|fair|rent|redistribution|benefit|legitimate|role of the state|national interest/.test(q)) return branch.question?.toLowerCase().includes('no tax') ? 'con' : 'pro'
  return 'evidence'
}

function viewpointTitle(node) {
  const q = node.question || ''
  return q.replace(/^Is this claim accurate:\s*/i, 'Test claim: ').replace(/\?$/, '')
}

function educationTopicTitle(node) {
  const q = node.question || ''
  return q
    .replace(/^What is the /i, '')
    .replace(/^What are the /i, '')
    .replace(/^What /i, '')
    .replace(/^How /i, 'How ')
    .replace(/^Does /i, 'Whether ')
    .replace(/^Would /i, 'Whether ')
    .replace(/^Under what /i, 'When ')
}

function resetView() {
  if (!svgEl.value || !zoomBehaviour) return
  d3.select(svgEl.value).transition().duration(350).call(zoomBehaviour.transform, lastFitTransform)
}

async function loadTree() {
  loading.value = true
  error.value = ''
  try {
    const session = await getSession(sessionId)
    if (session?.tree) {
      tree.value = session.tree
      selectedNode.value = session.tree
      await nextTick()
      expandAll()
    } else {
      error.value = 'No tree on this session yet. Open list view first to initialise it.'
    }
  } catch (err) {
    error.value = err?.response?.data?.error || err.message
  } finally {
    loading.value = false
  }
}

function drawTree(fit = false) {
  if (!svgEl.value || !tree.value) return

  const priorTransform = d3.zoomTransform(svgEl.value)
  const container = svgEl.value.parentElement
  const width = container.clientWidth || 1200
  const height = container.clientHeight || 800

  const svg = d3.select(svgEl.value)
    .attr('width', width)
    .attr('height', height)
    .attr('viewBox', `0 0 ${width} ${height}`)
    .attr('preserveAspectRatio', 'xMidYMid meet')
  svg.selectAll('*').remove()

  const defs = svg.append('defs')
  defs.append('pattern')
    .attr('id', 'blueprint-grid')
    .attr('width', 28)
    .attr('height', 28)
    .attr('patternUnits', 'userSpaceOnUse')
    .append('path')
    .attr('d', 'M 28 0 L 0 0 0 28')
    .attr('fill', 'none')
    .attr('stroke', '#1a2730')
    .attr('stroke-width', 0.7)

  svg.append('rect')
    .attr('width', width)
    .attr('height', height)
    .attr('fill', 'url(#blueprint-grid)')
    .attr('opacity', 0.45)

  zoomRoot = svg.append('g').attr('class', 'zoom-root')

  zoomBehaviour = d3.zoom()
    .scaleExtent([0.06, 8])
    .on('zoom', (event) => {
      zoomRoot.attr('transform', event.transform)
    })

  svg.call(zoomBehaviour).on('dblclick.zoom', null)

  const root = d3.hierarchy(buildEducationTree(tree.value), visibleChildren)
  const treeLayout = d3.tree()
    .nodeSize([NODE_HEIGHT + 74, NODE_WIDTH + 170])
    .separation((a, b) => a.parent === b.parent ? 1 : 1.55)
  treeLayout(root)

  const nodes = root.descendants()
  const links = root.links()
  const ext = getLayoutExtents(nodes)
  const boardX = ext.xMin - NODE_WIDTH / 2 - 90
  const boardY = ext.yMin - NODE_HEIGHT / 2 - 90
  const boardW = ext.xMax - ext.xMin + NODE_WIDTH + 180
  const boardH = ext.yMax - ext.yMin + NODE_HEIGHT + 180

  zoomRoot.append('rect')
    .attr('x', boardX)
    .attr('y', boardY)
    .attr('width', boardW)
    .attr('height', boardH)
    .attr('rx', 18)
    .attr('fill', '#0b1014')
    .attr('stroke', '#22313a')
    .attr('stroke-width', 1)
    .attr('opacity', 0.86)

  drawDepthLanes(zoomRoot, nodes, ext)
  drawLinks(zoomRoot, links)
  drawNodes(zoomRoot, nodes)

  lastFitTransform = fitTransform(width, height, boardX, boardY, boardW, boardH)
  svg.call(zoomBehaviour.transform, fit ? lastFitTransform : priorTransform)
}

function getLayoutExtents(nodes) {
  let xMin = Infinity, xMax = -Infinity, yMin = Infinity, yMax = -Infinity
  nodes.forEach(d => {
    const rx = d.y
    const ry = d.x
    xMin = Math.min(xMin, rx)
    xMax = Math.max(xMax, rx)
    yMin = Math.min(yMin, ry)
    yMax = Math.max(yMax, ry)
  })
  return { xMin, xMax, yMin, yMax }
}

function fitTransform(width, height, x, y, w, h) {
  const scale = Math.max(0.06, Math.min(2.2, 0.9 / Math.max(w / width, h / height)))
  const tx = (width - w * scale) / 2 - x * scale
  const ty = (height - h * scale) / 2 - y * scale
  return d3.zoomIdentity.translate(tx, ty).scale(scale)
}

function drawDepthLanes(g, nodes, ext) {
  const depths = Array.from(new Set(nodes.map(d => d.depth))).sort((a, b) => a - b)
  const lane = g.append('g').attr('class', 'lanes')
  depths.forEach(depth => {
    const depthNodes = nodes.filter(n => n.depth === depth)
    const sample = depthNodes[0]
    const x = sample.y - NODE_WIDTH / 2 - 28
    const color = TYPE_COLORS[displayType(sample.data)] || '#3a3a3a'
    lane.append('rect')
      .attr('x', x)
      .attr('y', ext.yMin - NODE_HEIGHT / 2 - 55)
      .attr('width', NODE_WIDTH + 56)
      .attr('height', ext.yMax - ext.yMin + NODE_HEIGHT + 110)
      .attr('rx', 14)
      .attr('fill', color)
      .attr('opacity', 0.045)
      .attr('stroke', color)
      .attr('stroke-width', 0.6)
      .attr('stroke-opacity', 0.22)
    lane.append('text')
      .attr('x', x + 10)
      .attr('y', ext.yMin - NODE_HEIGHT / 2 - 34)
      .attr('fill', '#6f7d86')
      .attr('font-size', 10)
      .attr('letter-spacing', '0.12em')
      .text(depth === 0 ? 'QUESTION' : `LEVEL ${depth}`)
  })
}

function drawLinks(g, links) {
  g.append('g')
    .attr('fill', 'none')
    .selectAll('path')
    .data(links)
    .join('path')
    .attr('d', d => {
      const sourceX = d.source.y + NODE_WIDTH / 2
      const sourceY = d.source.x
      const targetX = d.target.y - NODE_WIDTH / 2
      const targetY = d.target.x
      const midX = (sourceX + targetX) / 2
      return `M ${sourceX} ${sourceY} C ${midX} ${sourceY}, ${midX} ${targetY}, ${targetX} ${targetY}`
    })
    .attr('stroke', d => TYPE_COLORS[d.target.data.type] || '#3a3a3a')
    .attr('stroke-width', 1.6)
    .attr('stroke-opacity', 0.42)
}

function drawNodes(g, nodes) {
  const node = g.append('g')
    .selectAll('g')
    .data(nodes)
    .join('g')
    .attr('class', 'node-group')
    .attr('transform', d => `translate(${d.y - NODE_WIDTH / 2}, ${d.x - NODE_HEIGHT / 2})`)

  node.append('rect')
    .attr('width', NODE_WIDTH)
    .attr('height', NODE_HEIGHT)
    .attr('rx', 10)
    .attr('fill', d => TYPE_TINTS[displayType(d.data)] || TYPE_TINTS.free)
    .attr('stroke', d => TYPE_COLORS[displayType(d.data)] || TYPE_COLORS.free)
    .attr('stroke-width', d => originalNode(d.data) === selectedNode.value ? 3 : 1.5)
    .attr('stroke-dasharray', d => d.data.displayKind === 'group' ? '5 4' : null)
    .attr('filter', 'drop-shadow(0 8px 16px rgba(0,0,0,.28))')
    .style('cursor', 'pointer')
    .on('click', (event, d) => {
      event.stopPropagation()
      selectDisplayNode(d.data)
      updateSelectedStyles()
    })

  node.append('rect')
    .attr('width', 6)
    .attr('height', NODE_HEIGHT)
    .attr('rx', 3)
    .attr('fill', d => TYPE_COLORS[displayType(d.data)] || TYPE_COLORS.free)
    .attr('opacity', 0.95)

  node.append('circle')
    .attr('class', 'collapse-toggle')
    .attr('cx', NODE_WIDTH - 18)
    .attr('cy', 18)
    .attr('r', 10)
    .attr('fill', d => hasChildren(d.data) ? '#0a0a0a' : '#1e1e1e')
    .attr('stroke', d => hasChildren(d.data) ? (TYPE_COLORS[displayType(d.data)] || TYPE_COLORS.free) : '#333')
    .attr('stroke-width', 1.2)
    .style('cursor', d => hasChildren(d.data) ? 'pointer' : 'default')
    .on('click', (event, d) => {
      event.stopPropagation()
      toggleCollapsed(d)
    })

  node.append('text')
    .attr('x', NODE_WIDTH - 18)
    .attr('y', 22)
    .attr('text-anchor', 'middle')
    .attr('font-size', 12)
    .attr('font-weight', 700)
    .attr('fill', '#ddd')
    .style('pointer-events', 'none')
    .text(d => {
      if (!hasChildren(d.data)) return '·'
      return collapsedIds.value.has(nodeId(d.data)) ? '+' : '−'
    })

  node.append('text')
    .attr('x', 16)
    .attr('y', 22)
    .attr('font-size', 14)
    .attr('fill', '#ddd')
    .text(d => displayIcon(d.data))

  node.append('text')
    .attr('x', 36)
    .attr('y', 19)
    .attr('font-size', 11)
    .attr('font-weight', 700)
    .attr('letter-spacing', '0.02em')
    .attr('fill', '#f3f4f6')
    .text(d => truncate(displayLabel(d.data), d.data.displayKind === 'group' ? 30 : 38))

  const headlineText = node.append('text')
    .attr('x', 14)
    .attr('y', 42)
    .attr('font-size', 10.5)
    .attr('fill', '#cbd5e1')

  headlineText.each(function(d) {
    const headline = displayHeadline(d.data)
    const sel = d3.select(this)
    if (!headline) {
      sel.append('tspan')
        .attr('x', 14)
        .attr('dy', 0)
        .attr('font-style', 'italic')
        .attr('fill', '#7b7b7b')
        .text('(not analysed yet)')
      return
    }
    wrapText(truncate(headline, 128), 38).slice(0, 2).forEach((line, i) => {
      sel.append('tspan')
        .attr('x', 14)
        .attr('dy', i === 0 ? 0 : 12)
        .text(line)
    })
  })

  node.each(function(d) {
    const source = originalNode(d.data)
    if (!source?.scores || d.data.displayKind === 'group') return
    const s = source.scores
    const badges = [
      { text: `🎲 ${s.confidence}`, color: confColor(s.confidence) },
      { text: `⚖ ${s.contestedness}`, color: contColor(s.contestedness) },
      { text: `📣 ${s.salience}`, color: salColor(s.salience) },
    ]
    let cursorX = 14
    const sel = d3.select(this)
    for (const b of badges) {
      sel.append('text')
        .attr('x', cursorX)
        .attr('y', NODE_HEIGHT - 22)
        .attr('font-size', 8.5)
        .attr('font-weight', 700)
        .attr('fill', b.color)
        .text(b.text)
      cursorX += b.text.length * 5.1 + 6
    }
  })

  node.append('text')
    .attr('x', 14)
    .attr('y', NODE_HEIGHT - 7)
    .attr('font-size', 8.5)
    .attr('fill', '#94a3b8')
    .text(d => {
      const source = originalNode(d.data)
      const fetched = fetchedEvidenceCount(source)
      const total = source.evidence?.length || 0
      const childCount = d.data.children?.length || 0
      const hidden = collapsedIds.value.has(nodeId(d.data)) && childCount > 0
      const parts = []
      if (total > 0) parts.push(`${fetched}/${total} sources`)
      if (childCount > 0) parts.push(hidden ? `${childCount} hidden branches` : `${childCount} branches`)
      return parts.join(' · ')
    })
}

function updateSelectedStyles() {
  if (!zoomRoot) return
  zoomRoot.selectAll('.node-group rect:first-child')
    .attr('stroke-width', d => originalNode(d?.data) === selectedNode.value ? 3 : 1.5)
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

onMounted(() => {
  loadTree()
  nextTick(() => {
    if (!svgEl.value?.parentElement) return
    resizeObserver = new ResizeObserver(() => drawTree(true))
    resizeObserver.observe(svgEl.value.parentElement)
  })
})

onBeforeUnmount(() => {
  if (resizeObserver) resizeObserver.disconnect()
})

watch(tree, async () => {
  await nextTick()
  drawTree(true)
})
</script>

<style scoped>
.map-layout {
  min-height: 100vh;
  background: #081016;
  color: #ddd;
  font-family: system-ui, sans-serif;
  display: flex;
  flex-direction: column;
}
.map-topbar {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.75rem 1.25rem;
  border-bottom: 1px solid #1f313a;
  background: #0a0d0f;
}
.back-btn {
  background: transparent;
  border: 1px solid #33434c;
  color: #ddd;
  padding: 0.35rem 0.7rem;
  border-radius: 5px;
  cursor: pointer;
  font-family: inherit;
  font-size: 0.82rem;
  white-space: nowrap;
}
.back-btn:hover:not(:disabled) { background: #152129; }
.back-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.brand { font-weight: bold; letter-spacing: 0.15em; white-space: nowrap; }
.topic { color: #aeb8c2; font-size: 0.9rem; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.map-help {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  flex-wrap: wrap;
  padding: 0.45rem 1.25rem;
  color: #83929c;
  font-size: 0.78rem;
  border-bottom: 1px solid #13242d;
  background: #0b141a;
}
.legend-item { display: inline-flex; align-items: center; gap: 0.3rem; }
.legend-item i { display: inline-block; width: 0.75rem; height: 0.75rem; border-radius: 50%; }
.legend-item.upstream i { background: #60a5fa; }
.legend-item.downstream i { background: #f59e0b; }
.legend-item.analogy i { background: #c084fc; }
.legend-item.central i { background: #4ade80; }
.error { color: #f87171; padding: 0.5rem 1.25rem; }
.loading { color: #aaa; font-style: italic; padding: 0.5rem 1.25rem; }

.map-canvas-wrap {
  flex: 1;
  overflow: hidden;
  padding: 0;
  min-height: 640px;
  cursor: grab;
}
.map-canvas-wrap:active { cursor: grabbing; }
.map-svg {
  display: block;
  width: 100%;
  height: 100%;
  user-select: none;
}

.detail-pane {
  position: fixed;
  right: 0;
  top: 0;
  bottom: 0;
  width: min(500px, 90vw);
  background: #0e1418;
  border-left: 1px solid #2a3f49;
  padding: 0;
  overflow-y: auto;
  box-shadow: -4px 0 18px rgba(0, 0, 0, 0.55);
  z-index: 5;
}
.detail-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid #263942;
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
.score-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.5rem;
  padding: 0.75rem 1rem 0;
}
.score-grid div {
  border: 1px solid #24353d;
  border-radius: 8px;
  padding: 0.5rem;
  background: #101b21;
}
.score-grid span {
  display: block;
  color: #83929c;
  font-size: 0.68rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.score-grid strong {
  display: block;
  margin-top: 0.15rem;
  font-size: 0.82rem;
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
  color: #77828a;
  font-style: italic;
  font-size: 0.85rem;
}
.evidence-block {
  padding: 0.5rem 1rem 1rem;
  border-top: 1px solid #263942;
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
  border-left: 2px solid #2a3f49;
}
.evidence-block a { color: #80b4ff; text-decoration: none; }
.evidence-block a:hover { text-decoration: underline; }
.status.err { display: block; color: #f87171; margin-top: 0.2rem; }

@media (max-width: 900px) {
  .map-topbar { flex-wrap: wrap; }
  .topic { flex-basis: 100%; order: 2; }
}
</style>
