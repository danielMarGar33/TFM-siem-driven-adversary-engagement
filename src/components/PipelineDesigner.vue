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
const executionInputFileSize = ref(0);
const inputFileError = ref('');

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
const MAX_INPUT_FILE_SIZE_BYTES = 10 * 1024 * 1024;

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
  const fileInput = event.target as HTMLInputElement;
  const file = fileInput.files?.[0];
  if (!file) return;

  if (file.size > MAX_INPUT_FILE_SIZE_BYTES) {
    executionInputPath.value = '';
    executionInputData.value = null;
    executionInputText.value = '';
    executionInputFileSize.value = 0;
    inputFileError.value = 'Input file must be 10 MB or smaller.';
    fileInput.value = '';
    return;
  }

  inputFileError.value = '';
  executionInputPath.value = file.webkitRelativePath || file.name;
  executionInputFileSize.value = file.size;
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
    .replace(/[._]/g, ' ')
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
    ttps_fields: 'Example: rule.mitre.id',
    alert_type_field: 'Example: tags.engage.alert_type',
    max_cvss_base_score: 'Example: tags.engage.max_cvss_base_score',
    max_impact_subscore: 'Example: tags.engage.max_impact_subscore',
    max_exploitability_subscore: 'Example: tags.engage.max_exploitability_subscore',
    payload_context_fields: 'Example: rule.id, agent.name'
  };

  return placeholders[key] || 'Enter value';
};

const isAlertTranslatorNode = (node: any) => {
  return node?.id === 'm1' || node?.node_type === 'm1';
};

const sanitizePayloadContextFieldsValue = (value: unknown) => {
  const source = Array.isArray(value) ? value : String(value || '').split(',');

  return source
    .map((field) => String(field || '').trim())
    .filter((field) => field.length > 0);
};

const sanitizeTtpFieldsValue = (value: unknown) => {
  const source = Array.isArray(value) ? value : String(value || '').split(',');

  return source
    .map((field) => String(field || '').trim())
    .filter((field) => field.length > 0);
};

const REQUIRED_TRANSLATOR_PARAMETER_LABELS: Record<string, string> = {
  siem_name: 'SIEM Name',
  input_format: 'Input Format',
  name_field: 'Name Field',
  description_field: 'Description Field',
  alert_type_field: 'Alert Type Field',
  max_cvss_base_score: 'Max CVSS Base Score',
  max_impact_subscore: 'Max Impact Subscore',
  max_exploitability_subscore: 'Max Exploitability Subscore'
};

const sanitizeParameters = (parameters: Record<string, any> = {}) => {
  const sanitized = { ...parameters };

  if ('ttps_fields' in sanitized || 'ttps_field' in sanitized) {
    sanitized.ttps_fields = sanitizeTtpFieldsValue(
      sanitized.ttps_fields ?? sanitized.ttps_field
    );
    delete sanitized.ttps_field;
  }

  if ('payload_context_fields' in sanitized) {
    sanitized.payload_context_fields = sanitizePayloadContextFieldsValue(
      sanitized.payload_context_fields
    );
  }

  return sanitized;
};

const selectedParametersJson = computed(() => {
  return JSON.stringify(
    sanitizeParameters(selectedCanvasNode.value?.parameters || {}),
    null,
    2
  );
});

const getPayloadContextFields = (node: any) => {
  const value = node?.parameters?.payload_context_fields;

  if (Array.isArray(value)) {
    return value;
  }

  const fields = sanitizePayloadContextFieldsValue(value);
  node.parameters.payload_context_fields = fields;

  return node.parameters.payload_context_fields;
};

const getTtpFields = (node: any) => {
  const value = node?.parameters?.ttps_fields;

  if (Array.isArray(value)) {
    return value;
  }

  const fields = sanitizeTtpFieldsValue(value ?? node?.parameters?.ttps_field);
  node.parameters.ttps_fields = fields;
  delete node.parameters.ttps_field;

  return node.parameters.ttps_fields;
};

const sanitizePayloadContextFieldsForNode = (node: any) => {
  if (!node?.parameters) return;

  node.parameters.payload_context_fields = sanitizePayloadContextFieldsValue(
    node.parameters.payload_context_fields
  );
};

