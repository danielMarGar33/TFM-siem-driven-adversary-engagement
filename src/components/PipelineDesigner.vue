<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import pipelinesData from '../assets/pipelines.json';
import modelsData from '../assets/models.json';

const router = useRouter();

const pipelines = pipelinesData as any[];
const models = modelsData as any[];

const fixedPipeline = pipelines[0];

const pipelineId = ref(fixedPipeline.pipeline_id);
const pipelineStatus = ref('ready');
const isDirty = ref(false);

const showToast = ref(false);
const toastPipelineId = ref('');
const toastAction = ref('');

const canvasNodes = ref<any[]>([]);
const connections = ref<any[]>([]);
const selectedCanvasNode = ref<any | null>(null);

const executionName = ref('');
const executionInputPath = ref('');
const executionInputData = ref<any>(null);
const executionInputText = ref('');

const zoomLevel = ref(1);
const showSearch = ref(false);
const canvasSearchQuery = ref('');
const canvasRef = ref<HTMLElement | null>(null);
const inputFileRef = ref<HTMLInputElement | null>(null);
const parametersFileRef = ref<HTMLInputElement | null>(null);
const isCanvasDragging = ref(false);
const suppressNextNodeClick = ref(false);
const dragStart = ref({
  x: 0,
  y: 0,
  scrollLeft: 0,
  scrollTop: 0
});

const NODE_WIDTH = 220;
const NODE_HORIZONTAL_PADDING = 24;
const NODE_CENTER_Y = 68;
const NODE_RENDERED_WIDTH = NODE_WIDTH + NODE_HORIZONTAL_PADDING;

const enrichedNodes = computed(() => {
  return fixedPipeline.pipeline_nodes.map((node: any, index: number) => {
    const model = models.find((item: any) => item.id === node.node_type);

    return {
      ...node,
      instanceId: node.node_id,
      id: node.node_type,
      name: node.node_name,
      desc: model?.desc || '',
      inputs: model?.inputs || [],
      outputs: model?.outputs || [],
      intermediate: model?.intermediate || [],
      parameters: {
        ...(model?.parameters || {}),
        ...(node.node_parameters || {})
      },
      execution: {
        ...(model?.execution || {}),
        ...(node.node_execution_settings || {})
      },
      outputConfig: {
        ...(model?.outputConfig || {}),
        ...(node.node_output_configuration || {})
      },
      script: model?.script || model?.execution_path || null,
      x: 90 + index * 360,
      y: 105
    };
  });
});

onMounted(() => {
  pipelineId.value = fixedPipeline.pipeline_id;
  pipelineStatus.value = 'ready';

  canvasNodes.value = enrichedNodes.value;

  connections.value = fixedPipeline.pipeline_connections.map((connection: any) => ({
    ...connection,
    id: connection.connection_id,
    source: connection.source_node_id,
    target: connection.target_node_id
  }));

  selectedCanvasNode.value = canvasNodes.value[0] || null;
});

const selectCanvasNode = (node: any) => {
  if (suppressNextNodeClick.value) {
    suppressNextNodeClick.value = false;
    return;
  }

  selectedCanvasNode.value = node;
};

const startCanvasDrag = (event: PointerEvent) => {
  if (!canvasRef.value || event.button !== 0) return;
  if ((event.target as HTMLElement).closest('.pipeline-node')) return;

  isCanvasDragging.value = false;
  suppressNextNodeClick.value = false;
  dragStart.value = {
    x: event.clientX,
    y: event.clientY,
    scrollLeft: canvasRef.value.scrollLeft,
    scrollTop: canvasRef.value.scrollTop
  };

  canvasRef.value.setPointerCapture(event.pointerId);
};

const dragCanvas = (event: PointerEvent) => {
  if (!canvasRef.value || !(event.buttons & 1)) return;

  const deltaX = event.clientX - dragStart.value.x;
  const deltaY = event.clientY - dragStart.value.y;

  if (!isCanvasDragging.value && Math.hypot(deltaX, deltaY) < 4) return;

  isCanvasDragging.value = true;
  suppressNextNodeClick.value = true;
  canvasRef.value.scrollLeft = dragStart.value.scrollLeft - deltaX;
  canvasRef.value.scrollTop = dragStart.value.scrollTop - deltaY;
};

const stopCanvasDrag = (event: PointerEvent) => {
  canvasRef.value?.releasePointerCapture(event.pointerId);
  isCanvasDragging.value = false;
};

