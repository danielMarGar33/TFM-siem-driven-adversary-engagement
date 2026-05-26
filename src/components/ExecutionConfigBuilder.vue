<script setup lang="ts">
import { ref, computed } from 'vue';

const siemName = ref('');
const inputFormat = ref('');

const nameField = ref('');
const descriptionField = ref('');
const ttpsField = ref('');
const alertTypeField = ref('');
const acceptableRiskField = ref('');

const payloadContextFields = ref<string[]>(['']);

const addPayloadContextField = () => {
    payloadContextFields.value.push('');
};

const removePayloadContextField = (index: number) => {
    payloadContextFields.value.splice(index, 1);

    if (payloadContextFields.value.length === 0) {
        payloadContextFields.value.push('');
    }
};

const generatedParameters = computed(() => {
    return {
        siem_name: siemName.value.trim(),
        input_format: inputFormat.value.trim(),
        name_field: nameField.value.trim(),
        description_field: descriptionField.value.trim(),
        ttps_field: ttpsField.value.trim(),
        alert_type_field: alertTypeField.value.trim(),
        acceptable_risk_field: acceptableRiskField.value.trim(),
        payload_context_fields: payloadContextFields.value
            .map((field) => field.trim())
            .filter((field) => field.length > 0)
    };
});

const generatedParametersText = computed(() => {
    return JSON.stringify(generatedParameters.value, null, 2);
});
</script>

<template>
    <div class="config-builder">
        <h3>Execution Configuration Parameters</h3>
        <p class="helper-text">
            These values are model parameters now. Configure them by selecting the Alert Translator model in the
            Pipeline Designer before creating the execution.
        </p>

        <div class="form-grid">
            <div class="form-group">
                <label class="field-label">SIEM name</label>
                <input v-model="siemName" class="text-input" type="text" placeholder="Example: wazuh" />
            </div>

            <div class="form-group">
                <label class="field-label">Input format</label>
                <input v-model="inputFormat" class="text-input" type="text" placeholder="Example: json_or_ndjson" />
            </div>
        </div>

        <h4>Field mapping</h4>

        <div class="form-group">
            <label class="field-label">Name field</label>
            <input v-model="nameField" class="text-input" type="text" placeholder="Example: rule.description" />
        </div>

        <div class="form-group">
            <label class="field-label">Description field</label>
            <input v-model="descriptionField" class="text-input" type="text" placeholder="Example: rule.description" />
        </div>

        <div class="form-group">
            <label class="field-label">TTPs field</label>
            <input v-model="ttpsField" class="text-input" type="text" placeholder="Example: rule.mitre.id" />
        </div>

        <div class="form-group">
            <label class="field-label">Alert type field</label>
            <input v-model="alertTypeField" class="text-input" type="text"
                placeholder="Example: tags.engage.alert_type" />
        </div>

        <div class="form-group">
            <label class="field-label">Acceptable risk field</label>
            <input v-model="acceptableRiskField" class="text-input" type="text"
                placeholder="Example: tags.engage.acceptable_risk" />
        </div>

        <div class="form-group">
            <div class="payload-header">
                <label class="field-label">Payload context fields</label>

                <button type="button" class="btn-add-field" @click="addPayloadContextField" title="Add field">
                    +
                </button>
            </div>

            <div class="payload-fields">
                <div v-for="(field, index) in payloadContextFields" :key="index" class="payload-field-row">
                    <input v-model="payloadContextFields[index]" class="text-input" type="text"
                        placeholder="Example: rule.id" />

                    <button type="button" class="btn-remove-field" @click="removePayloadContextField(index)"
                        title="Remove field">
                        x
                    </button>
                </div>
            </div>
        </div>

        <div class="preview-box">
            <div class="preview-header">
                <h4>Model parameters</h4>
            </div>

            <pre>{{ generatedParametersText }}</pre>
        </div>
    </div>
    <button class="btn-secondary back-button" @click="$router.back()">
        ← Back
    </button>
</template>

<style scoped src="./ExecutionConfigBuilder.css"></style>
