<template>
  <div class="consequence-tree">
    <div v-if="loading" class="tree-loading">Extracting causal chains...</div>
    <div v-else-if="!treeData" class="tree-empty">No consequence data available.</div>
    <div v-else class="tree-container">
      <div class="tree-stats">
        <span class="stat">{{ treeData.total_nodes }} events</span>
        <span class="stat unintended" v-if="treeData.unintended_count">
          {{ treeData.unintended_count }} unintended
        </span>
      </div>
      <svg ref="svgRef" :width="svgWidth" :height="svgHeight">
        <g ref="gRef">
          <!-- Links -->
          <path
            v-for="link in links"
            :key="link.id"
            :d="link.path"
            class="tree-link"
            :class="{ unintended: link.targetUnintended }"
          />
          <!-- Nodes -->
          <g
            v-for="node in nodes"
            :key="node.data.event_id"
            :transform="`translate(${node.y},${node.x})`"
            class="tree-node"
            :class="{
              unintended: node.data.is_unintended,
              root: node.data.event_id === 'root',
              collapsed: node._children && node._children.length > 0
            }"
            @click="toggleNode(node)"
          >
            <circle
              :r="nodeRadius(node)"
              :class="node.data.consequence_type"
            />
            <text
              :x="node.children || node._children ? -12 : 12"
              dy="4"
              :text-anchor="node.children || node._children ? 'end' : 'start'"
              class="node-label"
            >
              {{ truncate(node.data.summary || node.data.agent_name, 40) }}
            </text>
            <text
              :x="node.children || node._children ? -12 : 12"
              dy="16"
              :text-anchor="node.children || node._children ? 'end' : 'start'"
              class="node-meta"
            >
              R{{ node.data.round_num }} · {{ node.data.agent_name }}
            </text>
            <!-- Unintended badge -->
            <text
              v-if="node.data.is_unintended"
              :x="nodeRadius(node) + 4"
              dy="-8"
              class="unintended-badge"
            >!</text>
          </g>
        </g>
      </svg>
    </div>

    <!-- Detail panel -->
    <div v-if="selectedNode" class="detail-panel">
      <button class="detail-close" @click="selectedNode = null">&times;</button>
      <div class="detail-type" :class="selectedNode.data.consequence_type">
        {{ selectedNode.data.consequence_type }}
      </div>
      <div class="detail-agent">{{ selectedNode.data.agent_name }}</div>
      <div class="detail-round">Round {{ selectedNode.data.round_num }}</div>
      <div class="detail-summary">{{ selectedNode.data.summary }}</div>
      <div class="detail-content">{{ selectedNode.data.content }}</div>
      <div class="detail-importance">
        Importance: {{ selectedNode.data.importance }}/10
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, nextTick, computed } from 'vue'
import * as d3 from 'd3'

const props = defineProps({
  treeData: { type: Object, default: null },
  loading: { type: Boolean, default: false },
})

const svgRef = ref(null)
const gRef = ref(null)
const svgWidth = ref(900)
const svgHeight = ref(600)
const nodes = ref([])
const links = ref([])
const selectedNode = ref(null)

const nodeRadius = (node) => {
  if (node.data.event_id === 'root') return 8
  return Math.max(4, Math.min(7, node.data.importance / 2))
}

const truncate = (text, max) => {
  if (!text) return ''
  return text.length > max ? text.slice(0, max) + '...' : text
}

const toggleNode = (node) => {
  if (node.children) {
    node._children = node.children
    node.children = null
  } else if (node._children) {
    node.children = node._children
    node._children = null
  } else {
    selectedNode.value = node
    return
  }
  updateLayout()
}

const updateLayout = () => {
  if (!props.treeData?.root) return

  const root = d3.hierarchy(props.treeData.root, d => d.children)
  const nodeCount = root.descendants().length
  const treeHeight = Math.max(400, nodeCount * 28)
  const treeWidth = Math.max(700, root.height * 220 + 200)

  svgHeight.value = treeHeight + 40
  svgWidth.value = treeWidth + 40

  const treeLayout = d3.tree().size([treeHeight, treeWidth - 200])
  treeLayout(root)

  nodes.value = root.descendants()
  links.value = root.links().map((link, idx) => ({
    id: `link-${idx}`,
    path: d3.linkHorizontal()
      .x(d => d.y + 100)
      .y(d => d.x + 20)(link),
    targetUnintended: link.target.data.is_unintended,
  }))

  nodes.value.forEach(n => {
    n.y += 100
    n.x += 20
  })
}

