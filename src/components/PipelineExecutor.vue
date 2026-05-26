<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import pipelinesData from '../assets/pipelines.json';
import modelsData from '../assets/models.json';

const router = useRouter();

const simulationsList = ref<any[]>([]);
const searchQuery = ref('');
const selectedSimulationId = ref<string | null>(null);

const showToast = ref(false);
const toastSimulationId = ref('');
const toastAction = ref('');

const fixedPipeline = (pipelinesData as any[])[0];
const fixedModels = modelsData as any[];
const WEBHOOK_URL =
  localStorage.getItem('decision_engine_webhook_url') ||
  (import.meta as any).env?.VITE_WEBHOOK_URL ||
  'http://localhost:5000';

onMounted(() => {
  loadSimulations();
});

const loadSimulations = () => {
  const savedSims = localStorage.getItem('simulations_db');

  if (!savedSims) {
    simulationsList.value = [];
    return;
  }

  try {
    simulationsList.value = JSON.parse(savedSims).sort((a: any, b: any) => {
      return (
        new Date(b.metadata?.created_at || 0).getTime() -
        new Date(a.metadata?.created_at || 0).getTime()
      );
    });
  } catch (error) {
    console.error('Error parsing simulations:', error);
    simulationsList.value = [];
  }
};

const syncDatabase = () => {
  localStorage.setItem('simulations_db', JSON.stringify(simulationsList.value));
};

const normalizeStatus = (status: string | undefined | null) => {
  const s = (status || '').toLowerCase();

  if (s === 'queued' || s === 'ready') return 'Ready';
  if (s === 'success' || s === 'finished') return 'Finished';
  if (s === 'failed' || s === 'error') return 'Failed';
  if (s === 'aborted' || s === 'stopped') return 'Aborted';
  if (!s) return 'Ready';

  return s.charAt(0).toUpperCase() + s.slice(1);
};

const filteredSimulations = computed(() => {
  if (!searchQuery.value) return simulationsList.value;

  const query = searchQuery.value.toLowerCase();

  return simulationsList.value.filter((sim) => {
    return (
      sim.simulation_id?.toLowerCase().includes(query) ||
      sim.pipeline_id?.toLowerCase().includes(query) ||
      sim.input?.execution_name?.toLowerCase().includes(query)
    );
  });
});

const selectedSim = computed(() => {
  return simulationsList.value.find(
    (sim) => sim.simulation_id === selectedSimulationId.value
  );
});

const currentExecutionStatus = computed(() => {
  return (selectedSim.value?.status || '').toLowerCase();
});

const canPlay = computed(() => {
  return !!selectedSim.value && ['ready', 'paused', 'failed', 'aborted'].includes(currentExecutionStatus.value);
});

const canPause = computed(() => !!selectedSim.value && currentExecutionStatus.value === 'running');
const canStop = computed(() => !!selectedSim.value && ['running', 'paused'].includes(currentExecutionStatus.value));
const canRestart = computed(() => !!selectedSim.value && ['finished', 'failed', 'aborted'].includes(currentExecutionStatus.value));
const canDelete = computed(() => !!selectedSim.value && currentExecutionStatus.value !== 'running');

const toggleSelection = (id: string) => {
  selectedSimulationId.value =
    selectedSimulationId.value === id ? null : id;
};

