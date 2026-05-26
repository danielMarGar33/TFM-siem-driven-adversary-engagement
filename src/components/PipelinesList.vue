<script setup lang="ts">
import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import PipelineCard from './PipelineCard.vue';
import pipelinesData from '../assets/pipelines.json';

const router = useRouter();

const pipelinesList = ref<any[]>(
  (pipelinesData as any[]).map((pipeline) => ({
    ...pipeline,
    is_readonly: true
  }))
);

const searchQuery = ref('');
const selectedPipelineId = ref<string | null>(
  pipelinesList.value[0]?.pipeline_id || null
);

const showConfigBuilder = ref(false);

const filteredPipelines = computed(() => {
  if (!searchQuery.value) return pipelinesList.value;

  const query = searchQuery.value.toLowerCase();

  return pipelinesList.value.filter((pipeline) => {
    const id = pipeline.pipeline_id || '';
    const description = pipeline.pipeline_description || '';
    const mission = pipeline.mission_characterization_id || '';

    return (
      id.toLowerCase().includes(query) ||
      description.toLowerCase().includes(query) ||
      mission.toLowerCase().includes(query)
    );
  });
});

const toggleSelection = (id: string) => {
  selectedPipelineId.value = selectedPipelineId.value === id ? null : id;
};

const handleDoubleClick = (id: string) => {
  router.push(`/detailed/pipelines/${id}/edit`);
};
</script>

<template>
  <div class="view-container">
     <div class="header-section">
       <div class="header-info">
         <h1 class="header-title">Welcome to the Decision Engine platform</h1>
         <p class="header-description">
           Browse and manage your pipelines.
         </p>
       </div>
     </div>
    <div class="toolbar-section">
      <div class="search-input">
        <input
          type="text"
          placeholder="Search pipeline..."
          v-model="searchQuery"
        />

        <span class="search-icon">
          <img src="/Search.svg" alt="Search" />
        </span>
      </div>
    </div>

    <div class="content-grid">
      <PipelineCard
        v-for="pipeline in filteredPipelines"
        :key="pipeline.pipeline_id"
        :pipeline="pipeline"
        :is-selected="selectedPipelineId === pipeline.pipeline_id"
        @seleccionar="toggleSelection(pipeline.pipeline_id)"
        @dblclick="handleDoubleClick(pipeline.pipeline_id)"
      />
    </div>
  </div>
</template>

<style scoped src="./PipelinesList.css"></style>