watch(() => props.treeData, () => {
  nextTick(updateLayout)
}, { deep: true })

onMounted(() => {
  if (props.treeData) {
    nextTick(updateLayout)
  }
  if (svgRef.value) {
    const svg = d3.select(svgRef.value)
    const g = d3.select(gRef.value)
    const zoom = d3.zoom()
      .scaleExtent([0.3, 3])
      .on('zoom', (event) => {
        g.attr('transform', event.transform)
      })
    svg.call(zoom)
  }
})
</script>

<style scoped>
.consequence-tree {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
}

.tree-loading, .tree-empty {
  text-align: center;
  padding: 40px;
  color: #999;
  font-size: 13px;
}

.tree-container {
  width: 100%;
  height: 100%;
  overflow: auto;
}

.tree-stats {
  display: flex;
  gap: 12px;
  padding: 8px 16px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  color: #666;
  border-bottom: 1px solid #eaeaea;
}

.stat.unintended {
  color: #c62828;
  font-weight: 600;
}

svg {
  display: block;
}

.tree-link {
  fill: none;
  stroke: #ddd;
  stroke-width: 1.5;
}

.tree-link.unintended {
  stroke: #ef5350;
  stroke-dasharray: 4 2;
}

.tree-node { cursor: pointer; }
.tree-node circle {
  fill: #fff;
  stroke: #999;
  stroke-width: 1.5;
}

.tree-node.root circle { fill: #000; stroke: #000; }
.tree-node circle.direct_reaction { stroke: #1976d2; fill: #e3f2fd; }
.tree-node circle.cascade { stroke: #ff9800; fill: #fff3e0; }
.tree-node circle.counter_reaction { stroke: #7b1fa2; fill: #f3e5f5; }
.tree-node circle.escalation { stroke: #c62828; fill: #ffebee; }
.tree-node circle.unintended { stroke: #c62828; fill: #c62828; }
.tree-node circle.reversal { stroke: #e65100; fill: #fff3e0; }

.tree-node.collapsed circle { stroke-dasharray: 3 2; }

.node-label {
  font-size: 10px;
  font-family: 'Space Grotesk', sans-serif;
  fill: #333;
}

.node-meta {
  font-size: 8px;
  font-family: 'JetBrains Mono', monospace;
  fill: #999;
}

.unintended-badge {
  font-size: 12px;
  font-weight: 900;
  fill: #c62828;
}

.detail-panel {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: #fff;
  border-top: 2px solid #eaeaea;
  padding: 16px 20px;
  max-height: 200px;
  overflow-y: auto;
}

.detail-close {
  position: absolute;
  top: 8px;
  right: 12px;
  background: none;
  border: none;
  font-size: 20px;
  color: #999;
  cursor: pointer;
}

.detail-type {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  padding: 2px 8px;
  border-radius: 3px;
  display: inline-block;
  margin-bottom: 8px;
  background: #f0f0f0;
  color: #666;
}
.detail-type.unintended, .detail-type.escalation { background: #ffebee; color: #c62828; }
.detail-type.direct_reaction { background: #e3f2fd; color: #1565c0; }
.detail-type.cascade { background: #fff3e0; color: #e65100; }
.detail-type.counter_reaction { background: #f3e5f5; color: #6a1b9a; }

.detail-agent { font-weight: 600; font-size: 14px; }
.detail-round { font-size: 11px; color: #999; font-family: 'JetBrains Mono', monospace; }
.detail-summary { font-size: 13px; margin-top: 8px; line-height: 1.5; }
.detail-content { font-size: 11px; color: #666; margin-top: 4px; font-style: italic; }
.detail-importance { font-size: 10px; color: #999; margin-top: 4px; font-family: 'JetBrains Mono', monospace; }
</style>
