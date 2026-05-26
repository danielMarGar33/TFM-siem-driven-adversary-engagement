import { createRouter, createWebHistory } from 'vue-router';

import PipelinesList from './components/PipelinesList.vue';
import PipelineDesigner from './components/PipelineDesigner.vue';
import PipelineExecutor from './components/PipelineExecutor.vue';
import DetailedViewExecutor from './components/DetailedViewExecutor.vue';
import ExecutionConfigBuilder from './components/ExecutionConfigBuilder.vue';

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
  },
  {
    //Vista de creación de un archivo de configuración
    path: '/configBuilder',
    name: 'ExecutionConfigBuilder',
    component: ExecutionConfigBuilder
  }
];

const router = createRouter({
  history: createWebHistory(),
  routes
});

export default router;