const isNodeDimmed = (nodeName: string) => {
  if (!canvasSearchQuery.value) return false;

  return !nodeName
    .toLowerCase()
    .includes(canvasSearchQuery.value.toLowerCase());
};

const calculatePath = (sourceId: string, targetId: string) => {
  const sourceNode = canvasNodes.value.find(
    (node) => node.node_id === sourceId || node.instanceId === sourceId
  );

  const targetNode = canvasNodes.value.find(
    (node) => node.node_id === targetId || node.instanceId === targetId
  );

  if (!sourceNode || !targetNode) return '';

  const startX = sourceNode.x + NODE_RENDERED_WIDTH;
  const startY = sourceNode.y + NODE_CENTER_Y;
  const endX = targetNode.x - 10;
  const endY = targetNode.y + NODE_CENTER_Y;
  const curveOffset = Math.max(80, Math.abs(endX - startX) * 0.45);

  return `M ${startX} ${startY} C ${startX + curveOffset} ${startY}, ${endX - curveOffset} ${endY}, ${endX} ${endY}`;
};

const getConnectionPoint = (nodeId: string, side: 'source' | 'target') => {
  const node = canvasNodes.value.find(
    (item) => item.node_id === nodeId || item.instanceId === nodeId
  );

  if (!node) return { x: 0, y: 0 };

  return {
    x: side === 'source' ? node.x + NODE_RENDERED_WIDTH : node.x,
    y: node.y + NODE_CENTER_Y
  };
};

const zoomIn = () => {
  zoomLevel.value = Math.min(zoomLevel.value + 0.1, 2);
};

const zoomOut = () => {
  zoomLevel.value = Math.max(zoomLevel.value - 0.1, 0.4);
};

const toggleFullscreen = () => {
  if (!document.fullscreenElement) {
    canvasRef.value?.requestFullscreen().catch(() => { });
  } else {
    document.exitFullscreen();
  }
};

const openInputFilePicker = () => {
  inputFileRef.value?.click();
};

const readFileAsText = (file: File) => {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ''));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(file);
  });
};

const onInputFileSelected = async (event: Event) => {
  const file = (event.target as HTMLInputElement).files?.[0];
  if (!file) return;

  executionInputPath.value = file.webkitRelativePath || file.name;
  executionInputText.value = await readFileAsText(file);

  try {
    executionInputData.value = JSON.parse(executionInputText.value);
  } catch {
    executionInputData.value = null;
  }
};

const showToastMessage = (id: string, action: string) => {
  toastPipelineId.value = id;
  toastAction.value = action;
  showToast.value = true;

  setTimeout(() => {
    showToast.value = false;
  }, 3000);
};

const formatParamLabel = (key: string) => {
  return key
    .replace(/_/g, ' ')
    .split(' ')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
};

const getParameterPlaceholder = (key: string) => {
  const placeholders: Record<string, string> = {
    siem_name: 'Example: wazuh',
    input_format: 'Example: json_or_ndjson',
    name_field: 'Example: rule.description',
    description_field: 'Example: rule.description',
    ttps_field: 'Example: rule.mitre.id',
    alert_type_field: 'Example: tags.engage.alert_type',
    acceptable_risk_field: 'Example: tags.engage.acceptable_risk',
    payload_context_fields: 'Example: rule.id, agent.name'
  };

  return placeholders[key] || 'Enter value';
};

const isAlertTranslatorNode = (node: any) => {
  return node?.id === 'm1' || node?.node_type === 'm1';
};

const selectedParametersJson = computed(() => {
  return JSON.stringify(selectedCanvasNode.value?.parameters || {}, null, 2);
});

const getPayloadContextFields = (node: any) => {
  const value = node?.parameters?.payload_context_fields;

  if (Array.isArray(value)) {
    return value.length > 0 ? value : [''];
  }

  const fields = String(value || '')
    .split(',')
    .map((field) => field.trim())
    .filter((field) => field.length > 0);

  node.parameters.payload_context_fields = fields.length > 0 ? fields : [''];

  return node.parameters.payload_context_fields;
};

const addPayloadContextField = (node: any) => {
  getPayloadContextFields(node).push('');
};

const removePayloadContextField = (node: any, index: string | number) => {
  const fields = getPayloadContextFields(node);
  fields.splice(Number(index), 1);

  if (fields.length === 0) {
    fields.push('');
  }
};

