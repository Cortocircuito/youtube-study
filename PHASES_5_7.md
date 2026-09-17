# Fases 5–7 — Referencia de trabajo

Documento breve para consultar el estado y los siguientes pasos del refactor de YouTube Study.

> Alcance: estas fases no añaden Ollama, LLMs, Whisper, GUI ni servicios externos.

## Fase 5 — Refactor arquitectónico sin cambio funcional ✅

**Estado:** completada en el commit `f3fca1f`.

### Resultado

La aplicación quedó separada por responsabilidades:

```txt
app.py                         # Entry point mínimo
src/youtube_study/cli.py       # argparse, comandos y salida al usuario
src/youtube_study/service.py   # Pipeline de study, analyze y export
src/youtube_study/models.py    # Tipos VideoInfo y LibraryEntry
```

### Cambios realizados

- Se extrajo el pipeline de `app.py` a `service.py`.
- Se extrajeron parsing CLI, presentación y errores a `cli.py`.
- Se centralizaron opciones repetidas `--out` y `--lang`.
- Se añadieron tipos para metadata de video y entradas de biblioteca.
- `app.py` conserva el contrato público:

```bash
python app.py "URL"
python app.py list
python app.py analyze VIDEO_ID
python app.py export VIDEO_ID --format all
```

### Verificación realizada

```bash
.venv/bin/python app.py --help
.venv/bin/python app.py list
.venv/bin/python -m py_compile app.py src/youtube_study/*.py
.venv/bin/python -m pytest
```

Resultado: `29 passed`.

---

## Fase 6 — Calidad heurística medible ✅

**Estado:** completada. El catálogo versionado, los fixtures heurísticos y las pruebas de regresión ya cubren herramientas conocidas, categorías, falsos positivos (`QR`, `SIM`) y conceptos de relleno.

**Objetivo:** detectar herramientas y conceptos con mayor precisión y proteger el comportamiento con fixtures pequeños y medibles.

### Pasos

1. Crear fixtures pequeños con herramientas, conceptos y falsos positivos esperados.
   - Casos positivos: `SSH`, `Tailscale`, `tmux`, `Claude`.
   - Falsos positivos conocidos: `QR`, `SIM` y nombres comunes.
2. Clasificar los hallazgos en categorías explícitas:
   - herramienta
   - protocolo
   - modelo
   - servicio
   - candidato desconocido
3. Mover el catálogo de herramientas y sus aliases desde `analyzer.py` a datos configurables y versionados.
4. Mejorar `STOPWORDS` y el ranking de conceptos para excluir muletillas, verbos frecuentes y términos poco útiles.
5. Añadir tests/métricas que impidan regresiones:
   - las herramientas conocidas deben seguir detectándose;
   - `QR` y `SIM` no deben clasificarse como herramientas;
   - la lista de candidatos desconocidos debe ser limitada y conservadora.

### Archivos previstos

```txt
src/youtube_study/analyzer.py
src/youtube_study/...           # catálogo de herramientas configurable
tests/test_analyzer.py
tests/fixtures/...              # textos cortos etiquetados
```

### Verificación

```bash
.venv/bin/python -m pytest tests/test_analyzer.py
.venv/bin/python -m py_compile app.py src/youtube_study/*.py
.venv/bin/python -m pytest
```

### Criterio de aceptación

- Fixtures no clasifican `QR` ni `SIM` como herramientas.
- Las herramientas conocidas se detectan correctamente.
- Conceptos principales no contienen muletillas conocidas.

⏸️ Pausa: revisar resultados en fragmentos limitados de videos locales antes de continuar.

---

## Fase 7 — Documentación, dependencias y calidad de desarrollo ✅

**Estado:** completada. `README.md`, las dependencias separadas, Ruff y el skill compartido ya están versionados y validados.

**Objetivo:** que una persona nueva pueda instalar, probar y entender el proyecto sin depender de datos locales ni configuración personal.

### Pasos

1. Actualizar `README.md`:
   - árbol real de archivos (`tools.json`, `concepts.json`, `study.md`, `anki.csv`);
   - comando `rebuild-library`;
   - errores y códigos de salida relevantes;
   - estado real de los próximos pasos.
2. Separar dependencias de runtime y desarrollo.
   - Mantener `requirements.txt` para ejecutar la aplicación.
   - Crear `requirements-dev.txt` para `pytest` y herramientas de calidad.
3. Añadir Ruff y su configuración mínima.
   - Ejecutar lint, formato e import sorting sin cambios funcionales.
4. Documentar versión mínima de Python y el flujo reproducible:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   python -m pytest
   ```

5. Mantener `.pi/skills/video-study-summary/` versionado como recurso compartido del repositorio.

### Verificación

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m py_compile app.py src/youtube_study/*.py
.venv/bin/python -m pytest
git status --short
```

### Criterio de aceptación

- La instalación de runtime no instala `pytest`.
- README refleja los comandos y artefactos reales.
- Ruff y tests pasan.
- El repositorio no deja configuración compartida sin versionar.

⏸️ Pausa: revisar documentación como una persona que clona el repositorio por primera vez.

---

## Fase 8 — Automatización CI y cierre ✅

**Estado:** completada. `.github/workflows/ci.yml` ejecuta la instalación limpia con Python 3.11, el smoke test de ayuda, Ruff, compilación y tests sin red ni datos locales.

**Objetivo:** validar automáticamente cada cambio en GitHub sin requerir datos reales, red, API keys ni servicios externos.

### Pasos

1. Añadir un workflow de GitHub Actions para la versión de Python soportada.
2. Ejecutar en CI:

   ```bash
   python -m ruff check .
   python -m py_compile app.py src/youtube_study/*.py
   python -m pytest
   ```

3. Añadir smoke tests de instalación limpia y de `python app.py --help`.
4. Medir cobertura e identificar módulos críticos sin tests; definir un umbral solo después de conocer la situación real.
5. Ejecutar localmente la misma validación que CI y actualizar roadmap/resumen de versión.

### Archivos previstos

```txt
.github/workflows/ci.yml
requirements-dev.txt
README.md
PLAN.md
```

### Reglas de CI

- No descargar videos de YouTube.
- No leer transcripciones reales de `data/`.
- No usar Ollama, API keys ni red.
- Usar únicamente fixtures pequeños incluidos en `tests/`.

### Verificación local equivalente

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m py_compile app.py src/youtube_study/*.py
.venv/bin/python -m pytest
```

### Criterio de aceptación

- El workflow pasa en GitHub Actions.
- La validación es reproducible en una instalación limpia.
- Los cambios futuros quedan protegidos por lint, compilación y tests automáticos.

⏸️ Pausa final: revisar CI, roadmap y estado del repositorio antes de marcar el plan como terminado.
