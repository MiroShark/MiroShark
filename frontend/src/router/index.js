import { createRouter, createWebHistory } from 'vue-router'
import SeedChat from '../views/SeedChat.vue'
import HomeLegacy from '../views/HomeLegacy.vue'
import Process from '../views/MainView.vue'
import SimulationView from '../views/SimulationView.vue'
import SimulationRunView from '../views/SimulationRunView.vue'
import ReportView from '../views/ReportView.vue'
import InteractionView from '../views/InteractionView.vue'
import DecisionLabView from '../views/DecisionLabView.vue'
import DecisionTreeView from '../views/DecisionTreeView.vue'

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
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
