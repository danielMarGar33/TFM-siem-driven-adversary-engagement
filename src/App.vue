<script setup lang="ts">
import Header from './components/Header.vue';
</script>

<template>
  <div class="app-layout">
    <div class="main-wrapper">
      <Header />
      
      <main class="main-content">
        <router-view></router-view>
      </main>
    </div>
  </div>
</template>

<style scoped src="./App.css"></style>