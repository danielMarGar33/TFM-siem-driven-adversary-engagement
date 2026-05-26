<script setup lang="ts">
import { computed } from 'vue';

interface CanvasNode {
  name: string;
  node_name: string;
  node_type: string;
  parameters?: Record<string, any>;
  execution?: Record<string, any>;
  outputConfig?: Record<string, any>;
}

interface Props {
  modelNode: CanvasNode | null;
}

interface Emits {
  close: [];
  updateNode: [node: CanvasNode];
}

defineProps<Props>();
defineEmits<Emits>();

const formatParamLabel = (key: string) => {
  return key
    .replace(/_/g, ' ')
    .split(' ')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
};
</script>

<template>
  <aside v-if="modelNode" class="side-panel config-panel">
    <div class="side-panel-header">
      <h3>{{ modelNode.node_name || modelNode.name }}</h3>
      <button class="close-btn" @click="$emit('close')">✕</button>
    </div>

    <!-- Parámetros del modelo -->
    <div v-if="modelNode.parameters && Object.keys(modelNode.parameters).length > 0" class="config-group">
      <h4 class="group-title">Model Parameters</h4>
      <div 
        v-for="(val, key) in modelNode.parameters" 
        :key="key"
        class="form-field"
      >
        <label>{{ formatParamLabel(key as string) }}</label>
        <input 
          type="text" 
          :value="modelNode.parameters![key as string]" 
          @input="(e: Event) => {
            if (modelNode && modelNode.parameters) {
              modelNode.parameters[key as string] = (e.target as HTMLInputElement).value;
              $emit('updateNode', modelNode);
            }
          }"
          class="input-text" 
          placeholder="Enter value"
        />
      </div>
    </div>

    <!-- Configuración de ejecución -->
    <div v-if="modelNode.execution && Object.keys(modelNode.execution).length > 0" class="config-group">
      <h4 class="group-title">Execution Configuration</h4>
      <div 
        v-for="(val, key) in modelNode.execution" 
        :key="key"
        class="form-field"
      >
        <label>{{ formatParamLabel(key as string) }}</label>
        <input 
          type="text" 
          :value="modelNode.execution![key as string]" 
          @input="(e: Event) => {
            if (modelNode && modelNode.execution) {
              modelNode.execution[key as string] = (e.target as HTMLInputElement).value;
              $emit('updateNode', modelNode);
            }
          }"
          class="input-text"
          placeholder="Enter value"
        />
      </div>
    </div>

    <!-- Configuración de salida -->
    <div v-if="modelNode.outputConfig && Object.keys(modelNode.outputConfig).length > 0" class="config-group">
      <h4 class="group-title">Output Configuration</h4>
      <div 
        v-for="(val, key) in modelNode.outputConfig" 
        :key="key"
        class="form-field"
      >
        <label>{{ formatParamLabel(key as string) }}</label>
        <input 
          type="text" 
          :value="modelNode.outputConfig![key as string]" 
          @input="(e: Event) => {
            if (modelNode && modelNode.outputConfig) {
              modelNode.outputConfig[key as string] = (e.target as HTMLInputElement).value;
              $emit('updateNode', modelNode);
            }
          }"
          class="input-text"
          placeholder="Enter value"
        />
      </div>
    </div>

    <!-- Mensaje si no hay configuración -->
    <div v-if="!modelNode.parameters && !modelNode.execution && !modelNode.outputConfig" class="no-config">
      <p>No configuration available for this model</p>
    </div>
  </aside>
</template>

<style scoped>
.config-panel {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 0;
  display: flex;
  flex-direction: column;
  max-height: 600px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  overflow-y: auto;
}

.side-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid #e2e8f0;
  background: #f8fafc;
  border-radius: 8px 8px 0 0;
  flex-shrink: 0;
}

.side-panel-header h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
}

.close-btn {
  background: none;
  border: none;
  font-size: 20px;
  color: #94a3b8;
  cursor: pointer;
  padding: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.close-btn:hover {
  color: #0f172a;
  background: #e2e8f0;
  border-radius: 4px;
}

.config-group {
  padding: 16px;
  border-bottom: 1px solid #f1f5f9;
}

.config-group:last-child {
  border-bottom: none;
}

.group-title {
  margin: 0 0 12px 0;
  font-size: 12px;
  font-weight: 600;
  color: #475569;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 12px;
}

.form-field:last-child {
  margin-bottom: 0;
}

.form-field label {
  font-size: 12px;
  font-weight: 500;
  color: #334155;
}

.input-text {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid #cbd5e1;
  border-radius: 4px;
  font-size: 12px;
  background-color: #ffffff;
  transition: all 0.2s ease;
  box-sizing: border-box;
}

.input-text:focus {
  outline: none;
  border-color: #0F92A3;
  box-shadow: 0 0 0 2px rgba(15, 146, 163, 0.1);
}

.input-text::placeholder {
  color: #94a3b8;
}

.no-config {
  padding: 24px 16px;
  text-align: center;
  color: #94a3b8;
  font-size: 12px;
}

.no-config p {
  margin: 0;
}
</style>
