<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps({
  pipeline: {
    type: Object,
    required: true
  },
  isSelected: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['seleccionar']);

const modelsList = computed(() => {
  if (!props.pipeline?.pipeline_nodes || !Array.isArray(props.pipeline.pipeline_nodes)) return [];
  
  return props.pipeline.pipeline_nodes.map((node: any) => {
    // Sacamos la versión si existe
    const version = node.model_version ? `v${node.model_version.split('.')[0]}` : '';
    const name = (node.node_type || node.name || 'Unknown').replace(/_/g, ' ');
    return version ? `${name}-${version}` : name;
  }).slice(0, 4);
});

// Computado para sacar los nombres reales para el esquema de abajo (DAG)
const dagNodes = computed(() => {
  if (!props.pipeline?.pipeline_nodes || !Array.isArray(props.pipeline.pipeline_nodes)) return [];
  return props.pipeline.pipeline_nodes.map((node: any) => node.node_name || node.name || 'Unknown');
});
</script>

<template>
  <div 
    class="pipeline-card selectable-card"
    :class="{ 'is-selected': isSelected }"
    @click="emit('seleccionar')"
  >
    <div class="card-header">
       <h3 class="pipeline-id">{{ pipeline.pipeline_id }}</h3>
       <p class="pipeline-desc">{{ pipeline.pipeline_description }}</p>
    </div>

    <div class="card-meta">
      <div class="meta-item">
        <span class="meta-label">CKT Characterization ID</span>
        <span class="meta-value">{{ pipeline.mission_characterization_id }}</span>
      </div>
      <div class="meta-item">
        <span class="meta-label">Execution Mode</span>
        <span class="meta-value" style="text-transform: capitalize;">
          {{ pipeline.pipeline_execution_mode?.replace('_', ' ') }}
        </span>
      </div>
    </div>
      
    <div class="tags-group models-group">
      <span class="meta-label">Models</span>
      <div class="models-list">
        <span v-for="model in modelsList" :key="model" class="model-badge">
          {{ model }}
        </span>
      </div>
    </div>

    <div class="card-summary">
      <span class="meta-label">Results Summary</span>
      <p class="summary-text">{{ pipeline.results_summary || 'Pending execution...' }}</p>
    </div>

    <div class="card-dag">
      <div class="start-circle"></div>
      
      <template v-for="(node, index) in pipeline.pipeline_nodes" :key="index">
        <span class="dag-arrow">→</span>
        <div class="dag-node">{{ node.name || node.node_name }}</div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.pipeline-card {
  background: #FFFFFF;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0px 2px 4px rgba(0, 0, 0, 0.05);
  border: 1px solid #E2E8F0;
  
  /* Flexbox interno de la tarjeta */
  display: flex;
  flex-direction: column;
  gap: 16px;
  
  /* Forzamos a que ocupe todo el espacio que le da el padre */
  width: 100%;
  height: 100%; 
  box-sizing: border-box;
  font-family: 'Roboto', sans-serif;
}

.card-summary {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex-grow: 1; 
}

.card-dag {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: auto; 
  padding-top: 16px;
  overflow-x: auto;
  width: 100%;
  padding-bottom: 6px; /* Espacito por si sale la barra de scroll */
}

/* Hacemos la barra de scroll horizontal muy finita y elegante */
.card-dag::-webkit-scrollbar {
  height: 4px;
}
.card-dag::-webkit-scrollbar-thumb {
  background-color: #CBD5E1;
  border-radius: 4px;
}

/* --- NUEVOS ESTILOS DE SELECCIÓN --- */
.selectable-card {
  cursor: pointer;
  transition: all 0.2s ease;
}

.selectable-card:hover {
  box-shadow: 0px 4px 12px rgba(0, 0, 0, 0.08); 
}

.is-selected {
  border-color: #0F92A3 !important; 
  box-shadow: 0px 0px 0px 1px #0F92A3; 
  background-color: #F0FBFC; 
}
/* --------------------------------- */

.pipeline-id {
  font-size: 16px;
  font-weight: 700;
  color: #1E293B;
  margin: 0 0 4px 0;
}

.pipeline-desc {
  font-size: 13px;
  color: #64748B;
  margin: 0;
}

.card-meta {
  display: flex;
  gap: 24px;
}

.meta-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.meta-label {
  font-size: 11px;
  font-weight: 600;
  color: #000000;
}

.meta-value {
  font-size: 13px;
  color: #334155;
}

.tags-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.models-group {
  flex-grow: 1;
}

.models-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.model-badge {
  background-color: #F1F5F9;
  color: #475569;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
}

.summary-text {
  font-size: 12px;
  color: #475569;
  margin: 0;
  line-height: 1.4;
}

.start-circle {
  width: 24px;
  height: 24px;
  border: 1px solid #94A3B8;
  border-radius: 50%;
  flex-shrink: 0; /* Evita que el círculo se deforme */
}

.dag-arrow {
  color: #94A3B8;
  font-size: 14px;
  flex-shrink: 0; /* Evita que la flecha se aplaste */
}

.dag-node {
  border: 1px solid #CBD5E1;
  border-radius: 4px;
  padding: 4px 8px; /* Un poco más compactas */
  font-size: 11px;  /* Texto ligeramente más pequeño */
  color: #1E293B;
  background: white;
  white-space: nowrap; /* Impide que el texto baje a la siguiente línea */
  flex-shrink: 0; /* Impide que la caja se encoja */
}
</style>