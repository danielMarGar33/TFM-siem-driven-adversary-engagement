<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import pipelinesData from '../assets/pipelines.json';
import modelsData from '../assets/models.json';

const route = useRoute();
const router = useRouter();

const simulationId = route.params.id as string;

const simulation = ref<any>(null);
const executionData = ref<any>(null);
const selectedTaskId = ref<string | null>(null);
const executionLogs = ref<any[]>([]);
const logsLoading = ref(false);
const showFinalResultsModal = ref(false);

const fixedPipeline = (pipelinesData as any[])[0];
const fixedModels = modelsData as any[];
const WEBHOOK_URL =
  localStorage.getItem('decision_engine_webhook_url') ||
  (import.meta as any).env?.VITE_WEBHOOK_URL ||
  'http://localhost:5000';

let localRunToken = 0;

const activePipeline = computed(() => simulation.value?.pipeline_snapshot || fixedPipeline);
const activeModels = computed(() => simulation.value?.models_snapshot || fixedModels);

const actualPipelineNodes = computed(() => {
  return activePipeline.value.pipeline_nodes.map((node: any, index: number) => {
    const model = activeModels.value.find((item: any) => item.id === node.node_type);

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
      x: 260 + index * 320,
      y: 220
    };
  });
});

const normalizeStatus = (status: string | undefined | null) => {
  const s = (status || '').toLowerCase();

  if (s === 'ready' || s === 'queued') return 'ready';
  if (s === 'running') return 'running';
  if (s === 'success' || s === 'finished') return 'success';
  if (s === 'failed' || s === 'error') return 'failed';
  if (s === 'paused') return 'paused';
  if (s === 'aborted' || s === 'stopped') return 'aborted';

  return s || 'ready';
};

const currentExecutionStatus = computed(() => {
  const rawStatus = executionData.value?.status || simulation.value?.status || 'Ready';
  return normalizeStatus(rawStatus);
});

const displayExecutionStatus = computed(() => {
  const status = currentExecutionStatus.value;

  if (status === 'ready') return 'Ready';
  if (status === 'running') return 'Running';
  if (status === 'success') return 'Finished';
  if (status === 'failed') return 'Failed';
  if (status === 'paused') return 'Paused';
  if (status === 'aborted') return 'Aborted';

  return 'Ready';
});

const canPlay = computed(() => {
  return !!simulation.value && ['ready', 'paused', 'failed', 'aborted'].includes(currentExecutionStatus.value);
});

const canPause = computed(() => !!simulation.value && currentExecutionStatus.value === 'running');
const canStop = computed(() => !!simulation.value && ['running', 'paused'].includes(currentExecutionStatus.value));
const canRestart = computed(() => !!simulation.value && ['success', 'failed', 'aborted'].includes(currentExecutionStatus.value));
const canDelete = computed(() => !!simulation.value && currentExecutionStatus.value !== 'running');

const loadSimulation = () => {
  const savedSims = localStorage.getItem('simulations_db');

  if (!savedSims) {
    simulation.value = null;
    return;
  }

  const simulations = JSON.parse(savedSims);
  simulation.value = simulations.find((sim: any) => sim.simulation_id === simulationId) || null;
};

const syncDatabase = () => {
  const savedSims = localStorage.getItem('simulations_db');

  if (!savedSims || !simulation.value) return;

  const simulations = JSON.parse(savedSims);
  const index = simulations.findIndex((sim: any) => sim.simulation_id === simulationId);

  if (index !== -1) {
    simulations[index] = simulation.value;
    localStorage.setItem('simulations_db', JSON.stringify(simulations));
  }
};

const loadExecutionData = async () => {
  if (!simulation.value?.execution_id) return;

  executionData.value = simulation.value.execution_data || null;

  if (executionData.value?.status) {
    simulation.value.status = displayExecutionStatus.value;
  }

  if (executionData.value?.output) {
    simulation.value.output = executionData.value.output;
  }

  syncDatabase();
};

