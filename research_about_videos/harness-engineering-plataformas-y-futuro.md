# Harness Engineering: qué merece la pena construir sobre Claude Code, Codex, OpenCode y Pi

> Síntesis de videos sobre harness engineering, documentación oficial y publicaciones técnicas recientes. El objetivo es separar las capas duraderas de las que las plataformas están convirtiendo en funcionalidades nativas.

- **Actualizado:** 25 de septiembre de 2026
- **Enfoque:** coding agents

## La tesis en una frase

**El harness engineering no tiene los días contados; los wrappers genéricos sí.** Claude Code, Codex, OpenCode y Pi ya son harnesses. Construir otra capa encima solo tiene sentido cuando aporta conocimiento, controles o feedback específicos que el producto base no puede conocer.

Las plataformas están absorbiendo memoria, subagentes, permisos, skills, hooks, worktrees, planificación y orquestación. Un sistema cuya única aportación sea crear un agente líder, un implementador, un revisor y un archivo de tareas tiene un riesgo alto de quedar redundante.

> El activo duradero no es «cómo hago funcionar al agente», sino «cómo hago que mi entorno sea legible, verificable y seguro para cualquier agente».

## Las cinco capas que solemos confundir

1. **Modelo:** Claude, GPT, Gemini u otro modelo. Aporta razonamiento, generación y selección de herramientas.
2. **Harness base:** Claude Code, Codex, OpenCode o Pi: loop agéntico, herramientas, sesiones, contexto y permisos.
3. **Harness del repositorio:** `AGENTS.md`, documentación, arquitectura, scripts, tests, CI y convenciones del proyecto.
4. **Harness de la organización:** tickets, despliegues, observabilidad, seguridad, QA, compliance y revisión.
5. **Meta-harness:** programas que lanzan agentes, asignan modelos, mantienen memoria y coordinan tareas.

Las plataformas están absorbiendo rápidamente la quinta capa genérica. Las capas tres y cuatro no se pueden generalizar por completo: dependen de tu producto, arquitectura, riesgos y definición de calidad.

La evolución histórica puede entenderse así:

```text
Prompt engineering  → instrucciones
Context engineering → información relevante
Harness engineering → entorno completo de ejecución y verificación
```

## Comparativa ejecutiva

| Plataforma | Fortaleza principal | ¿Construir encima? | Riesgo principal | Mejor encaje |
|---|---|---|---|---|
| **Claude Code** | Harness muy completo y workflows dinámicos | Selectivamente | Duplicar funciones que Anthropic incorpora rápidamente | Máxima productividad e integración |
| **Codex** | SDK, App Server, sandbox y automatización | Sí, por API | Acoplamiento al runtime y ecosistema OpenAI | Automatización, CI y flujos empresariales |
| **OpenCode** | Abierto, multiproveedor y extensible | Sí | Churn de APIs y configuración en un producto joven | Portabilidad y control |
| **Pi** | Runtime mínimo y profundamente extensible | Sí, es su propósito | Debes aportar aislamiento y más infraestructura | Experimentación y harnesses verticales |

