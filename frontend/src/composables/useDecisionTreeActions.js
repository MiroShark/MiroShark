import { ref } from 'vue'
import { getSession } from '../api/seedChat.js'
import {
  postTreeExpand,
  postTreeResearch,
  postTreeUpdateNode,
  postTreeSynthesize,
  postTreeScore,
  postTreeAugmentBigPicture,
  postTreeAugmentStoryDepth,
} from '../api/decisionTree.js'

export function useDecisionTreeActions({ sessionId, tree, error, statusMessage, busyMap, clearInfographicArtifacts }) {
  const researchingAll = ref(false)
  const stopRequested = ref(false)
  const researchProgress = ref({ current: 0, total: 0, label: '' })

  const synthesizingAll = ref(false)
  const synthStopRequested = ref(false)
  const synthProgress = ref({ current: 0, total: 0, label: '' })

  const scoringAll = ref(false)
  const scoreStopRequested = ref(false)
  const scoreProgress = ref({ current: 0, total: 0, label: '' })

  const augmentingBigPicture = ref(false)
  const augmentingStoryDepth = ref(false)
  const autoGrowing = ref(false)
  const autoGrowStopRequested = ref(false)
  const autoGrowProgress = ref({ phase: '', current: 0, total: 0, label: '' })

  function setBusy(nodeId, action, value) {
    if (!busyMap[nodeId]) busyMap[nodeId] = {}
    busyMap[nodeId][action] = value
  }

  function flattenBfs(root) {
    const out = []
    const queue = [root]
    while (queue.length > 0) {
      const node = queue.shift()
      out.push(node)
      for (const child of node.children || []) {
        queue.push(child)
      }
    }
    return out
  }

  async function refreshTree() {
    const session = await getSession(sessionId)
    if (session?.tree) tree.value = session.tree
  }

  async function onExpand(nodeId) {
    setBusy(nodeId, 'expand', true)
    error.value = ''
    try {
      const data = await postTreeExpand({ session_id: sessionId, node_id: nodeId })
      if (data?.tree) tree.value = data.tree
    } catch (err) {
      error.value = err?.response?.data?.error || err.message
    } finally {
      setBusy(nodeId, 'expand', false)
    }
  }

  async function onResearch(nodeId) {
    setBusy(nodeId, 'research', true)
    error.value = ''
    try {
      await postTreeResearch({ session_id: sessionId, node_id: nodeId })
      await refreshTree()
    } catch (err) {
      error.value = err?.response?.data?.error || err.message
    } finally {
      setBusy(nodeId, 'research', false)
    }
  }

  async function researchAll() {
    if (!tree.value || researchingAll.value) return
    const nodes = flattenBfs(tree.value).filter(n => !(n.evidence?.length > 0))
    if (nodes.length === 0) {
      error.value = 'All nodes already have evidence. Click Research on a single node to refresh.'
      return
    }
    researchingAll.value = true
    stopRequested.value = false
    error.value = ''
    researchProgress.value = { current: 0, total: nodes.length, label: '' }
    for (let i = 0; i < nodes.length; i++) {
      if (stopRequested.value) break
      const node = nodes[i]
      researchProgress.value = { current: i + 1, total: nodes.length, label: node.question }
      setBusy(node.id, 'research', true)
      try {
        await postTreeResearch({ session_id: sessionId, node_id: node.id })
        await refreshTree()
      } catch (err) {
        const msg = err?.response?.data?.error || err.message
        error.value = `Node ${i + 1} failed: ${msg}. Continuing.`
      } finally {
        setBusy(node.id, 'research', false)
      }
    }
    researchingAll.value = false
    researchProgress.value = { current: 0, total: 0, label: '' }
  }

  function stopResearchAll() {
    stopRequested.value = true
  }

  async function onSynthesize(nodeId) {
    setBusy(nodeId, 'synthesize', true)
    error.value = ''
    try {
      await postTreeSynthesize({ session_id: sessionId, node_id: nodeId })
      await refreshTree()
    } catch (err) {
      error.value = err?.response?.data?.error || err.message
    } finally {
      setBusy(nodeId, 'synthesize', false)
    }
  }

  async function synthesizeAll() {
    if (!tree.value || synthesizingAll.value) return
    const nodes = flattenBfs(tree.value).filter(n => (n.evidence?.length > 0) && !n.summary)
    if (nodes.length === 0) {
      error.value = 'Nothing to synthesize. Run Research first or all nodes already summarized.'
      return
    }
    synthesizingAll.value = true
    synthStopRequested.value = false
    error.value = ''
    synthProgress.value = { current: 0, total: nodes.length, label: '' }
    for (let i = 0; i < nodes.length; i++) {
      if (synthStopRequested.value) break
      const node = nodes[i]
      synthProgress.value = { current: i + 1, total: nodes.length, label: node.question }
      setBusy(node.id, 'synthesize', true)
      try {
        await postTreeSynthesize({ session_id: sessionId, node_id: node.id })
        await refreshTree()
      } catch (err) {
        const msg = err?.response?.data?.error || err.message
        error.value = `Node ${i + 1} failed: ${msg}. Continuing.`
      } finally {
        setBusy(node.id, 'synthesize', false)
      }
    }
    synthesizingAll.value = false
    synthProgress.value = { current: 0, total: 0, label: '' }
  }

  function stopSynthesizeAll() {
    synthStopRequested.value = true
  }

  async function onScore(nodeId) {
    setBusy(nodeId, 'score', true)
    error.value = ''
    try {
      await postTreeScore({ session_id: sessionId, node_id: nodeId })
      await refreshTree()
    } catch (err) {
      error.value = err?.response?.data?.error || err.message
    } finally {
      setBusy(nodeId, 'score', false)
    }
  }

  async function scoreAll() {
    if (!tree.value || scoringAll.value) return
    const nodes = flattenBfs(tree.value).filter(n => (n.evidence?.length > 0 || (n.summary && n.summary.trim())))
    if (nodes.length === 0) {
      error.value = 'Nothing to score yet — run Research and Synthesize first.'
      return
    }
    scoringAll.value = true
    scoreStopRequested.value = false
    error.value = ''
    scoreProgress.value = { current: 0, total: nodes.length, label: '' }
    for (let i = 0; i < nodes.length; i++) {
      if (scoreStopRequested.value) break
      const node = nodes[i]
      scoreProgress.value = { current: i + 1, total: nodes.length, label: node.question }
      setBusy(node.id, 'score', true)
      try {
        await postTreeScore({ session_id: sessionId, node_id: node.id })
        await refreshTree()
      } catch (err) {
        const msg = err?.response?.data?.error || err.message
        error.value = `Node ${i + 1} failed: ${msg}. Continuing.`
      } finally {
        setBusy(node.id, 'score', false)
      }
    }
    scoringAll.value = false
    scoreProgress.value = { current: 0, total: 0, label: '' }
  }

  function stopScoreAll() {
    scoreStopRequested.value = true
  }

  async function augmentStoryDepth() {
    if (!tree.value || augmentingStoryDepth.value) return
    augmentingStoryDepth.value = true
    error.value = ''
    try {
      const data = await postTreeAugmentStoryDepth({ session_id: sessionId })
      if (data?.tree) tree.value = data.tree
      clearInfographicArtifacts()
      if (data?.added === 0) {
        statusMessage.value = 'Story-depth nodes are already present. Next step: research/synthesize those nodes, then regenerate the infographic timeline.'
      } else {
        statusMessage.value = `Added ${data.added} story-depth nodes. Regenerate the infographic timeline after research/synthesis.`
      }
    } catch (err) {
      error.value = err?.response?.data?.error || err.message
    } finally {
      augmentingStoryDepth.value = false
    }
  }

  async function augmentBigPicture() {
    if (!tree.value || augmentingBigPicture.value) return
    augmentingBigPicture.value = true
    error.value = ''
    try {
      const data = await postTreeAugmentBigPicture({ session_id: sessionId })
      if (data?.tree) tree.value = data.tree
      clearInfographicArtifacts()
      if (data?.added === 0) error.value = 'Big-picture story nodes are already present.'
    } catch (err) {
      error.value = err?.response?.data?.error || err.message
    } finally {
      augmentingBigPicture.value = false
    }
  }

  async function autoGrowAndAnalyse() {
    if (!tree.value || autoGrowing.value) return
    autoGrowing.value = true
    autoGrowStopRequested.value = false
    error.value = ''
    try {
      const roots = (tree.value.children || []).filter(n => !(n.children?.length > 0))
      autoGrowProgress.value = { phase: 'expanding', current: 0, total: roots.length, label: '' }
      for (let i = 0; i < roots.length; i++) {
        if (autoGrowStopRequested.value) break
        const node = roots[i]
        autoGrowProgress.value = { phase: 'expanding', current: i + 1, total: roots.length, label: node.question }
        setBusy(node.id, 'expand', true)
        try {
          await postTreeExpand({ session_id: sessionId, node_id: node.id })
          await refreshTree()
        } catch (err) {
          const msg = err?.response?.data?.error || err.message
          error.value = `Expand ${i + 1} failed: ${msg}. Continuing.`
        } finally {
          setBusy(node.id, 'expand', false)
        }
      }
      if (autoGrowStopRequested.value) return

      const researchTargets = flattenBfs(tree.value).filter(n => !(n.evidence?.length > 0))
      autoGrowProgress.value = { phase: 'researching', current: 0, total: researchTargets.length, label: '' }
      for (let i = 0; i < researchTargets.length; i++) {
        if (autoGrowStopRequested.value) break
        const node = researchTargets[i]
        autoGrowProgress.value = { phase: 'researching', current: i + 1, total: researchTargets.length, label: node.question }
        setBusy(node.id, 'research', true)
        try {
          await postTreeResearch({ session_id: sessionId, node_id: node.id })
          await refreshTree()
        } catch (err) {
          const msg = err?.response?.data?.error || err.message
          error.value = `Research ${i + 1} failed: ${msg}. Continuing.`
        } finally {
          setBusy(node.id, 'research', false)
        }
      }
      if (autoGrowStopRequested.value) return

      const synthTargets = flattenBfs(tree.value).filter(n => (n.evidence?.length > 0) && !n.summary)
      autoGrowProgress.value = { phase: 'synthesising', current: 0, total: synthTargets.length, label: '' }
      for (let i = 0; i < synthTargets.length; i++) {
        if (autoGrowStopRequested.value) break
        const node = synthTargets[i]
        autoGrowProgress.value = { phase: 'synthesising', current: i + 1, total: synthTargets.length, label: node.question }
        setBusy(node.id, 'synthesize', true)
        try {
          await postTreeSynthesize({ session_id: sessionId, node_id: node.id })
          await refreshTree()
        } catch (err) {
          const msg = err?.response?.data?.error || err.message
          error.value = `Synthesise ${i + 1} failed: ${msg}. Continuing.`
        } finally {
          setBusy(node.id, 'synthesize', false)
        }
      }
      if (autoGrowStopRequested.value) return

      const scoreTargets = flattenBfs(tree.value).filter(n => (n.evidence?.length > 0 || (n.summary && n.summary.trim())))
      autoGrowProgress.value = { phase: 'scoring', current: 0, total: scoreTargets.length, label: '' }
      for (let i = 0; i < scoreTargets.length; i++) {
        if (autoGrowStopRequested.value) break
        const node = scoreTargets[i]
        autoGrowProgress.value = { phase: 'scoring', current: i + 1, total: scoreTargets.length, label: node.question }
        setBusy(node.id, 'score', true)
        try {
          await postTreeScore({ session_id: sessionId, node_id: node.id })
          await refreshTree()
        } catch (err) {
          const msg = err?.response?.data?.error || err.message
          error.value = `Score ${i + 1} failed: ${msg}. Continuing.`
        } finally {
          setBusy(node.id, 'score', false)
        }
      }
    } finally {
      autoGrowing.value = false
      autoGrowProgress.value = { phase: '', current: 0, total: 0, label: '' }
    }
  }

  function stopAutoGrow() {
    autoGrowStopRequested.value = true
  }

  async function onUpdateNode({ node_id, fields }) {
    try {
      const data = await postTreeUpdateNode({ session_id: sessionId, node_id, fields })
      if (data?.tree) tree.value = data.tree
    } catch (err) {
      error.value = err?.response?.data?.error || err.message
    }
  }

  return {
    researchingAll,
    stopRequested,
    researchProgress,
    synthesizingAll,
    synthStopRequested,
    synthProgress,
    scoringAll,
    scoreStopRequested,
    scoreProgress,
    augmentingBigPicture,
    augmentingStoryDepth,
    autoGrowing,
    autoGrowStopRequested,
    autoGrowProgress,
    onExpand,
    onResearch,
    researchAll,
    stopResearchAll,
    onSynthesize,
    synthesizeAll,
    stopSynthesizeAll,
    onScore,
    scoreAll,
    stopScoreAll,
    augmentStoryDepth,
    augmentBigPicture,
    autoGrowAndAnalyse,
    stopAutoGrow,
    onUpdateNode,
  }
}
