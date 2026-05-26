<script setup lang="ts">
// Aquí importarás las rutas de tus iconos descargados más adelante
</script>

<template>
  <nav class="side-nav">
    <div class="nav-item"><img src="/public/Dashboard.svg" alt="Dashboard"></div>
    <div class="nav-item"><img src="/public/Flag.svg" alt="Flag"></div>
    <div class="nav-item"><img src="/public/List.svg" alt="List"></div>
    <div class="nav-item"><img src="/public/Simulation.svg" alt="Simulation"></div>
    <div class="nav-item"><img src="/public/Eye.svg" alt="Eye"></div>
    <div class="nav-item"><img src="/public/Target.svg" alt="Target"></div>
  </nav>
</template>

<style scoped>
.side-nav {
  display: flex;
  flex-direction: column; /* Para que los iconos vayan en vertical */
  width: 42px;
  height: 100vh; /* Mejor que 1036px fijos para adaptarse a cualquier pantalla */
  align-items: center; /* Centra los iconos horizontalmente en esos 42px */
  background: var(--contextmenu-background, #F8FAFB);
  border-right: 1px solid #E4E7EB; /* Borde sutil para separar del contenido */
  padding-top: 16px; /* Separación desde el borde superior */
  gap: 24px; /* Separación entre cada icono */
  flex-shrink: 0; /* Evita que el menú se encoja si falta espacio */
  z-index: 10;
}

/* Estilos temporales para que veas dónde van los iconos */
.nav-item {
  width: 24px;
  height: 24px;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: #E2E8F0; 
  color: #64748B;
  font-size: 12px;
  border-radius: 4px;
  cursor: pointer;
  transition: opacity 0.2s;
}

.nav-item:hover {
  opacity: 0.7;
}
</style>