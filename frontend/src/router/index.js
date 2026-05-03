import { createRouter, createWebHistory } from 'vue-router'

const SeedChat = () => import('../views/SeedChat.vue')
const HomeLegacy = () => import('../views/HomeLegacy.vue')
const Process = () => import('../views/MainView.vue')
const SimulationView = () => import('../views/SimulationView.vue')
const SimulationRunView = () => import('../views/SimulationRunView.vue')
const ReportView = () => import('../views/ReportView.vue')
const InteractionView = () => import('../views/InteractionView.vue')
const DecisionLabView = () => import('../views/DecisionLabView.vue')
const DecisionTreeView = () => import('../views/DecisionTreeView.vue')
const DecisionTreeMapView = () => import('../views/DecisionTreeMapView.vue')

const routes = [
  { path: '/', name: 'SeedChat', component: SeedChat },
  { path: '/legacy', name: 'HomeLegacy', component: HomeLegacy },
  {
    path: '/decision-lab/:labId?',
    name: 'DecisionLab',
    component: DecisionLabView,
    props: true,
  },
  {
    path: '/process/:projectId',
    name: 'Process',
    component: Process,
    props: true,
  },
  {
    path: '/simulation/:simulationId',
    name: 'Simulation',
    component: SimulationView,
    props: true,
  },
  {
    path: '/simulation/:simulationId/start',
    name: 'SimulationRun',
    component: SimulationRunView,
    props: true,
  },
  {
    path: '/report/:reportId',
    name: 'Report',
    component: ReportView,
    props: true,
  },
  {
    path: '/interaction/:reportId',
    name: 'Interaction',
    component: InteractionView,
    props: true,
  },
  {
    path: '/decision-tree/:sessionId',
    name: 'DecisionTree',
    component: DecisionTreeView,
    props: true,
  },
  {
    path: '/tree-map/:sessionId',
    name: 'DecisionTreeMap',
    component: DecisionTreeMapView,
    props: true,
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
