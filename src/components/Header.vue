<script setup>
import { useRouter } from 'vue-router';

const router = useRouter();
</script>

<template>
  <div class="header">
    <p class="headerTitle" @click="router.push('/')">DECISION ENGINE - TFM</p>
  </div>
</template>

<style scoped src="./Header.css"></style>
