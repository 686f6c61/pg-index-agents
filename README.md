# PG Index Agents

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Next.js](https://img.shields.io/badge/Next.js-15-black.svg)](https://nextjs.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14+-336791.svg)](https://www.postgresql.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agent_Framework-orange.svg)](https://github.com/langchain-ai/langgraph)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Sistema de agentes inteligentes para analisis y optimizacion automatica de indices en PostgreSQL.

Este proyecto es una prueba de concepto que explora la aplicacion de modelos de lenguaje en tareas de administracion de bases de datos. El sistema utiliza multiples agentes especializados que colaboran para analizar, diagnosticar y proponer mejoras en la estructura de indices de una base de datos PostgreSQL.

## Tabla de contenidos

- [Hipotesis](#hipotesis)
- [Arquitectura](#arquitectura)
- [Sistema de agentes](#sistema-de-agentes)
- [Stack tecnologico](#stack-tecnologico)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Requisitos](#requisitos)
- [Instalacion](#instalacion)
- [Bases de datos de ejemplo](#bases-de-datos-de-ejemplo)
- [Uso](#uso)
- [API REST](#api-rest)
- [Niveles de autonomia](#niveles-de-autonomia)
- [Contribuciones](#contribuciones)
- [Licencia](#licencia)

---

## Hipotesis

La gestion de indices en bases de datos PostgreSQL es un proceso complejo que tradicionalmente requiere expertise de administradores de bases de datos especializados. Este proyecto plantea la hipotesis de que un sistema multi-agente con capacidades de inteligencia artificial puede automatizar gran parte de este trabajo.

Los objetivos especificos son:

- Analizar automaticamente la estructura y patrones de uso de una base de datos
- Detectar anomalias y oportunidades de optimizacion de indices
- Generar propuestas de indices con justificaciones comprensibles
- Mantener la salud de los indices existentes de forma proactiva
- Recomendar estrategias de particionamiento para tablas de gran volumen

---

## Arquitectura

El sistema sigue una arquitectura cliente-servidor con separacion clara entre el backend de procesamiento y el frontend de visualizacion.

```
                                    +------------------+
                                    |    Frontend      |
                                    |    (Next.js)     |
                                    +--------+---------+
                                             |
                                             | HTTP/REST
                                             |
                                    +--------v---------+
                                    |    Backend       |
                                    |    (FastAPI)     |
                                    +--------+---------+
                                             |
                         +-------------------+-------------------+
                         |                   |                   |
                +--------v-------+  +--------v-------+  +--------v-------+
                |   PostgreSQL   |  |    SQLite      |  |   OpenRouter   |
                |   (Target DB)  |  |   (State)      |  |   (LLM API)    |
                +----------------+  +----------------+  +----------------+
```

El backend mantiene su estado interno en una base de datos SQLite separada, lo que permite analizar cualquier base de datos PostgreSQL sin modificarla. La comunicacion con modelos de lenguaje se realiza a traves de OpenRouter, permitiendo utilizar diferentes proveedores de LLM.

---

## Sistema de agentes

El sistema esta compuesto por cinco agentes especializados que trabajan de forma coordinada. Cada agente tiene un proposito especifico y genera artefactos que pueden ser consumidos por otros agentes o presentados al usuario.

| Agente | Proposito | Artefactos |
|--------|-----------|------------|
| Explorer | Analiza la estructura de la base de datos, clasifica tablas por criticidad y detecta anomalias iniciales | Clasificaciones, grafo de dependencias, anomalias |
| Observer | Monitorea metricas de rendimiento, analiza patrones de queries y genera senales de alerta | Senales, metricas, patrones detectados |
| Architect | Procesa senales y anomalias para generar propuestas concretas de indices con justificaciones | Propuestas SQL, estimaciones de impacto |
| Gardener | Mantiene la salud de indices existentes, detecta bloat y programa tareas de mantenimiento | Tareas de mantenimiento, recomendaciones |
| Partitioner | Analiza tablas grandes para recomendar estrategias de particionamiento | Informes de particionamiento, planes de migracion |

### Flujo de trabajo

El flujo tipico de analisis sigue esta secuencia:

```
Explorer --> Observer --> Architect --> Gardener --> Partitioner
```

Cada agente puede ejecutarse de forma independiente, pero los resultados son mas completos cuando se ejecutan en secuencia, ya que cada uno enriquece el contexto disponible para el siguiente.

---

## Stack tecnologico

### Backend

El backend esta desarrollado en Python y utiliza las siguientes tecnologias:

| Tecnologia | Version | Proposito |
|------------|---------|-----------|
| Python | 3.11+ | Lenguaje de programacion |
| FastAPI | 0.100+ | Framework web asincronico |
| SQLAlchemy | 2.0+ | ORM y conexion a bases de datos |
| LangChain | 0.1+ | Orquestacion de modelos de lenguaje |
| Pydantic | 2.0+ | Validacion de datos y configuracion |
| psycopg2 | 2.9+ | Driver nativo de PostgreSQL |

### Frontend

El frontend esta desarrollado en TypeScript con React y utiliza las siguientes tecnologias:

| Tecnologia | Version | Proposito |
|------------|---------|-----------|
| Next.js | 15 | Framework React con App Router |
| TypeScript | 5.0+ | Tipado estatico |
| Tailwind CSS | 3.4+ | Framework de estilos utilitarios |
| React Flow | 11+ | Visualizacion de grafos |
| Lucide React | - | Iconografia |

### Infraestructura

| Componente | Proposito |
|------------|-----------|
| PostgreSQL 14+ | Base de datos objetivo a analizar |
| SQLite | Almacenamiento de estado interno |
| OpenRouter | Gateway para acceso a modelos de lenguaje |

---

## Estructura del proyecto

```
Agentes_Indices/
├── backend/
│   ├── agents/                 # Implementacion de los 5 agentes
│   │   ├── explorer.py         # Agente de exploracion y clasificacion
│   │   ├── observer.py         # Agente de monitoreo y senales
│   │   ├── architect.py        # Agente de propuestas de indices
│   │   ├── gardener.py         # Agente de mantenimiento
│   │   └── partitioner.py      # Agente de particionamiento
│   ├── api/
│   │   └── routes.py           # Endpoints REST de la API
│   ├── core/
│   │   ├── config.py           # Configuracion y variables de entorno
│   │   ├── database.py         # Conexiones a bases de datos
│   │   ├── state.py            # Gestion de estado persistente
│   │   ├── llm.py              # Integracion con modelos de lenguaje
│   │   ├── executor.py         # Orquestador de agentes
│   │   └── background.py       # Sistema de tareas en segundo plano
│   ├── services/
│   │   ├── metadata.py         # Extraccion de metadatos de PostgreSQL
│   │   └── ai_explainer.py     # Generacion de explicaciones con IA
│   ├── main.py                 # Punto de entrada de la aplicacion
│   └── requirements.txt        # Dependencias Python
├── frontend/
│   ├── src/
│   │   ├── app/                # Paginas de la aplicacion (App Router)
│   │   ├── components/         # Componentes React reutilizables
│   │   ├── hooks/              # Hooks personalizados
│   │   └── lib/                # Utilidades y cliente API
│   ├── package.json            # Dependencias Node.js
│   └── tailwind.config.ts      # Configuracion de Tailwind
├── scripts/
│   ├── download_stackexchange.py   # Descarga de datos de Stack Exchange
│   ├── import_stackoverflow.py     # Importacion automatica con tamanos
│   ├── import_to_postgres.py       # Importacion de XML a PostgreSQL
│   └── import_airbnb.py            # Importacion de datos de Airbnb
└── start.sh                    # Script de inicio rapido
```

---

## Requisitos

Antes de instalar el proyecto, asegurate de tener instalados los siguientes componentes:

| Requisito | Version minima | Proposito |
|-----------|----------------|-----------|
| PostgreSQL | 14 | Base de datos objetivo |
| Python | 3.11 | Backend |
| Node.js | 18 | Frontend |
| p7zip | - | Descompresion de datos de ejemplo |
| wget | - | Descarga de datos (opcional) |

Para sistemas basados en Debian/Ubuntu, puedes instalar los requisitos con:

```bash
sudo apt update
sudo apt install postgresql p7zip-full python3-pip nodejs npm wget
```

---

## Instalacion

### Clonar el repositorio

```bash
git clone https://github.com/686f6c61/pg-index-agents.git
cd pg-index-agents
```

### Configurar el backend

El backend requiere un entorno virtual de Python y la configuracion de variables de entorno.

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Crea el archivo de configuracion copiando el ejemplo:

```bash
cp .env.example .env
```

Edita el archivo `.env` con tu configuracion:

```env
# API de OpenRouter para acceso a modelos de lenguaje
OPENROUTER_API_KEY=tu_api_key

# Conexion a la base de datos objetivo
PG_TARGET_HOST=localhost
PG_TARGET_PORT=5432
PG_TARGET_DATABASE=nombre_de_tu_base_de_datos
PG_TARGET_USER=tu_usuario
PG_TARGET_PASSWORD=tu_password
```

### Configurar el frontend

```bash
cd frontend
npm install
```

### Iniciar la aplicacion

Puedes iniciar ambos servicios con el script de inicio:

```bash
./start.sh
```

O iniciarlos por separado en terminales diferentes:

```bash
# Terminal 1 - Backend
cd backend
source venv/bin/activate
python main.py

# Terminal 2 - Frontend
cd frontend
npm run dev
```

El backend estara disponible en `http://localhost:8000` y el frontend en `http://localhost:3000`.

---

## Bases de datos de ejemplo

El proyecto incluye scripts para importar tres conjuntos de datos de ejemplo que permiten probar las capacidades del sistema.

### Stack Exchange (metodo rapido)

Este metodo descarga automaticamente sitios de Stack Exchange de diferentes tamanos. Es la opcion recomendada para comenzar.

| Tamano | Sitio | Registros aproximados |
|--------|-------|----------------------|
| small | coffee.stackexchange | 5,000 posts |
| medium | dba.stackexchange | 75,000 posts |
| large | serverfault | 350,000 posts |

```bash
sudo -u postgres createdb stackoverflow_sample
cd backend && source venv/bin/activate
cd ../scripts
python import_stackoverflow.py --sample-size medium
```

### Stack Overflow completo (metodo manual)

Para analisis a escala real, puedes descargar el dataset completo de Stack Overflow desde archive.org. Este metodo requiere aproximadamente 30GB de espacio en disco para la descarga y 150GB para los datos descomprimidos.

```bash
cd scripts
python download_stackexchange.py
sudo -u postgres createdb stackexchange
python import_to_postgres.py
```

El script de descarga presenta un menu interactivo con las siguientes opciones:

- Full: Posts, Users, Comments, Votes, Badges, Tags (30GB)
- Core: Posts y Users (21GB)
- DBA Site: Sitio de administradores de bases de datos (500MB)
- Custom: Seleccion manual de archivos

### Airbnb

Los datos de Inside Airbnb son utiles para probar el agente de particionamiento, ya que incluyen tablas con millones de registros.

```bash
sudo -u postgres createdb airbnb_sample
cd scripts
python import_airbnb.py --city amsterdam --skip-calendar
```

La opcion `--skip-calendar` omite la tabla de calendario, que puede contener varios millones de filas.

---

## Uso

Una vez iniciada la aplicacion, accede a `http://localhost:3000` en tu navegador.

### Pantalla principal

La pantalla principal muestra las bases de datos configuradas. Haz clic en una base de datos para acceder a su panel de analisis.

### Panel de base de datos

El panel de base de datos contiene las siguientes secciones:

| Seccion | Descripcion |
|---------|-------------|
| Resumen | Estadisticas generales de la base de datos |
| Agentes | Panel de control para ejecutar cada agente |
| Propuestas | Lista de propuestas de indices pendientes de aprobacion |
| Reportes | Informes detallados generados por los agentes |

### Ejecucion de agentes

Para ejecutar un agente, seleccionalo en el panel de agentes y haz clic en el boton de ejecucion. El agente se ejecutara en segundo plano y podras ver su progreso en tiempo real.

Los resultados de cada agente se muestran en la pestana correspondiente. Las propuestas de indices generadas por el Architect requieren aprobacion manual antes de ejecutarse.

---

## API REST

El backend expone una API REST documentada con OpenAPI. Puedes acceder a la documentacion interactiva en `http://localhost:8000/docs`.

### Endpoints principales

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| GET | /api/databases | Lista todas las bases de datos configuradas |
| GET | /api/databases/{id} | Obtiene detalles de una base de datos |
| POST | /api/databases/{id}/agents/{agent}/run | Ejecuta un agente |
| GET | /api/databases/{id}/analyses | Obtiene los analisis realizados |
| GET | /api/databases/{id}/proposals | Lista las propuestas de indices |
| POST | /api/proposals/{id}/approve | Aprueba y ejecuta una propuesta |
| POST | /api/proposals/{id}/reject | Rechaza una propuesta |
| GET | /api/jobs | Lista los trabajos en ejecucion |
| GET | /api/logs | Obtiene los logs del sistema |

---

## Niveles de autonomia

El sistema soporta cuatro niveles de autonomia que determinan el grado de intervencion humana requerido.

| Nivel | Nombre | Comportamiento |
|-------|--------|----------------|
| 0 | Observacion | Solo analiza e informa, sin generar propuestas |
| 1 | Asistido | Genera propuestas que requieren aprobacion manual |
| 2 | Confianza | Ejecuta automaticamente propuestas de bajo riesgo |
| 3 | Autonomo | Ejecuta todas las propuestas automaticamente |

El nivel de autonomia se configura por base de datos y puede ajustarse en tiempo de ejecucion desde el panel de configuracion.

Para entornos de produccion, se recomienda comenzar con el nivel 1 (Asistido) y aumentar gradualmente segun la confianza en las propuestas del sistema.

---

## Contribuciones

Las contribuciones son bienvenidas. Para contribuir al proyecto, sigue estos pasos:

1. Haz un fork del repositorio
2. Crea una rama para tu funcionalidad (`git checkout -b feature/nueva-funcionalidad`)
3. Realiza tus cambios y anade tests si corresponde
4. Asegurate de que el codigo sigue el estilo del proyecto
5. Envia un pull request con una descripcion clara de los cambios

### Guia de estilo

El codigo Python sigue las convenciones de PEP 8. El codigo TypeScript sigue las convenciones del proyecto con ESLint configurado.

Los mensajes de commit deben ser descriptivos y seguir el formato:

```
tipo: descripcion breve

Descripcion detallada si es necesaria.
```

Donde tipo puede ser: feat, fix, docs, refactor, test, chore.

---

## Licencia

Este proyecto se distribuye bajo la licencia MIT. Consulta el archivo LICENSE para mas detalles.

---

## Autor

Desarrollado por [686f6c61](https://github.com/686f6c61) como prueba de concepto para la aplicacion de inteligencia artificial en la administracion de bases de datos.