const formatDate = (dateString: string) => {
  if (!dateString) return '-';

  const options: Intl.DateTimeFormatOptions = {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  };

  return new Date(dateString).toLocaleDateString('en-US', options);
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

const buildExecutionPayload = (sim: any) => {
  const pipelineSnapshot = sim.pipeline_snapshot || fixedPipeline;
  const modelsSnapshot = sim.models_snapshot || fixedModels;

  const nodes = pipelineSnapshot.pipeline_nodes.map((node: any) => {
    const model = modelsSnapshot.find((item: any) => item.id === node.node_type);

    return {
      id: String(node.node_id),
      modelId: node.node_type,
      name: node.node_name,
      inputs: model?.inputs || [],
      outputs: model?.outputs || [],
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
      script: model?.script || model?.execution_path || null
    };
  });

  const edges = pipelineSnapshot.pipeline_connections.map((connection: any) => ({
    source: String(connection.source_node_id),
    target: String(connection.target_node_id),
    source_output: connection.source_output,
    target_input: connection.target_input
  }));

  return {
    pipelineName: pipelineSnapshot.pipeline_id,
    nodes,
    edges,
    input: sim.input || {},
    metadata: sim.metadata || {},
    output: sim.output || {}
  };
};

const buildExpectedTaskId = (node: any) => {
  return `ejecutar_${node.modelId}_${String(node.id).slice(-4)}`;
};

const getWebhookPath = (node: any) => {
  return node.script || null;
};

const buildNamedInputs = (payload: any, node: any, previousOutput: any) => {
  const namedInputs: Record<string, any> = {};

  for (const inputName of node.inputs || []) {
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

  if (node.modelId === 'm1') {
    namedInputs['Translator configuration'] =
      payload.input['Translator configuration'] ||
      payload.input.configuration_data ||
      payload.input.translator_configuration ||
      sim.metadata?.model_configuration?.translator_configuration ||
      payload.metadata?.model_configuration?.translator_configuration ||
      buildTranslatorConfiguration(node.parameters || {});
  }

  return namedInputs;
};

const buildHookPayload = (sim: any, payload: any, node: any, previousOutput: any) => {
  return {
    execution_id: sim.execution_id,
    simulation_id: sim.simulation_id,
    pipeline_id: sim.pipeline_id,
    pipeline_name: payload.pipelineName,
    node,
    inputs: buildNamedInputs(payload, node, previousOutput),
    input: payload.input,
    previous_output: previousOutput
  };
};

const runWebhookPipeline = async (sim: any) => {
  const payload = buildExecutionPayload(sim);
  const executionId = sim.execution_id || `HOOK-${Date.now()}`;
  const now = new Date().toISOString();
  const logs: Record<string, any[]> = {};
  const output: Record<string, any> = {};
  let previousOutput = payload.input;

  const steps = [];

  for (const node of payload.nodes) {
    const taskId = buildExpectedTaskId(node);
    const webhookPath = getWebhookPath(node);

    logs[taskId] = [
      { timestamp: now, event: `Prepared ${node.name}` },
      { timestamp: now, event: `Calling webhook ${webhookPath || 'not configured'} for ${node.script || 'unknown script'}` }
    ];

    const step = {
      task_id: taskId,
      node_id: node.id,
      node_name: node.name,
      script: node.script,
      webhook: webhookPath,
      state: 'running',
      started_at: now,
      finished_at: null as string | null
    };

    steps.push(step);

    if (!webhookPath) {
      throw new Error(`No webhook configured for ${node.script || node.name}`);
    }

    const response = await fetch(`${WEBHOOK_URL}${webhookPath}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(buildHookPayload(sim, payload, node, previousOutput))
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`${webhookPath} failed with status ${response.status}: ${errorText}`);
    }

    const result = await response.json();
    const finishedAt = new Date().toISOString();
    step.state = 'success';
    step.finished_at = finishedAt;
    output[node.id] = result;
    previousOutput = result.output || result.variables || result;
    logs[taskId].push({ timestamp: finishedAt, event: `${node.name} completed.` });
  }

  return {
    execution_id: executionId,
    status: 'success',
    steps,
    logs,
    input: payload.input,
    output: {
      model_outputs: output,
      final_output: previousOutput,
      logs
    }
  };
};

const handlePlay = async () => {
  if (!canPlay.value || !selectedSim.value) return;

  selectedSim.value.status = 'Running';

  if (selectedSim.value.metadata) {
    selectedSim.value.metadata.updated_at = new Date().toISOString();
  }

  syncDatabase();

  try {
    const executionResult = await runWebhookPipeline(selectedSim.value);

    selectedSim.value.execution_id = executionResult.execution_id;
    selectedSim.value.execution_data = executionResult;
    selectedSim.value.output = executionResult.output;
    selectedSim.value.status = normalizeStatus(executionResult.status);
  } catch (error) {
    console.error('Webhook execution failed:', error);
    selectedSim.value.status = 'Failed';
    selectedSim.value.execution_data = {
      execution_id: selectedSim.value.execution_id || `HOOK-${Date.now()}`,
      status: 'failed',
      error: error instanceof Error ? error.message : String(error)
    };
    alert(`No se pudo ejecutar la pipeline: ${error instanceof Error ? error.message : String(error)}`);
  }

  if (selectedSim.value.metadata) {
    selectedSim.value.metadata.updated_at = new Date().toISOString();
  }

  syncDatabase();
};

const handlePause = () => {
  if (!canPause.value || !selectedSim.value) return;

  selectedSim.value.status = 'Paused';

  if (selectedSim.value.metadata) {
    selectedSim.value.metadata.updated_at = new Date().toISOString();
  }

  syncDatabase();
};

const handleStop = () => {
  if (!canStop.value || !selectedSim.value) return;

  selectedSim.value.status = 'Aborted';

  if (selectedSim.value.metadata) {
    selectedSim.value.metadata.updated_at = new Date().toISOString();
  }

  syncDatabase();
};

const handleRestart = () => {
  if (!canRestart.value || !selectedSim.value) return;

  selectedSim.value.execution_id = null;
  selectedSim.value.status = 'Ready';
  selectedSim.value.output = {
    model_outputs: {},
    final_output: null
  };
  selectedSim.value.execution_data = null;

  if (selectedSim.value.metadata) {
    selectedSim.value.metadata.updated_at = new Date().toISOString();
  }

  syncDatabase();
};

const handleDelete = () => {
  if (!canDelete.value || !selectedSim.value) return;

  const idToDelete = selectedSimulationId.value;

  if (!confirm(`Are you sure you want to delete ${idToDelete}?`)) return;

  simulationsList.value = simulationsList.value.filter(
    (sim) => sim.simulation_id !== idToDelete
  );

  selectedSimulationId.value = null;
  syncDatabase();

  toastSimulationId.value = idToDelete as string;
  toastAction.value = 'deleted';
  showToast.value = true;

  setTimeout(() => {
    showToast.value = false;
  }, 3500);
};

const goToDetails = (id: string) => {
  router.push(`/execution/simulations/${id}`);
};

const goToDesign = () => {
  router.push(`/detailed/pipelines/${fixedPipeline.pipeline_id}/edit`);
};
</script>

<template>
  <div class="executor-view">

    <div class="top-nav">
      <button class="btn-back" @click="$router.back()">&lt; Back</button>
      <button class="btn-primary" @click="goToDesign">New Execution</button>
    </div>

    <div class="toolbar-section">
      <div class="search-input">
        <input
          type="text"
          placeholder="Search by Execution ID, Pipeline ID or name..."
          v-model="searchQuery"
        />
        <span class="search-icon">
          <img src="/Search.svg" alt="Search" />
        </span>
      </div>

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

    <div class="table-container">
      <table class="data-grid">
        <thead>
          <tr>
            <th>Execution ID</th>
            <th>Name</th>
            <th>Pipeline ID</th>
            <th>Created At</th>
            <th>Status</th>
          </tr>
        </thead>

        <tbody>
          <tr v-if="filteredSimulations.length === 0">
            <td colspan="5" class="empty-state">No executions found.</td>
          </tr>

          <tr
            v-for="sim in filteredSimulations"
            :key="sim.simulation_id"
            :class="{ 'selected-row': selectedSimulationId === sim.simulation_id }"
            @click="toggleSelection(sim.simulation_id)"
            @dblclick="goToDetails(sim.simulation_id)"
          >
            <td class="fw-bold text-teal">{{ sim.simulation_id }}</td>
            <td>{{ sim.input?.execution_name || '-' }}</td>
            <td>{{ sim.pipeline_id }}</td>
            <td class="text-gray">{{ formatDate(sim.metadata?.created_at) }}</td>
            <td>
              <span class="status-badge" :class="sim.status?.toLowerCase()">
                {{ sim.status }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <Teleport to="body">
      <transition name="toast-slide">
        <div v-if="showToast" class="success-toast">
          <div class="toast-content">
            <h4>Success</h4>
            <p><strong>{{ toastSimulationId }}</strong> {{ toastAction }}</p>
          </div>
          <button class="toast-close" @click="showToast = false">✕</button>
        </div>
      </transition>
    </Teleport>
  </div>
</template>

<style scoped src="./PipelineExecutor.css"></style>
