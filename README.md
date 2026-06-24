# SIEM-driven Adversary Engagement

**Plataforma para ejecutar y validar un modelo de adversary engagement dirigido por alertas SIEM y basado en MITRE Engage.**

Este repositorio acompaña al Trabajo Fin de Máster:

**Modelo de adversary engagement dirigido por alertas SIEM y basado en MITRE Engage**

El objetivo principal es validar que una alerta SIEM enriquecida puede transformarse en una recomendación MITRE Engage trazable, explicable y ejecutable dentro de un flujo realista.

---

## Descripción general

La plataforma permite validar el flujo propuesto en el Trabajo Fin de Máster:

1. Carga de una alerta SIEM enriquecida.
2. Traducción de la alerta nativa a una alerta normalizada.
3. Ejecución del modelo de decisión basado en MITRE Engage.
4. Generación de resultados con Activities recomendadas y no recomendadas.
5. Preservación de información operativa en `payload_context`.

El pipeline principal está compuesto por dos modelos:

* **Alert Translator**
  Traduce una alerta SIEM nativa a un formato común utilizado por el modelo.

* **Engage Mapper**
  Mapea la alerta normalizada a Goals, Approaches y Activities de MITRE Engage, aplicando los límites de exposición definidos.

---

## Tecnologías utilizadas

* **Node.js**
* **npm**
* **Python**
* **FastAPI**
* **Uvicorn**
* **MITRE Engage**
* **MITRE ATT&CK**
* **CVSS v3.1**
* **Docker** *(opcional para despliegue como microservicio)*

---

## Requisitos previos

Antes de ejecutar el proyecto, asegúrate de tener instalado:

* **Node.js**
* **npm**
* **Python 3**
* **pip**
* **Uvicorn**

Puedes comprobar la instalación con:

```bash
node -v
npm -v
python --version
pip --version
```

---

## Instalación del proyecto

Clona el repositorio:

```bash
git clone https://github.com/danielMarGar33/siem-driven-adversary-engagement.git
cd siem-driven-adversary-engagement
```

Instala las dependencias del frontend:

```bash
npm install
```

Instala las dependencias del backend de modelos:

```bash
pip install fastapi uvicorn
```

---

## Ejecución del frontend

Para compilar y lanzar la aplicación en modo desarrollo:

```bash
npm run dev
```

Una vez arrancada, la aplicación mostrará en consola la URL local desde la que se puede acceder a la interfaz web.

---

## Ejecución del backend de modelos

Además del frontend, es necesario levantar el backend encargado de ejecutar los modelos del pipeline.
Este backend expone los endpoints utilizados por la plataforma para llamar a los modelos **Alert Translator** y **Engage Mapper**.

Para arrancarlo en local, ejecuta:

```bash
python -m uvicorn webhook_server:app --host 127.0.0.1 --port 5000 --reload
```

Una vez iniciado, estarán disponibles los siguientes hooks:

```text
POST http://localhost:5000/translator
POST http://localhost:5000/engage-mapper
```

Estos endpoints son utilizados por la plataforma para ejecutar los modelos definidos en el pipeline:

* `POST /translator`: traduce la alerta SIEM nativa a una alerta normalizada.
* `POST /engage-mapper`: genera la salida basada en MITRE Engage a partir de la alerta normalizada.

---

## Uso básico

El uso general de la plataforma consiste en:

1. Arrancar el backend de modelos.
2. Arrancar el frontend.
3. Seleccionar el pipeline de adversary engagement.
4. Crear una nueva ejecución.
5. Cargar una alerta SIEM.
6. Configurar los campos necesarios para traducir la alerta.
7. Ejecutar el pipeline.
8. Revisar la alerta normalizada, los logs y los resultados generados.

La salida final permite consultar las Activities de MITRE Engage recomendadas y no recomendadas, junto con su exposición y el motivo de la decisión.

---

## Estructura del flujo

El flujo implementado sigue esta lógica:

```text
SIEM Alert
   ↓
Alert Translator
   ↓
Normalized Alert
   ↓
Engage Mapper
   ↓
MITRE Engage Playbook-like Output
```

La alerta normalizada contiene los campos necesarios para que el modelo pueda tomar la decisión:

* `name`
* `ttps`
* `alert_type`
* `max_cvss_base_score`
* `max_impact_subscore`
* `max_exploitability_subscore`
* `payload_context`

---

## Despliegue con Docker

El proyecto también puede ejecutarse mediante Docker si se quiere desplegar como microservicio.

Construye la imagen:

```bash
docker build -t siem-engage-decision-engine .
```

Ejecuta el contenedor:

```bash
docker run -p 5173:5173 siem-engage-decision-engine
```

En caso de modificar el puerto interno de la aplicación o desplegar también el backend en contenedor, ajusta el mapeo de puertos según corresponda.

---

## Autor

**Daniel Martín García**

Máster Universitario en Ciberseguridad
Universidad Politécnica de Madrid
2026