const normalizeImportedParameters = (data: any) => {
  const source = data?.parameters || data;

  if (source?.siem || source?.field_mapping) {
    const mapping = source.field_mapping || {};

    return {
      siem_name: source.siem?.name || '',
      input_format: source.siem?.input_format || '',
      name_field: mapping.name || '',
      description_field: mapping.description || '',
      ttps_field: mapping.ttps || '',
      alert_type_field: mapping.alert_type || '',
      acceptable_risk_field: mapping.acceptable_risk || '',
      payload_context_fields: Array.isArray(mapping.payload_context)
        ? mapping.payload_context
        : String(mapping.payload_context || '')
            .split(',')
            .map((field) => field.trim())
            .filter((field) => field.length > 0)
    };
  }

  return {
    ...source,
    payload_context_fields: Array.isArray(source?.payload_context_fields)
      ? source.payload_context_fields
      : String(source?.payload_context_fields || '')
          .split(',')
          .map((field) => field.trim())
          .filter((field) => field.length > 0)
  };
};

const openParametersFilePicker = () => {
  parametersFileRef.value?.click();
};

const onParametersFileSelected = async (event: Event) => {
  const fileInput = event.target as HTMLInputElement;
  const file = fileInput.files?.[0];

  if (!file || !selectedCanvasNode.value || !isAlertTranslatorNode(selectedCanvasNode.value)) return;

  try {
    const importedData = JSON.parse(await readFileAsText(file));
    selectedCanvasNode.value.parameters = normalizeImportedParameters(importedData);
  } catch {
    alert('Parameters file must be valid JSON.');
  } finally {
    fileInput.value = '';
  }
};