const sanitizeTtpFieldsForNode = (node: any) => {
  if (!node?.parameters) return;

  node.parameters.ttps_fields = sanitizeTtpFieldsValue(
    node.parameters.ttps_fields ?? node.parameters.ttps_field
  );
  delete node.parameters.ttps_field;
};

const addPayloadContextField = (node: any) => {
  if (!node?.parameters) return;

  if (!Array.isArray(node.parameters.payload_context_fields)) {
    node.parameters.payload_context_fields = sanitizePayloadContextFieldsValue(
      node.parameters.payload_context_fields
    );
  }

  node.parameters.payload_context_fields.push('');
};

const addTtpField = (node: any) => {
  if (!node?.parameters) return;

  if (!Array.isArray(node.parameters.ttps_fields)) {
    node.parameters.ttps_fields = sanitizeTtpFieldsValue(
      node.parameters.ttps_fields ?? node.parameters.ttps_field
    );
  }

  delete node.parameters.ttps_field;
  node.parameters.ttps_fields.push('');
};

const removePayloadContextField = (node: any, index: string | number) => {
  const fields = getPayloadContextFields(node);
  fields.splice(Number(index), 1);
  sanitizePayloadContextFieldsForNode(node);
};

const removeTtpField = (node: any, index: string | number) => {
  const fields = getTtpFields(node);
  fields.splice(Number(index), 1);
  sanitizeTtpFieldsForNode(node);
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
      ttps_fields: sanitizeTtpFieldsValue(mapping.ttps),
      alert_type_field: mapping.alert_type || '',
      max_cvss_base_score: mapping.max_cvss_base_score || '',
      max_impact_subscore: mapping.max_impact_subscore || '',
      max_exploitability_subscore: mapping.max_exploitability_subscore || '',
      payload_context_fields: sanitizePayloadContextFieldsValue(mapping.payload_context)
    };
  }

  const normalized = {
    siem_name: source?.siem_name || '',
    input_format: source?.input_format || '',
    name_field: source?.name_field || '',
    description_field: source?.description_field || '',
    ttps_fields: sanitizeTtpFieldsValue(source?.ttps_fields ?? source?.ttps_field),
    alert_type_field: source?.alert_type_field || '',
    max_cvss_base_score: source?.max_cvss_base_score || '',
    max_impact_subscore: source?.max_impact_subscore || '',
    max_exploitability_subscore: source?.max_exploitability_subscore || '',
    payload_context_fields: sanitizePayloadContextFieldsValue(source?.payload_context_fields)
  };

  return sanitizeParameters(normalized);
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
  const ttps = sanitizeTtpFieldsValue(parameters.ttps_fields ?? parameters.ttps_field);
  const payloadContext = sanitizePayloadContextFieldsValue(parameters.payload_context_fields);

  return {
    siem: {
      name: String(parameters.siem_name || '').trim(),
      input_format: String(parameters.input_format || '').trim()
    },
    field_mapping: {
      name: String(parameters.name_field || '').trim(),
      description: String(parameters.description_field || '').trim(),
      ttps,
      alert_type: String(parameters.alert_type_field || '').trim(),
      max_cvss_base_score: String(parameters.max_cvss_base_score || '').trim(),
      max_impact_subscore: String(parameters.max_impact_subscore || '').trim(),
      max_exploitability_subscore: String(parameters.max_exploitability_subscore || '').trim(),
      payload_context: payloadContext
    }
  };
};

const getMissingTranslatorParameters = (parameters: Record<string, any> = {}) => {
  const sanitized = sanitizeParameters(parameters);
  const missingFields = Object.entries(REQUIRED_TRANSLATOR_PARAMETER_LABELS)
    .filter(([key]) => !String(sanitized[key] || '').trim())
    .map(([, label]) => label);

  if (sanitizeTtpFieldsValue(sanitized.ttps_fields).length === 0) {
    missingFields.push('TTP Fields');
  }

  return missingFields;
};

