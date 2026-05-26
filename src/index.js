import { createRouter, createWebHistory } from 'vue-router';

import PipelinesList from './components/PipelinesList.vue';
import PipelineDesigner from './components/PipelineDesigner.vue';
import PipelineExecutor from './components/PipelineExecutor.vue';
import DetailedViewExecutor from './components/DetailedViewExecutor.vue';

const routes = [
  {
    path: '/',
    name: 'PipelinesList',
    component: PipelinesList
  },
  {
    // Vista de la pipeline fija
    path: '/detailed/pipelines/:id/edit',
    name: 'FixedPipelineView',
    component: PipelineDesigner
  },
  {
    // Vista general de ejecuciones
    path: '/execution/simulations',
    name: 'PipelineExecutor',
    component: PipelineExecutor
  },
  {
    // Vista detallada de una ejecución concreta
    path: '/execution/simulations/:id',
    name: 'DetailedViewExecutor',
    component: DetailedViewExecutor
  }
];

const router = createRouter({
  history: createWebHistory(),
  routes
});

export default router;