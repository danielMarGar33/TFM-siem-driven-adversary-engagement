<script setup lang="ts">
import { ref } from 'vue';

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'imported'): void; 
}>();

const isDragging = ref(false);
const fileError = ref('');
const selectedFile = ref<File | null>(null);
const MAX_SIZE_MB = 10;

const onDragOver = (e: DragEvent) => { e.preventDefault(); isDragging.value = true; };
const onDragLeave = () => { isDragging.value = false; };
const onDrop = (e: DragEvent) => { e.preventDefault(); isDragging.value = false; if (e.dataTransfer?.files?.length) validateAndSetFile(e.dataTransfer.files[0]); };
const onFileSelect = (e: Event) => { const target = e.target as HTMLInputElement; if (target.files?.length) validateAndSetFile(target.files[0]); };

const validateAndSetFile = (file: File) => {
  fileError.value = '';
  const validExtensions = ['.json', '.xml'];
  const fileName = file.name.toLowerCase();
  
  if (!validExtensions.some(ext => fileName.endsWith(ext)) && !['application/json', 'text/xml'].includes(file.type)) {
    fileError.value = 'Formato no soportado. Solo .json o .xml';
    return;
  }

  if (file.size > MAX_SIZE_MB * 1024 * 1024) {
    fileError.value = `El archivo excede ${MAX_SIZE_MB}MB`;
    return;
  }
  selectedFile.value = file;
};

// --- LÓGICA DE IMPORTACIÓN CON TRADUCTOR (MAPPER) AVANZADO ---
const handleSave = () => {
  if (!selectedFile.value) return;
  if (!selectedFile.value.name.toLowerCase().endsWith('.json')) {
    fileError.value = "Por el momento solo soportamos importar archivos .json";
    return;
  }

  const reader = new FileReader();
  
  reader.onload = (e) => {
    try {
      const content = e.target?.result as string;
      const parsedData = JSON.parse(content);

      const savedData = localStorage.getItem('pipelines_db');
      let currentPipelines = savedData ? JSON.parse(savedData) : [];

      const pipelinesToImport = Array.isArray(parsedData) ? parsedData : [parsedData];

      pipelinesToImport.forEach(newPipeline => {
        // 1. Evitar IDs duplicados
        let baseId = newPipeline.pipeline_id || 'IMPORTED-PIPELINE';
        let newId = baseId;
        let counter = 1;
        while (currentPipelines.some((p: any) => p.pipeline_id === newId)) {
          newId = `${baseId} (${counter})`;
          counter++;
        }
        newPipeline.pipeline_id = newId;
        
        // 2. Etiqueta de importado
        if (!newPipeline.metadata) newPipeline.metadata = {};
        newPipeline.metadata.tags = ["imported"];

        // 3. TRADUCCIÓN DE NODOS (Para que sean "Cajas Buenas" en el UI)
        if (newPipeline.pipeline_nodes && Array.isArray(newPipeline.pipeline_nodes)) {
          let currentX = 150; 
          const startY = 250; 

          newPipeline.pipeline_nodes = newPipeline.pipeline_nodes.map((node: any) => {
            const uiNode = { ...node };
            
            // A. IDs y Nombres básicos
            uiNode.instanceId = uiNode.instanceId || uiNode.node_id || (Date.now() + Math.random());
            uiNode.name = uiNode.name || uiNode.node_name || 'Unknown Node';
            
            // B. Posiciones en el lienzo
            if (uiNode.x === undefined || uiNode.y === undefined) {
              uiNode.x = currentX;
              uiNode.y = startY;
              currentX += 300; 
            }

            // C. TRADUCCIÓN DE PANELES DE CONFIGURACIÓN
            // Convertimos node_parameters -> parameters (Para los sliders)
            uiNode.parameters = uiNode.parameters || uiNode.node_parameters || {};
            
            // Convertimos node_execution_settings -> execution
            if (!uiNode.execution && uiNode.node_execution_settings) {
              uiNode.execution = {
                mode: uiNode.node_execution_settings.execution_mode === 'monte_carlo' ? 'Monte Carlo' : 'Single Run',
                duration: uiNode.node_execution_settings.duration_hours || 1,
                intervention: uiNode.node_execution_settings.human_intervention === 'fully_automated' ? 'Fully Automated' : 'Semi Automated'
              };
            }

            // Convertimos node_output_configuration -> outputConfig
            if (!uiNode.outputConfig && uiNode.node_output_configuration) {
              uiNode.outputConfig = {
                variables: (uiNode.node_output_configuration.variables || []).join(', '),
                visualization: (uiNode.node_output_configuration.visualization_preferences || []).join(', ')
              };
            }

            // D. TRADUCCIÓN DE PUERTOS (Para que te deje conectar flechas sin error)
            uiNode.inputs = uiNode.inputs || ["Data"]; // Asignamos genéricos para no romper la compatibilidad
            uiNode.outputs = uiNode.outputs || ["Data"];

            return uiNode;
          });
        }

        // 4. TRADUCCIÓN DE CONEXIONES (Líneas del lienzo)
        if (newPipeline.pipeline_connections && Array.isArray(newPipeline.pipeline_connections)) {
          newPipeline.pipeline_connections = newPipeline.pipeline_connections.map((conn: any) => {
            const uiConn = { ...conn };
            uiConn.id = uiConn.id || uiConn.connection_id || `conn-${Date.now() + Math.random()}`;
            uiConn.source = uiConn.source || uiConn.source_node_id;
            uiConn.target = uiConn.target || uiConn.target_node_id;
            return uiConn;
          });
        }

        currentPipelines.push(newPipeline);
      });

      localStorage.setItem('pipelines_db', JSON.stringify(currentPipelines));
      
      emit('imported');
      emit('close');

    } catch (error) {
      console.error(error);
      fileError.value = "Error al leer el archivo. Asegúrate de que es un JSON válido.";
    }
  };

  reader.readAsText(selectedFile.value);
};
</script>