const createExecutionValidationMessage = computed(() => {
  if (!executionInputPath.value.trim()) {
    return 'Input file path is required.';
  }

  if (executionInputFileSize.value > MAX_INPUT_FILE_SIZE_BYTES) {
    return 'Input file must be 10 MB or smaller.';
  }

  const rawSiemAlert = executionInputData.value ?? executionInputText.value.trim();

  if (!rawSiemAlert) {
    return 'Input file must contain a Raw SIEM alert.';
  }

  const translatorNode = getTranslatorNode();
  const missingParameters = getMissingTranslatorParameters(translatorNode?.parameters || {});

  if (missingParameters.length > 0) {
    return `Complete all required translator parameters: ${missingParameters.join(', ')}.`;
  }

  return '';
});

const canCreateExecution = computed(() => !createExecutionValidationMessage.value);

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
      node_parameters: sanitizeParameters(canvasNode?.parameters || {}),
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
  if (createExecutionValidationMessage.value) {
    alert(createExecutionValidationMessage.value);
    return;
  }

  const rawSiemAlert = executionInputData.value ?? executionInputText.value.trim();
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
          sanitizeParameters(node.parameters || {})
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
        &nbsp;
        <button
          class="create-execution-button btn-primary-exec"
          :class="{ disabled: !canCreateExecution }"
          :disabled="!canCreateExecution"
          @click="createExecution"
        >
          Create Execution
        </button>
        <p v-if="createExecutionValidationMessage" class="helper-text compact-helper create-execution-helper">
          {{ createExecutionValidationMessage }}
        </p>
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
          <p class="helper-text compact-helper">Maximum file size: 10 MB.</p>
          <p v-if="inputFileError" class="helper-text compact-helper" style="color: #dc2626;">{{ inputFileError }}</p>
        </div>

        <aside v-if="selectedCanvasNode" class="config-panel">
          <div class="side-panel-header">
            <h3>{{ selectedCanvasNode.name }} Parameters</h3>
          </div>

          <div class="config-group">
            <span class="helper-text compact-helper">Select a model to configure its parameters. You can import a parameter configuration or create one manually and export it for future use.</span>
            <div v-if="isAlertTranslatorNode(selectedCanvasNode)" class="parameter-actions">
              <button type="button" class="btn-secondary compact-button" @click="openParametersFilePicker">
                Import Parameters
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
                :class="{ 'payload-context-field': key === 'payload_context_fields' || key === 'ttps_fields' }"
              >
                <label>{{ formatParamLabel(key as string) }}</label>

                <template v-if="key === 'ttps_fields'">
                  <div class="payload-header">
                    <span class="helper-text compact-helper">
                      Add one TTP field path or SIEM prefix per entry. Use a full field such as
                      <code>rule.mitre.id</code>, or a prefix such as
                      <code>attack</code> or <code>mitre</code> to extract keys like
                      <code>attack.t1003</code>, <code>attack.t1003.001</code> or <code>mitre.t1055</code>.
                    </span>

                    <button
                      type="button"
                      class="btn-add-field"
                      @click="addTtpField(selectedCanvasNode)"
                      title="Add field"
                    >
                      +
                    </button>
                  </div>

                  <div class="payload-fields">
                    <div
                      v-for="(_, index) in getTtpFields(selectedCanvasNode)"
                      :key="index"
                      class="payload-field-row"
                    >
                      <input
                        v-model="selectedCanvasNode.parameters.ttps_fields[index]"
                        type="text"
                        class="text-input"
                        placeholder="Example: rule.mitre.id or attack"
                        @blur="sanitizeTtpFieldsForNode(selectedCanvasNode)"
                      />

                      <button
                        type="button"
                        class="btn-remove-field"
                        @click="removeTtpField(selectedCanvasNode, index)"
                        title="Remove field"
                      >
                        x
                      </button>
                    </div>
                  </div>
                </template>

                <template v-else-if="key === 'payload_context_fields'">
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
                        @blur="sanitizePayloadContextFieldsForNode(selectedCanvasNode)"
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
            &nbsp;
            <button
              v-if="isAlertTranslatorNode(selectedCanvasNode)"
              type="button"
              class="btn-secondary compact-button"
              @click="exportSelectedParameters"
              > Export Parameters</button>
          </div>
          
        </aside>
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
