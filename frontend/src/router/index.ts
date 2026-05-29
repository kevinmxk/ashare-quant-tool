import { createRouter, createWebHistory } from 'vue-router'
import DiagnosisView from '../views/DiagnosisView.vue'
import RankingsView from '../views/RankingsView.vue'
import WatchlistView from '../views/WatchlistView.vue'
import StatusView from '../views/StatusView.vue'

const routes = [
  { path: '/', redirect: '/diagnosis' },
  { path: '/diagnosis', name: 'Diagnosis', component: DiagnosisView },
  { path: '/rankings', name: 'Rankings', component: RankingsView },
  { path: '/watchlist', name: 'Watchlist', component: WatchlistView },
  { path: '/status', name: 'Status', component: StatusView },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