const exportSelectedParameters = () => {
  if (!selectedCanvasNode.value || !isAlertTranslatorNode(selectedCanvasNode.value)) return;

  const blob = new Blob([selectedParametersJson.value], {
    type: 'application/json'
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');

  a.href = url;
  a.download = `${selectedCanvasNode.value.name || 'model'}-parameters.json`
    .toLowerCase()
    .replace(/\s+/g, '-');

  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
};

const buildTranslatorConfiguration = (parameters: Record<string, any> = {}) => {
  const rawPayloadContext = parameters.payload_context_fields;
  const payloadContextSource = Array.isArray(rawPayloadContext)
    ? rawPayloadContext
    : String(rawPayloadContext || '').split(',');
  const payloadContext = payloadContextSource
    .map((field) => field.trim())
    .filter((field) => field.length > 0);

  return {
    siem: {
      name: String(parameters.siem_name || '').trim(),
      input_format: String(parameters.input_format || '').trim()
    },
    field_mapping: {
      name: String(parameters.name_field || '').trim(),
      description: String(parameters.description_field || '').trim(),
      ttps: String(parameters.ttps_field || '').trim(),
      alert_type: String(parameters.alert_type_field || '').trim(),
      acceptable_risk: String(parameters.acceptable_risk_field || '').trim(),
      payload_context: payloadContext
    }
  };
};

const getTranslatorNode = () => {
  return canvasNodes.value.find((node) => node.id === 'm1' || node.node_type === 'm1');
};

const buildPipelineSnapshot = () => {
  const nodeSnapshots = fixedPipeline.pipeline_nodes.map((node: any) => {
    const canvasNode = canvasNodes.value.find(
      (item) => item.node_id === node.node_id || item.instanceId === node.node_id
    );

    return {
      ...node,
      node_name: canvasNode?.name || node.node_name,
      node_parameters: { ...(canvasNode?.parameters || {}) },
      node_execution_settings: { ...(canvasNode?.execution || {}) },
      node_output_configuration: { ...(canvasNode?.outputConfig || {}) }
    };
  });

  return {
    ...fixedPipeline,
    pipeline_nodes: nodeSnapshots
  };
};

const createExecution = () => {
  if (!executionInputPath.value.trim()) {
    alert('Input file path is required.');
    return;
  }

  const rawSiemAlert = executionInputData.value ?? executionInputText.value.trim();

  if (!rawSiemAlert) {
    alert('Input file must contain a Raw SIEM alert.');
    return;
  }

  const translatorNode = getTranslatorNode();
  const translatorConfiguration = buildTranslatorConfiguration(translatorNode?.parameters || {});
  const pipelineSnapshot = buildPipelineSnapshot();

  const savedSims = localStorage.getItem('simulations_db');
  const simulations = savedSims ? JSON.parse(savedSims) : [];

  const relatedExecutions = simulations.filter(
    (simulation: any) => simulation.pipeline_id === fixedPipeline.pipeline_id
  );

  const nextNumber = relatedExecutions.length + 1;
  const simulationId = `EXEC-${String(nextNumber).padStart(3, '0')}`;

  const newSimulation = {
    simulation_id: simulationId,
    execution_id: null,

    pipeline_id: fixedPipeline.pipeline_id,
    pipeline_name: fixedPipeline.pipeline_id,

    status: 'Ready',

    input: {
      execution_name: executionName.value.trim() || `Execution ${nextNumber}`,
      input_file_path: executionInputPath.value.trim(),
      'Raw SIEM alert': rawSiemAlert,
      input_data: executionInputData.value,
      input_text: executionInputText.value,
      model_parameters: Object.fromEntries(
        canvasNodes.value.map((node) => [
          node.node_id || node.instanceId,
          { ...(node.parameters || {}) }
        ])
      )
    },

    output: {
      model_outputs: {},
      final_output: null
    },

    pipeline_snapshot: pipelineSnapshot,
    models_snapshot: models,

    metadata: {
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      created_by: 'current-user',
      model_configuration: {
        translator_configuration: translatorConfiguration
      }
    }
  };

  simulations.push(newSimulation);
  localStorage.setItem('simulations_db', JSON.stringify(simulations));

  showToastMessage(simulationId, 'created');

  setTimeout(() => {
    router.push(`/execution/simulations/${simulationId}`);
  }, 700);
};

const goBack = () => {
  router.push('/');
};
</script>

<template>
  <div class="designer-view">
    <div class="top-nav">
      <button class="btn-back" @click="$router.back()">&lt; Back</button>
      <div>
        <button class="btn-primary" @click="$router.push('/execution/simulations')">Execution List</button>
      </div>
    </div>
    <div class="designer-header">
      <div>
        <h2>{{ pipelineId }}</h2>
        <p>
          {{ fixedPipeline.pipeline_description }}
        </p>
      </div>
    </div>

    <div class="designer-layout">
      <aside class="side-panel">
        <div class="panel-box">
          <h3>Execution Input</h3>

          <label class="field-label">Execution name</label>
          <input v-model="executionName" class="text-input" type="text" placeholder="Example: Base scenario" />

          <label class="field-label">Input file path</label>
          <div class="file-picker">
            <input v-model="executionInputPath" class="text-input" type="text"
              placeholder="Select input file..." readonly />
            <button type="button" class="file-picker-button" @click="openInputFilePicker">
              Browse
            </button>
            <input ref="inputFileRef" class="file-input" type="file" @change="onInputFileSelected" />
          </div>
        </div>

        <aside v-if="selectedCanvasNode" class="config-panel">
          <div class="side-panel-header">
            <h3>{{ selectedCanvasNode.name }} Parameters</h3>
          </div>

          <div class="config-group">
            <h4 class="group-title">Analysis Model</h4>

            <div v-if="isAlertTranslatorNode(selectedCanvasNode)" class="parameter-actions">
              <button type="button" class="btn-secondary compact-button" @click="openParametersFilePicker">
                Import Parameters
              </button>

              <button type="button" class="btn-secondary compact-button" @click="exportSelectedParameters">
                Export Parameters
              </button>

              <input
                ref="parametersFileRef"
                class="file-input"
                type="file"
                accept=".json,application/json"
                @change="onParametersFileSelected"
              />
            </div>

            <template v-if="selectedCanvasNode.parameters && Object.keys(selectedCanvasNode.parameters).length > 0">
              <div
                v-for="(val, key) in selectedCanvasNode.parameters"
                :key="key"
                class="form-field"
                :class="{ 'payload-context-field': key === 'payload_context_fields' }"
              >
                <label>{{ formatParamLabel(key as string) }}</label>

                <template v-if="key === 'payload_context_fields'">
                  <div class="payload-header">
                    <span class="helper-text compact-helper">Add one payload context path per field.</span>

                    <button
                      type="button"
                      class="btn-add-field"
                      @click="addPayloadContextField(selectedCanvasNode)"
                      title="Add field"
                    >
                      +
                    </button>
                  </div>

                  <div class="payload-fields">
                    <div
                      v-for="(_, index) in getPayloadContextFields(selectedCanvasNode)"
                      :key="index"
                      class="payload-field-row"
                    >
                      <input
                        v-model="selectedCanvasNode.parameters.payload_context_fields[index]"
                        type="text"
                        class="text-input"
                        placeholder="Example: rule.id"
                      />

                      <button
                        type="button"
                        class="btn-remove-field"
                        @click="removePayloadContextField(selectedCanvasNode, index)"
                        title="Remove field"
                      >
                        x
                      </button>
                    </div>
                  </div>
                </template>

                <input
                  v-else
                  v-model="selectedCanvasNode.parameters[key]"
                  type="text"
                  class="text-input"
                  :placeholder="getParameterPlaceholder(key as string)"
                />
              </div>
            </template>

            <p v-else class="helper-text">
              This model has no parameters.
            </p>

            <div
              v-if="isAlertTranslatorNode(selectedCanvasNode) && selectedCanvasNode.parameters"
              class="parameters-json-preview"
            >
              <h4 class="group-title">Parameters JSON</h4>
              <pre>{{ selectedParametersJson }}</pre>
            </div>
          </div>
        </aside>

        <button class="btn-primary full-width create-execution-button" @click="createExecution">
          Create Execution
        </button>
      </aside>

      <main class="canvas-wrapper">
        <div class="canvas-toolbar">
          <button @click="showSearch = !showSearch">Search</button>

          <input v-if="showSearch" v-model="canvasSearchQuery" class="canvas-search-input"
            placeholder="Find model..." />

          <button @click="zoomIn">+</button>
          <button @click="zoomOut">-</button>
          <button @click="toggleFullscreen">⛶</button>
        </div>

        <div
          class="canvas-area"
          :class="{ dragging: isCanvasDragging }"
          ref="canvasRef"
          @pointerdown="startCanvasDrag"
          @pointermove="dragCanvas"
          @pointerup="stopCanvasDrag"
          @pointercancel="stopCanvasDrag"
          @pointerleave="stopCanvasDrag"
        >
          <div class="canvas-content" :style="{
            transform: `scale(${zoomLevel})`,
            transformOrigin: 'top left'
          }">
            <svg class="connections-layer">
              <defs>
                <marker
                  id="pipeline-arrow"
                  viewBox="0 0 10 10"
                  refX="8"
                  refY="5"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 0 L 10 5 L 0 10 z" class="connection-arrow" />
                </marker>
              </defs>

              <path v-for="connection in connections" :key="connection.id"
                :d="calculatePath(connection.source_node_id, connection.target_node_id)" class="connection-path" />

              <template v-for="connection in connections" :key="connection.id + '-points'">
                <circle
                  :cx="getConnectionPoint(connection.source_node_id, 'source').x"
                  :cy="getConnectionPoint(connection.source_node_id, 'source').y"
                  r="5"
                  class="connection-dot start-dot"
                />

                <circle
                  :cx="getConnectionPoint(connection.target_node_id, 'target').x"
                  :cy="getConnectionPoint(connection.target_node_id, 'target').y"
                  r="5"
                  class="connection-dot end-dot"
                />
              </template>
            </svg>

            <div v-for="node in canvasNodes" :key="node.instanceId" class="pipeline-node" :class="{
              selected: selectedCanvasNode?.instanceId === node.instanceId,
              dimmed: isNodeDimmed(node.name)
            }" :style="{ left: node.x + 'px', top: node.y + 'px' }" @click="selectCanvasNode(node)">
              <div class="node-title">
                {{ node.name }}
              </div>

              <div class="node-subtitle">
                {{ node.id }} · {{ node.execution?.mode || 'Script' }}
              </div>

              <div class="node-io">
                <div class="node-io-row">
                  <span class="node-io-label input-label">IN</span>
                  <span class="node-io-values">{{ node.inputs.join(', ') || 'None' }}</span>
                </div>

                <div class="node-io-row">
                  <span class="node-io-label output-label">OUT</span>
                  <span class="node-io-values">{{ node.outputs.join(', ') || 'None' }}</span>
                </div>
              </div>

              <div class="node-parameters-summary">
                <span class="node-parameters-arrow" aria-hidden="true"></span>

                <div class="node-parameters-content">
                  <span class="node-parameters-title">Parameters</span>

                  <div v-if="Object.keys(node.parameters || {}).length > 0" class="node-parameter-chips">
                    <span
                      v-for="parameterKey in Object.keys(node.parameters || {})"
                      :key="parameterKey"
                      class="node-parameter-chip"
                    >
                      {{ formatParamLabel(parameterKey) }}
                    </span>
                  </div>

                  <span v-else class="node-no-parameters">No parameters</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>

    <Teleport to="body">
      <transition name="toast-slide">
        <div v-if="showToast" class="success-toast">
          <div class="toast-content">
            <h4>Success</h4>
            <p><strong>{{ toastPipelineId }}</strong> {{ toastAction }}</p>
          </div>
          <button class="toast-close" @click="showToast = false">✕</button>
        </div>
      </transition>
    </Teleport>
  </div>
</template>

<style scoped src="./PipelineDesigner.css"></style>