En este informe, “Pi” se refiere al coding agent de [pi.dev](https://pi.dev/).

## Evaluación por plataforma

### Claude Code

Incluye instrucciones persistentes, memoria, skills, hooks, permisos, subagentes, agent teams, background agents, worktrees y Agent SDK.

La señal más importante es la aparición de **dynamic workflows**: Claude puede generar un harness JavaScript específico para cada tarea, con fan-out, verificación adversaria, torneos, routing y bucles.

**Opinión:** usa skills, hooks, workflows y SDK oficiales. Evita wrappers que ejecuten la CLI, analicen su texto o reimplementen memoria, permisos y subagentes. Es la plataforma con mayor probabilidad de absorber una innovación externa.

### Codex

Ya ofrece `AGENTS.md` jerárquico, subagentes, skills, MCP, hooks, plugins, worktrees, SDKs de TypeScript y Python y App Server.

El caso interno de OpenAI muestra que el valor no estaba en un prompt mágico: estaba en hacer el repositorio legible, observable y mecánicamente verificable mediante documentación, planes, linters, tests y entornos aislados.

**Opinión:** construir sobre el SDK o App Server es razonable. Envolver la CLI es frágil. No basaría una diferenciación comercial únicamente en “añadir subagentes a Codex”.

### OpenCode

Es abierto y multiproveedor. Incluye agentes declarativos, permisos, subagentes, skills compatibles, plugins, herramientas propias, servidor OpenAPI y SDK tipado.

**Opinión:** es el mejor punto medio si buscas neutralidad de modelo sin mantener un agent loop propio. Mantendría la lógica esencial en estándares y ejecutables independientes para reducir el impacto de cambios de versión.

### Pi

Expone un loop mínimo, múltiples proveedores, sesiones JSONL en árbol, skills, extensiones TypeScript, RPC y SDK. Permite intervenir en contexto, herramientas, ciclo, estado y UI.

**Opinión:** es donde más sentido tiene crear un harness propio, porque esa es su filosofía. Pero Pi no ofrece un sandbox general: las extensiones y herramientas tienen los permisos del proceso. Para ejecución desatendida necesitarás un contenedor, una VM o un sandbox externo.

## El patrón líder–implementador–revisor no es una ley

Anthropic estima que un sistema multiagente suele consumir entre **3 y 10 veces más tokens** que uno de un solo agente para tareas equivalentes. También ha observado equipos que construyeron arquitecturas complejas y obtuvieron resultados similares mejorando un único agente.

Separar por profesiones —planificador, implementador, tester y revisor— puede crear un teléfono roto. Cada traspaso pierde decisiones y obliga a reconstruir contexto.

### Buenas fronteras

- Investigaciones independientes.
- Componentes con interfaces claras.
- Análisis de logs separado del código.
- Verificación de caja negra.
- Hipótesis competidoras en paralelo.

### Fronteras problemáticas

- Planear, implementar y probar la misma feature en agentes distintos.
- Componentes fuertemente acoplados.
- Trabajo que exige sincronización continua.
- Subagentes creados solo porque “más agentes” parece mejor.

El patrón que sí mantiene valor es el **verificador independiente**: recibe requisitos y artefacto, ejecuta comprobaciones objetivas y dictamina sin necesitar toda la historia de implementación.

## Qué tiene riesgo real de desaparecer

### Alto riesgo de obsolescencia

- Wrappers que invocan una CLI y analizan texto.
- Sistemas propios de plan mode, memoria conversacional o worktrees paralelos.
- Orquestadores estáticos de roles.
- Catálogos propietarios equivalentes a Agent Skills.
- Capas de aprobación que duplican permisos y hooks nativos.

### Riesgo medio

- Plugins muy acoplados a eventos internos.
- Workflows exclusivos de un proveedor.
- Configuraciones complejas de hooks.
- Memoria dependiente del formato interno de sesiones.

### Bajo riesgo y alto valor

- `AGENTS.md` conciso y Agent Skills estándar.
- Documentación estructurada y versionada.
- Tests, linters y políticas ejecutables.
- Arquitectura con límites verificables.
- Observabilidad accesible mediante CLI o API.
- Evals, fixtures y criterios de aceptación.
- CI independiente del agente utilizado.

## Arquitectura recomendada para un harness durable

La lógica del negocio y la definición de calidad deberían vivir en el repositorio, no en una plataforma concreta.

```text
Repositorio
├── AGENTS.md                  # mapa breve, no enciclopedia
├── docs/                      # conocimiento estructurado
│   ├── architecture.md
│   ├── product/
│   ├── decisions/
│   └── plans/
├── .agents/skills/            # skills portables
├── scripts/                   # acciones reproducibles
├── tests/                     # criterios ejecutables
├── architecture-checks/       # invariantes mecánicas
├── observability/             # CLI/API legible para agentes
└── CI                         # autoridad final

Adaptadores finos
├── .claude/                   # solo integración Claude
├── .codex/                    # solo integración Codex
├── .opencode/                 # solo integración OpenCode
└── .pi/                       # solo integración Pi
```

La plataforma es un runtime sustituible. El harness real es el conocimiento, las herramientas y el feedback que permanecen cuando cambias de runtime o modelo.

## Diseño operativo: del feedback a la autonomía

Un harness útil no necesita empezar como un sistema autónomo complejo. Conviene escoger el loop más pequeño que resuelva la tarea y aumentar su alcance solo cuando existan verificadores capaces de detectar desviaciones.

### Flujo lineal

```text
Entrada → herramienta → respuesta → salida
```

Es adecuado para clasificar, inspeccionar o transformar cuando el recorrido debe ser predecible y limitado.

### Loop cerrado

```text
Observar → modificar → verificar → interpretar el fallo → repetir
```

Es adecuado para código, depuración y tareas cuyo estado final puede comprobarse mecánicamente.

### Escalera de autonomía

1. Empieza con una tarea pequeña y un criterio de aceptación explícito.
2. Haz que tests, linters o verificadores juzguen el resultado.
3. Encadena varios cambios pequeños y mide cuándo aparece la divergencia.
4. Aumenta el tamaño del loop solo si el sistema puede detectar, explicar y corregir fallos.
5. Reserva migraciones, ejecución prolongada y paralelismo para un entorno que ya haya demostrado fiabilidad.

La pregunta práctica no es solamente cuántos agentes utilizar, sino **cuántos cambios puede encadenar el sistema antes de necesitar intervención humana**.

### Desplazar el feedback a la izquierda

Una corrección repetida debería convertirse progresivamente en infraestructura reusable:

```text
Corrección manual
→ instrucción breve
→ documentación descubrible
→ herramienta o script
→ test o verificador
→ política automática
```

El objetivo es reducir la dependencia de prompts extensos. El agente debería clasificar la tarea y descubrir bajo demanda la documentación, las skills y las herramientas relevantes, en vez de cargar todo el conocimiento en cada ejecución.

### Observabilidad diseñada para agentes y humanos

Logs, métricas y trazas deben exponerse mediante CLI o API, con salidas densas, filtrables y reproducibles. La automatización no elimina la necesidad de inspección: cuando el artefacto final es incorrecto, debe ser posible reconstruir qué contexto, decisiones y verificaciones produjeron el desvío.

## Principios para aplicarlo en tu harness

- Construye el delta, no dupliques el runtime.
- Empieza con un agente; añade más solo con evidencia.
- Divide por fronteras de contexto, no por cargos.
- Haz que la verificación sea ejecutable.
- Escoge entre flujo lineal y loop cerrado según la tarea.
- Aumenta la autonomía solo después de demostrar fiabilidad.
- Usa progressive disclosure para el contexto.
- Mantén `AGENTS.md` como mapa corto.
- Convierte feedback repetido en tests o linters.
- Expón UI, logs, métricas y trazas al agente.
- Prefiere estándares y formatos portables.
- Aísla tareas de escritura con worktrees o sandboxes.
- Mide tiempo humano, coste, calidad y regresiones.
- Elimina periódicamente personalización innecesaria.

## Por qué un modelo mejor no elimina el harness

Un modelo más capaz reduce las instrucciones necesarias, pero no puede adivinar qué significa “correcto” para tu negocio, qué riesgos son inaceptables, cómo ejecutar tu aplicación, dónde encontrar logs o qué prueba demuestra que una tarea terminó.

Incluso un modelo excelente necesita:

1. objetivos y restricciones;
2. acceso al entorno;
3. límites de actuación;
4. información observable;
5. criterios de éxito.

> El harness del futuro tendrá menos “prompt sobre cómo programar” y más infraestructura que define y demuestra resultados.

## Productividad: evidencia todavía incompleta

El estudio de METR de 2025 encontró que 16 mantenedores experimentados tardaron un 19 % más con herramientas de IA, aunque creían haber sido más rápidos. Sin embargo, METR actualizó su evaluación en febrero de 2026: considera aquel resultado histórico y sus datos posteriores apuntan a una posible mejora, pero con sesgos de selección e intervalos demasiado amplios para una conclusión firme.

La lectura responsable es que la productividad depende del tipo de tarea, experiencia, madurez del repositorio y calidad del harness. Las percepciones personales y los benchmarks aislados no bastan.

## La prueba semestral

Cada seis meses compara la plataforma limpia con tu harness completo usando un conjunto de tareas reales.

### A. Baseline

Claude Code, Codex, OpenCode o Pi con configuración mínima y sin orquestación personalizada.

### B. Tu harness

La misma plataforma con reglas, skills, hooks, memoria, herramientas y agentes personalizados.

### Métricas recomendadas

- Tareas completadas correctamente.
- Intervenciones humanas necesarias.
- Tiempo humano activo y tiempo total.
- Tokens y coste económico.
- Tests, regresiones y rollbacks.
- Archivos modificados innecesariamente.
- Calidad y tiempo de revisión del PR.
- Recuperación después de compactación.

Si la personalización no mejora claramente estas métricas, simplifícala o elimínala. La complejidad del harness debe ganarse su existencia.

## Decisión práctica

- **Productividad inmediata:** Claude Code o Codex, usando sus extensiones oficiales en lugar de un orquestador externo.
- **Neutralidad de modelo:** OpenCode, con conocimiento y validación en formatos portables.
- **Investigación de harnesses:** Pi, aceptando que tendrás que resolver aislamiento, seguridad y más infraestructura.
- **Empresa multiproveedor:** un núcleo portable en el repositorio y adaptadores finos para cada runtime.

**Conclusión:** el futuro no es un gran harness universal encima de Claude Code o Codex. Es un repositorio preparado para agentes, con una capa fina de integración para el runtime que uses hoy.

## Fuentes

1. [OpenAI — Harness engineering: leveraging Codex in an agent-first world](https://openai.com/index/harness-engineering/)
2. [Anthropic — Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
3. [Claude Code — A harness for every task](https://claude.com/blog/a-harness-for-every-task-dynamic-workflows-in-claude-code)
4. [Anthropic — Building multi-agent systems: when and how to use them](https://claude.com/blog/building-multi-agent-systems-when-and-how-to-use-them)
5. [Anthropic — Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)
6. [OpenAI Developers — Codex documentation](https://developers.openai.com/codex/)
7. [OpenCode documentation](https://opencode.ai/docs/)
8. [Pi documentation](https://pi.dev/docs/latest)
9. [AGENTS.md — formato abierto de instrucciones](https://agents.md/)
10. [Agent Skills — estándar abierto](https://agentskills.io/)
11. [METR — actualización del estudio de productividad](https://metr.org/blog/2026-02-24-uplift-update/)
12. [Chroma — Context Rot](https://research.trychroma.com/context-rot)
13. [Don Woodlock — What Is Harness Engineering?](https://www.youtube.com/watch?v=yg55OIb5op0)
14. [Google Cloud Tech — Harness Engineering Explained](https://www.youtube.com/watch?v=F8EZJAm9iO8)

La síntesis también incorpora los materiales locales generados a partir de los videos sobre harness engineering almacenados en `data/videos/`.