const stopPolling = () => {
  localRunToken += 1;
};

const buildExpectedTaskId = (node: any) => {
  const modelPart = node.node_type || node.modelId || node.id;
  const rawNodePart = String(node.node_id || node.instanceId || node.id);
  const shortNodePart = rawNodePart.slice(-4);

  return `ejecutar_${modelPart}_${shortNodePart}`;
};

const loadTaskLogs = async (taskId: string) => {
  logsLoading.value = true;
  executionLogs.value = globalExecutionLogs.value;
  logsLoading.value = false;
};

const selectNodeAndLoadLogs = async (node: any) => {
  const taskId = buildExpectedTaskId(node);
  selectedTaskId.value = taskId;
  await loadTaskLogs(taskId);
};

const buildExecutionPayload = () => {
  const nodes = actualPipelineNodes.value.map((node: any) => ({
    id: String(node.node_id),
    modelId: node.node_type,
    name: node.node_name,
    inputs: node.inputs || [],
    outputs: node.outputs || [],
    parameters: node.parameters || {},
    execution: node.execution || {},
    outputConfig: node.outputConfig || {},
    script: node.script || null
  }));

  const edges = activePipeline.value.pipeline_connections.map((connection: any) => ({
    source: String(connection.source_node_id),
    target: String(connection.target_node_id),
    source_output: connection.source_output,
    target_input: connection.target_input
  }));

  return {
    pipelineName: activePipeline.value.pipeline_id,
    nodes,
    edges,
    input: simulation.value?.input || {},
    metadata: simulation.value?.metadata || {},
    output: simulation.value?.output || {}
  };
};