<template>
  <div :class="$style.modalOverlay" @click.self="$emit('close')">
    <div :class="$style.modalCard">
      
      <div :class="$style.modalHeader">
        <h3>Import pipeline</h3>
        <button :class="$style.closeBtn" @click="$emit('close')">✕</button>
      </div>

      <div :class="$style.modalBody">
        <p :class="$style.modalDescription">
          Drag & drop a compatible file with one of the following extensions: <strong>.json</strong>.
        </p>

        <div 
          :class="[$style.dropZone, isDragging ? $style.dropZoneActive : '']"
          @dragover="onDragOver"
          @dragleave="onDragLeave"
          @drop="onDrop"
        >
          <div v-if="!selectedFile" :class="$style.dropZoneContent">
             <img src="/Upload.svg" :class="$style.iconUpload" alt="Upload Icon" />
             <span style="font-weight: 700;">Drag & Drop</span>
             <span style="font-size: 12px; color: #888;">File limit is {{ MAX_SIZE_MB }} MB</span>
             <span style="font-size: 10px; color: #666;">.JSON</span>
             
             <label :class="$style.browseLabel">
                Browse files
                <input type="file" accept=".json" @change="onFileSelect" hidden>
             </label>
          </div>

          <div v-else :class="$style.dropZoneContent">
            <div :class="$style.iconUpload"></div>
            <strong>{{ selectedFile.name }}</strong>
            <button @click="selectedFile = null" :class="$style.browseLabel" style="background:none; border:none; margin-top:8px;">
              Change file
            </button>
          </div>
        </div>
        
        <p v-if="fileError" :class="$style.errorMsg" style="color: #EF4444; font-size: 12px; margin-top: 8px;">{{ fileError }}</p>
      </div>

      <div :class="$style.modalFooter">
        <button :class="$style.btnCancel" @click="$emit('close')">Cancel</button>
        <button :class="$style.btnSave" :disabled="!selectedFile" @click="handleSave">Save</button>
      </div>

    </div>
  </div>
</template>

<style module src="./Drag.module.css"></style>