const getWebhookPath = (node: any) => {
  return node?.script || null;
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

const buildNamedInputs = (payload: any, node: any, previousOutput: any) => {
  const namedInputs: Record<string, any> = {};

  for (const inputName of node?.inputs || []) {
    if (inputName === 'Raw SIEM alert') {
      namedInputs[inputName] =
        payload.input['Raw SIEM alert'] ??
        payload.input.input_data ??
        payload.input.input_text ??
        null;
    } else if (inputName === 'Normalized alerts') {
      namedInputs[inputName] =
        previousOutput?.['Normalized alerts'] ??
        previousOutput?.alerts ??
        previousOutput ??
        null;
    }
  }

  if ((node.node_type || node.modelId || node.id) === 'm1') {
    namedInputs['Translator configuration'] =
      payload.input['Translator configuration'] ||
      payload.input.configuration_data ||
      payload.input.translator_configuration ||
      simulation.value?.metadata?.model_configuration?.translator_configuration ||
      payload.metadata?.model_configuration?.translator_configuration ||
      buildTranslatorConfiguration(node.parameters || {});
  }

  return namedInputs;
};

const buildHookPayload = (node: any, previousOutput: any) => {
  const payload = buildExecutionPayload();

  return {
    execution_id: simulation.value?.execution_id,
    simulation_id: simulation.value?.simulation_id,
    pipeline_id: simulation.value?.pipeline_id,
    pipeline_name: payload.pipelineName,
    node,
    inputs: buildNamedInputs(payload, node, previousOutput),
    input: payload.input,
    previous_output: previousOutput
  };
};

const createInitialLocalExecutionData = () => {
  const payload = buildExecutionPayload();
  const executionId = simulation.value?.execution_id || `LOCAL-${Date.now()}`;
  const now = new Date().toISOString();
  const logs: Record<string, any[]> = {};

  const steps = payload.nodes.map((node: any) => {
    const taskId = buildExpectedTaskId(node);

    logs[taskId] = [
      { timestamp: now, event: `Queued ${node.name}` },
      { timestamp: now, event: `Python script reference: ${node.script || 'not configured'}` }
    ];

    return {
      task_id: taskId,
      node_id: node.id,
      node_name: node.name,
      script: node.script,
      state: 'queued',
      started_at: null,
      finished_at: null
    };
  });

  return {
    execution_id: executionId,
    status: 'running',
    steps,
    logs,
    input: payload.input,
    output: payload.output || {}
  };
};

const handlePlay = async () => {
  if (!simulation.value || !canPlay.value) return;

  const runToken = ++localRunToken;
  const executionResult = createInitialLocalExecutionData();
  const modelOutputs: Record<string, any> = {};
  let previousOutput: any = buildExecutionPayload().input;

  simulation.value.execution_id = executionResult.execution_id;
  simulation.value.execution_data = executionResult;
  simulation.value.status = 'Running';
  executionData.value = executionResult;

  if (simulation.value.metadata) {
    simulation.value.metadata.updated_at = new Date().toISOString();
  }

  syncDatabase();

  for (const step of executionData.value.steps) {
    if (runToken !== localRunToken) return;

    const node = actualPipelineNodes.value.find((item: any) => String(item.node_id) === String(step.node_id));
    const webhookPath = getWebhookPath(node);
    const now = new Date().toISOString();
    step.state = 'running';
    step.started_at = now;
    executionData.value.logs[step.task_id].push({
      timestamp: now,
      event: `Calling ${webhookPath || 'unconfigured webhook'} for ${step.script || 'not configured'}`
    });
    syncDatabase();

    try {
      if (!webhookPath || !node) {
        throw new Error(`No webhook configured for ${step.script || step.node_name}`);
      }

      const response = await fetch(`${WEBHOOK_URL}${webhookPath}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(buildHookPayload(node, previousOutput))
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`${webhookPath} failed with status ${response.status}: ${errorText}`);
      }

      const result = await response.json();
      const finishedAt = new Date().toISOString();
      step.state = 'success';
      step.finished_at = finishedAt;
      modelOutputs[String(step.node_id)] = result;
      previousOutput = result.output || result.variables || result;
      executionData.value.logs[step.task_id].push({
        timestamp: finishedAt,
        event: `${step.node_name} completed.`
      });
      syncDatabase();
    } catch (error) {
      const failedAt = new Date().toISOString();
      step.state = 'failed';
      step.finished_at = failedAt;
      executionData.value.status = 'failed';
      executionData.value.logs[step.task_id].push({
        timestamp: failedAt,
        event: error instanceof Error ? error.message : String(error)
      });
      simulation.value.status = 'Failed';
      simulation.value.execution_data = executionData.value;
      syncDatabase();
      alert(`No se pudo ejecutar la pipeline: ${error instanceof Error ? error.message : String(error)}`);
      return;
    }
  }

  executionData.value.status = 'success';
  executionData.value.output = {
    model_outputs: modelOutputs,
    final_output: previousOutput,
    logs: executionData.value.logs
  };
  simulation.value.execution_data = executionData.value;
  simulation.value.output = executionData.value.output;
  simulation.value.status = 'Finished';

  if (simulation.value.metadata) {
    simulation.value.metadata.updated_at = new Date().toISOString();
  }

  syncDatabase();
  if (selectedTaskId.value) await loadTaskLogs(selectedTaskId.value);
  showFinalResultsModal.value = true;
};

const handlePause = () => {
  if (!simulation.value || !canPause.value) return;

  simulation.value.status = 'Paused';
  stopPolling();
  if (executionData.value) {
    executionData.value.status = 'paused';
    simulation.value.execution_data = executionData.value;
  }

  if (simulation.value.metadata) {
    simulation.value.metadata.updated_at = new Date().toISOString();
  }

  syncDatabase();
};

const handleStop = () => {
  if (!simulation.value || !canStop.value) return;

  if (!confirm('Are you sure you want to stop this execution?')) return;

  simulation.value.status = 'Aborted';
  stopPolling();
  if (executionData.value) {
    executionData.value.status = 'aborted';
    executionData.value.steps.forEach((step: any) => {
      if (step.state === 'queued' || step.state === 'running') {
        step.state = 'aborted';
        step.finished_at = new Date().toISOString();
      }
    });
    simulation.value.execution_data = executionData.value;
  }

  if (simulation.value.metadata) {
    simulation.value.metadata.updated_at = new Date().toISOString();
  }

  syncDatabase();
};

const handleRestart = () => {
  if (!simulation.value || !canRestart.value) return;

  simulation.value.execution_id = null;
  simulation.value.status = 'Ready';
  simulation.value.output = {
    model_outputs: {},
    final_output: null
  };
  simulation.value.execution_data = null;

  executionData.value = null;
  executionLogs.value = [];
  selectedTaskId.value = null;

  if (simulation.value.metadata) {
    simulation.value.metadata.updated_at = new Date().toISOString();
  }

  syncDatabase();
};

const handleDelete = () => {
  if (!canDelete.value) return;

  if (!confirm(`Are you sure you want to delete ${simulationId}?`)) return;

  const savedSims = localStorage.getItem('simulations_db');
  const simulations = savedSims ? JSON.parse(savedSims) : [];

  const updatedSimulations = simulations.filter(
    (sim: any) => sim.simulation_id !== simulationId
  );

  localStorage.setItem('simulations_db', JSON.stringify(updatedSimulations));
  router.push('/execution/simulations');
};

const getNodeStatusClass = (node: any) => {
  if (!executionData.value?.steps) return '';

  const expectedTaskId = buildExpectedTaskId(node);
  const step = executionData.value.steps.find(
    (item: any) => item.task_id === expectedTaskId
  );

  if (!step?.state) return '';

  const status = normalizeStatus(step.state);

  if (status === 'success') return 'success';
  if (status === 'running') return 'running';
  if (status === 'failed') return 'failed';
  if (status === 'ready') return 'ready';

  return '';
};

const aggregatedData = computed(() => {
  const data = {
    inputs: [] as string[],
    outputs: [] as string[],
    params: [] as string[]
  };

  actualPipelineNodes.value.forEach((node: any) => {
    if (node.inputs) data.inputs.push(...node.inputs);
    if (node.outputs) data.outputs.push(...node.outputs);
    if (node.parameters) data.params.push(...Object.keys(node.parameters));
  });

  data.inputs = [...new Set(data.inputs)];
  data.outputs = [...new Set(data.outputs)];
  data.params = [...new Set(data.params)];

  return data;
});

const formattedInput = computed(() => {
  return JSON.stringify(simulation.value?.input || {}, null, 2);
});

const formattedOutput = computed(() => {
  return JSON.stringify(simulation.value?.output || {}, null, 2);
});

const finalResultPayload = computed(() => {
  return (
    executionData.value?.output?.final_output ||
    simulation.value?.output?.final_output ||
    null
  );
});

const finalResultRows = computed(() => {
  const payload = finalResultPayload.value;

  if (!payload) return [];

  const recommendation = payload['MITRE Engage recommendation'] || payload;

  if (Array.isArray(recommendation?.approaches)) {
    return recommendation.approaches.flatMap((approach: any) => {
      return (approach.activities || []).map((activity: any) => ({
        Goal: recommendation.goal_name || recommendation.goal_id || '-',
        Approach: approach.approach_name || approach.approach_id || '-',
        Activity: activity.activity_name || activity.activity_id || '-',
        Status: activity.recommendation?.status || '-',
        Reason: activity.recommendation?.reason || '-',
        'CVSS Base': activity.activity_exposure?.cvss_base_score ?? '-',
        Impact: activity.activity_exposure?.impact_subscore ?? '-',
        Exploitability: activity.activity_exposure?.exploitability_subscore ?? '-'
      }));
    });
  }

  if (Array.isArray(payload)) {
    return payload.map((item) => (typeof item === 'object' && item !== null ? item : { Value: item }));
  }

  if (typeof payload === 'object') {
    return Object.entries(payload).map(([field, value]) => ({
      Field: field,
      Value: typeof value === 'object' && value !== null ? JSON.stringify(value, null, 2) : value
    }));
  }

  return [{ Value: payload }];
});

const finalResultColumns = computed(() => {
  const columns = new Set<string>();

  finalResultRows.value.forEach((row: any) => {
    Object.keys(row || {}).forEach((key) => columns.add(key));
  });

  return [...columns];
});

const selectedExecutionNode = computed(() => {
  if (!selectedTaskId.value) return actualPipelineNodes.value[0] || null;

  return actualPipelineNodes.value.find(
    (node: any) => buildExpectedTaskId(node) === selectedTaskId.value
  ) || null;
});

const getNodeOutput = (node: any) => {
  if (!node) return null;

  const nodeId = String(node.node_id || node.id);
  const outputs =
    executionData.value?.output?.model_outputs ||
    simulation.value?.output?.model_outputs ||
    {};

  return outputs[nodeId] || null;
};

const getPreviousNodeOutput = (node: any) => {
  const index = actualPipelineNodes.value.findIndex(
    (item: any) => String(item.node_id) === String(node?.node_id)
  );

  if (index <= 0) return buildExecutionPayload().input;

  const previousNode = actualPipelineNodes.value[index - 1];
  const previousOutput = getNodeOutput(previousNode);

  return previousOutput?.output || previousOutput?.variables || previousOutput || null;
};

const selectedNodeInput = computed(() => {
  if (!selectedExecutionNode.value) return {};

  return buildNamedInputs(
    buildExecutionPayload(),
    selectedExecutionNode.value,
    getPreviousNodeOutput(selectedExecutionNode.value)
  );
});

const selectedNodeParameters = computed(() => selectedExecutionNode.value?.parameters || {});

const selectedNodeOutput = computed(() => {
  const output = getNodeOutput(selectedExecutionNode.value);
  return output?.output || output?.variables || output || {};
});

const selectedNodeName = computed(() => {
  return selectedExecutionNode.value?.name || selectedExecutionNode.value?.node_name || 'Selected model';
});

const formatDataValue = (value: any) => {
  if (value === null || value === undefined || value === '') return '-';
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }

  return JSON.stringify(value, null, 2);
};

const isComplexDataValue = (value: any) => {
  return typeof value === 'object' && value !== null;
};

const objectEntries = (value: any) => {
  if (!value || typeof value !== 'object') return [];
  const hiddenInputKeys = new Set([
    'Translator configuration',
    'configuration_data',
    'translator_configuration'
  ]);

  return Object.entries(value).filter(([key]) => !hiddenInputKeys.has(key));
};

const globalExecutionLogs = computed(() => {
  const logsByTask =
    executionData.value?.logs ||
    simulation.value?.output?.logs ||
    simulation.value?.execution_data?.logs ||
    {};

  return Object.entries(logsByTask).flatMap(([taskId, lines]: [string, any]) => {
    return (Array.isArray(lines) ? lines : []).map((line) => {
      if (typeof line === 'string') {
        return {
          task_id: taskId,
          event: line
        };
      }

      return {
        task_id: taskId,
        ...line
      };
    });
  }).sort((a: any, b: any) => {
    return new Date(a.timestamp || 0).getTime() - new Date(b.timestamp || 0).getTime();
  });
});

const showSearch = ref(false);
const canvasSearchQuery = ref('');
const zoomLevel = ref(1);
const canvasPanelRef = ref<HTMLElement | null>(null);
const executionCanvasRef = ref<HTMLElement | null>(null);
const isExecutionCanvasDragging = ref(false);
const suppressNextExecutionNodeClick = ref(false);
const executionDragStart = ref({
  x: 0,
  y: 0,
  scrollLeft: 0,
  scrollTop: 0
});

const zoomIn = () => {
  zoomLevel.value = Math.min(zoomLevel.value + 0.1, 2);
};

const zoomOut = () => {
  zoomLevel.value = Math.max(zoomLevel.value - 0.1, 0.4);
};

const toggleFullscreen = () => {
  if (!document.fullscreenElement) {
    canvasPanelRef.value?.requestFullscreen().catch(() => {});
  } else {
    document.exitFullscreen();
  }
};

const isNodeDimmed = (nodeName: string) => {
  if (!canvasSearchQuery.value) return false;

  return !nodeName
    .toLowerCase()
    .includes(canvasSearchQuery.value.toLowerCase());
};

const goToDesign = () => {
  router.push(`/detailed/pipelines/${activePipeline.value.pipeline_id}/edit`);
};

const startExecutionCanvasDrag = (event: PointerEvent) => {
  if (!executionCanvasRef.value || event.button !== 0) return;
  if ((event.target as HTMLElement).closest('.node-box')) return;

  isExecutionCanvasDragging.value = false;
  suppressNextExecutionNodeClick.value = false;
  executionDragStart.value = {
    x: event.clientX,
    y: event.clientY,
    scrollLeft: executionCanvasRef.value.scrollLeft,
    scrollTop: executionCanvasRef.value.scrollTop
  };

  executionCanvasRef.value.setPointerCapture(event.pointerId);
};

const dragExecutionCanvas = (event: PointerEvent) => {
  if (!executionCanvasRef.value || !(event.buttons & 1)) return;

  const deltaX = event.clientX - executionDragStart.value.x;
  const deltaY = event.clientY - executionDragStart.value.y;

  if (!isExecutionCanvasDragging.value && Math.hypot(deltaX, deltaY) < 4) return;

  isExecutionCanvasDragging.value = true;
  suppressNextExecutionNodeClick.value = true;
  executionCanvasRef.value.scrollLeft = executionDragStart.value.scrollLeft - deltaX;
  executionCanvasRef.value.scrollTop = executionDragStart.value.scrollTop - deltaY;
};

const stopExecutionCanvasDrag = (event: PointerEvent) => {
  executionCanvasRef.value?.releasePointerCapture(event.pointerId);
  isExecutionCanvasDragging.value = false;
};

const handleExecutionNodeClick = async (node: any) => {
  if (suppressNextExecutionNodeClick.value) {
    suppressNextExecutionNodeClick.value = false;
    return;
  }

  await selectNodeAndLoadLogs(node);
};

onMounted(async () => {
  loadSimulation();

  if (simulation.value?.execution_id) {
    await loadExecutionData();
  }

  if (actualPipelineNodes.value.length > 0) {
    await selectNodeAndLoadLogs(actualPipelineNodes.value[0]);
  }

});

onUnmounted(() => {
  stopPolling();
});
</script>

<template>
  <div class="detailed-executor-view">

    <div class="top-nav">
      <button class="btn-back" @click="$router.back()">&lt; Back</button>
      <div>
        <button class="btn-primary" @click="goToDesign">New Execution</button>
        &nbsp;
        <button class="btn-primary" @click="$router.push('/execution/simulations')">Execution List</button>
      </div>
    </div>

    <div class="header-actions">
      <h2>
        {{ simulationId }}
        <span class="text-gray fw-normal">
          ({{ simulation?.mission_characterization_id || activePipeline.mission_characterization_id }})
        </span>
      </h2>

      <div class="action-buttons">
        <button class="btn-action" :class="{ disabled: !canPlay }" @click="handlePlay">
          <img src="/actions/Play.svg" alt="Play" />
          Play
        </button>

        <button class="btn-action" :class="{ disabled: !canPause }" @click="handlePause">
          <img src="/actions/Pause.svg" alt="Pause" />
          Pause
        </button>

        <button class="btn-action" :class="{ disabled: !canStop }" @click="handleStop">
          <img src="/actions/Stop.svg" alt="Stop" />
          Stop
        </button>

        <button class="btn-action" :class="{ disabled: !canRestart }" @click="handleRestart">
          <img src="/actions/Restart.svg" alt="Restart" />
          Restart
        </button>

        <button class="btn-action" :class="{ disabled: !canDelete }" @click="handleDelete">
          <img src="/actions/Delete.svg" alt="Delete" />
          Delete
        </button>
      </div>
    </div>

    <div v-if="!simulation" class="panel">
      <h3>Execution not found</h3>
      <p>No execution was found in localStorage for ID {{ simulationId }}.</p>
    </div>

    <div v-else class="main-grid">
      <div class="left-col">
        <div class="panel canvas-panel" ref="canvasPanelRef">
          <h3>Fixed Execution Pipeline</h3>

          <div class="canvas-controls">
            <div class="search-wrapper">
              <button class="search-icon" @click="showSearch = !showSearch">
                <img src="/Search.svg" alt="Search" />
              </button>

              <input
                v-if="showSearch"
                v-model="canvasSearchQuery"
                type="text"
                placeholder="Find model..."
                class="canvas-search-input"
              />
            </div>

            <button @click="zoomIn">+</button>
            <button @click="zoomOut">-</button>
            <button @click="toggleFullscreen">⛶</button>
          </div>

          <div
            class="mock-canvas"
            :class="{ dragging: isExecutionCanvasDragging }"
            ref="executionCanvasRef"
            @pointerdown="startExecutionCanvasDrag"
            @pointermove="dragExecutionCanvas"
            @pointerup="stopExecutionCanvasDrag"
            @pointercancel="stopExecutionCanvasDrag"
            @pointerleave="stopExecutionCanvasDrag"
          >
            <div
              :style="{
                transform: `scale(${zoomLevel})`,
                transformOrigin: 'top left',
                transition: 'transform 0.2s ease',
                minHeight: '100%',
                display: 'flex',
                alignItems: 'center'
              }"
            >
              <div class="node-circle start"></div>

              <template
                v-for="(node, index) in actualPipelineNodes"
                :key="node.instanceId || node.id || index"
              >
                <div class="line"></div>

                <div
                  class="node-box"
                  :class="[
                    getNodeStatusClass(node),
                    {
                      'selected-node': selectedTaskId === buildExpectedTaskId(node),
                      'dimmed-node': isNodeDimmed(node.name || node.node_name)
                    }
                  ]"
                  @click="handleExecutionNodeClick(node)"
                >
                  {{ node.name || node.node_name }}
                </div>
              </template>
            </div>
          </div>
        </div>

        <div class="bottom-row">
          <div class="panel chart-panel">
            <div class="execution-data-header">
              <h3>Execution Data</h3>
              <span>{{ selectedNodeName }}</span>
            </div>

            <div class="model-data-grid">
              <section class="model-data-card">
                <div class="model-data-card-header">
                  <span class="model-data-kicker">Input</span>
                </div>

                <div v-if="objectEntries(selectedNodeInput).length > 0" class="model-data-list">
                  <div
                    v-for="[key, value] in objectEntries(selectedNodeInput)"
                    :key="'input-' + key"
                    class="model-data-row"
                  >
                    <label>{{ key }}</label>
                    <pre v-if="isComplexDataValue(value)">{{ formatDataValue(value) }}</pre>
                    <span v-else>{{ formatDataValue(value) }}</span>
                  </div>
                </div>

                <p v-else class="empty-data-note">No input data for this model.</p>
              </section>

              <section class="model-data-card">
                <div class="model-data-card-header">
                  <span class="model-data-kicker">Parameters</span>
                </div>

                <div v-if="objectEntries(selectedNodeParameters).length > 0" class="model-data-list compact">
                  <div
                    v-for="[key, value] in objectEntries(selectedNodeParameters)"
                    :key="'parameter-' + key"
                    class="model-data-row"
                  >
                    <label>{{ key }}</label>
                    <pre v-if="isComplexDataValue(value)">{{ formatDataValue(value) }}</pre>
                    <span v-else>{{ formatDataValue(value) }}</span>
                  </div>
                </div>

                <p v-else class="empty-data-note">No parameters configured.</p>
              </section>

              <section class="model-data-card output-card">
                <div class="model-data-card-header">
                  <span class="model-data-kicker">Output</span>
                </div>

                <div v-if="objectEntries(selectedNodeOutput).length > 0" class="model-data-list">
                  <div
                    v-for="[key, value] in objectEntries(selectedNodeOutput)"
                    :key="'output-' + key"
                    class="model-data-row"
                  >
                    <label>{{ key }}</label>
                    <pre v-if="isComplexDataValue(value)">{{ formatDataValue(value) }}</pre>
                    <span v-else>{{ formatDataValue(value) }}</span>
                  </div>
                </div>

                <p v-else class="empty-data-note">No output yet for this model.</p>
              </section>
            </div>
          </div>
        </div>
      </div>

      <div class="right-col panel">
        <h3>Execution Overview</h3>

        <div class="data-group">
          <label>Execution Status</label>
          <div>
            <span class="status-badge" :class="displayExecutionStatus.toLowerCase()">
              {{ displayExecutionStatus }}
            </span>
          </div>
        </div>

        <button
          v-if="finalResultPayload"
          class="btn-primary final-results-button"
          @click="showFinalResultsModal = true"
        >
          View Final Results
        </button>

        <div class="data-group">
          <label>Input Data Types</label>
          <div class="tags-container">
            <span
              v-for="tag in aggregatedData.inputs"
              :key="tag"
              class="data-tag"
            >
              {{ tag }}
            </span>
          </div>
        </div>

        <div class="data-group">
          <label>Output Data Types</label>
          <div class="tags-container">
            <span
              v-for="tag in aggregatedData.outputs"
              :key="tag"
              class="data-tag"
            >
              {{ tag }}
            </span>
          </div>
        </div>

        <div class="data-group">
          <label>Parameters</label>
          <div class="tags-container">
            <span
              v-for="tag in aggregatedData.params"
              :key="tag"
              class="data-tag"
            >
              {{ tag }}
            </span>
          </div>
        </div>

        <div class="data-group logs-group">
          <label>Execution Logs</label>

          <div class="logs-container">
            <div v-if="logsLoading" class="log-loading">
              Loading logs...
            </div>

            <template v-else-if="executionLogs.length > 0">
              <div
                v-for="(line, index) in executionLogs"
                :key="index"
                class="log-line"
              >
                <template v-if="typeof line === 'string'">
                  {{ line }}
                </template>

                <template v-else>
                  <span class="log-time">
                    {{ line.timestamp ? line.timestamp + ' ' : '' }}
                  </span>
                  <span v-if="line.task_id" class="log-task">
                    {{ line.task_id }}
                  </span>
                  {{ line.event || JSON.stringify(line) }}
                </template>
              </div>
            </template>

            <div v-else class="log-empty">
              No logs available for this task. Select a node to view logs.
            </div>
          </div>
        </div>
      </div>
    </div>

    <Teleport to="body">
      <div v-if="showFinalResultsModal" class="final-results-backdrop">
        <section class="final-results-modal">
          <div class="final-results-header">
            <div>
              <span class="final-results-eyebrow">Pipeline completed</span>
              <h3>Final Results</h3>
            </div>

            <button class="final-results-close" @click="showFinalResultsModal = false">
              x
            </button>
          </div>

          <div v-if="finalResultRows.length > 0" class="final-results-table-wrapper">
            <table class="final-results-table">
              <thead>
                <tr>
                  <th v-for="column in finalResultColumns" :key="column">
                    {{ column }}
                  </th>
                </tr>
              </thead>

              <tbody>
                <tr v-for="(row, rowIndex) in finalResultRows" :key="rowIndex">
                  <td v-for="column in finalResultColumns" :key="column">
                    <span
                      v-if="column === 'Status'"
                      class="result-status-pill"
                      :class="String(row[column] || '').toLowerCase().replace('_', '-')"
                    >
                      {{ row[column] || '-' }}
                    </span>

                    <span v-else>
                      {{ formatDataValue(row[column]) }}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div v-else class="final-results-empty">
            No final output is available yet.
          </div>
        </section>
      </div>
    </Teleport>
  </div>
</template>

<style scoped src="./DetailedViewExecutor.css"></style>
