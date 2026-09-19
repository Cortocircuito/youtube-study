# Evaluación de calidad

La calidad del análisis heurístico se mide con un corpus pequeño, versionado y sin red. El evaluador no usa LLM ni comparte reglas internas con el analizador.

## Corpus automático

`tests/fixtures/quality_corpus.v1.json` describe cuatro perfiles sanitizados:

- explicación estructurada de horticultura;
- explicación técnica de bases de datos;
- explicación conceptual de seguridad;
- directo ruidoso sobre eficiencia energética.

Cada caso referencia un VTT pequeño y objetivos revisados manualmente:

- `topics`: temas que las ideas seleccionadas deben cubrir;
- `standalone_claims`: relaciones que deben aparecer completas en un solo extracto;
- `noise_rules`: contenido que no debería llegar a una salida determinada;
- `question_targets`: preguntas cuya respuesta debe contener evidencia concreta.

Los aliases aceptan variantes explícitas. Los `marker_groups` exigen todos los grupos y aceptan cualquiera de las alternativas dentro de cada grupo. Los timestamps enlazan cada objetivo con los cues que justifican la anotación.

## Métricas

| Métrica | Dirección | Interpretación |
|---|---:|---|
| `topic_coverage` | mayor | Temas de referencia presentes en ideas con evidencia correcta |
| `standalone_claim_coverage` | mayor | Afirmaciones completas presentes en un mismo extracto |
| `noise_rule_violation_rate` | menor | Reglas de ruido incumplidas |
| `summary_duplicate_rate` | menor | Pares de ideas casi duplicadas |
| `useful_question_precision` | mayor | Preguntas generadas que cubren un objetivo útil |
| `useful_question_recall` | mayor | Objetivos de pregunta cubiertos |
| `useful_question_f1` | mayor | Equilibrio entre precisión y cobertura de preguntas |

El reporte usa promedio macro para que un dominio no oculte otro. También compara cada caso por separado.

## Línea base

`tests/fixtures/quality_baseline.v1.json` registra el mejor comportamiento revisado hasta el momento. No representa un objetivo final: actualmente expone una tasa macro de violación de ruido de `0.75` y baja precisión de preguntas. Su función es impedir regresiones mientras permite mejorar cualquier métrica. Un hash enlaza el baseline con el JSON del corpus y los VTT exactos para impedir comparaciones entre revisiones diferentes.

Para inspeccionar el reporte actual:

```bash
python -m src.youtube_study.quality tests/fixtures/quality_corpus.v1.json
```

Para ejecutar las pruebas relacionadas:

```bash
python -m pytest tests/test_quality.py tests/test_quality_corpus.py
```

El baseline sólo debe actualizarse después de revisar el diff del reporte y confirmar que el cambio es una mejora real. Las métricas positivas no pueden bajar y las negativas no pueden subir.

Los `question_targets` forman el conjunto cerrado de preguntas consideradas útiles para cada fixture. Deben anotar todas las formulaciones pedagógicamente aceptables mediante grupos de aliases. Una pregunta nueva que sea válida pero no coincida exige revisar las anotaciones antes de interpretar el cambio de precisión.

## Reconstrucción y ruido

El análisis reconstruye unidades textuales desde cues incompletos antes de seleccionar ideas. Cada unidad conserva los rangos exactos de todos sus cues, no añade puntuación y se cierra al encontrar puntuación terminal, un salto temporal o un límite de seguridad.

El filtro de ruido sólo afecta al material de estudio. Los cues originales permanecen en `AnalysisResult` y en las transcripciones exportadas. Para reducir falsos positivos, una unidad sólo se descarta cuando combina varias señales de producción, por ejemplo promoción explícita del canal, revisión de audio o una transición vacía. Las muletillas aisladas se penalizan durante la selección, pero no se eliminan ni se reescriben.

Después de esta fase, `noisy_energy.noise_rule_violation_rate` es `0.0`. Los otros casos todavía penalizan temas genéricos en preguntas; su mejora corresponde a la fase específica de generación de preguntas.

## Evaluación de videos largos

`quality/long_video_sample.v1.json` selecciona tres videos locales de entre dos y cuatro horas aproximadamente. Sus referencias permanecen marcadas como `pending_human_annotation`: una salida del analizador no puede utilizarse como referencia humana.

Procedimiento de anotación:

1. Revisar el video y sus capítulos, no el resumen generado por la aplicación.
2. Registrar entre 8 y 15 temas principales con timestamp inicial y final.
3. Registrar entre 10 y 20 ideas imprescindibles con una formulación breve y su evidencia temporal.
4. Marcar introducciones, promociones, música y conversaciones irrelevantes.
5. Medir el tiempo necesario para revisar `summary.md` y localizar las mismas ideas.
6. Hacer una segunda revisión independiente de una muestra antes de declarar completa la referencia.

La biblioteca local actual es principalmente tecnológica. Antes de extraer conclusiones generales deberá reemplazarse el perfil `contenido_mixto` o añadirse un cuarto video largo de otro dominio.

Los videos largos no forman parte de CI: `data/videos/` está ignorado y las pruebas no deben leer datos reales, descargar videos ni usar red.

## Añadir un caso

1. Crear un VTT corto, sanitizado y representativo en `tests/fixtures/`.
2. Añadir objetivos con timestamps al corpus.
3. Ejecutar el reporte y revisar manualmente cada coincidencia.
4. Añadir el caso y sus métricas actuales al baseline.
5. Ejecutar Ruff, compilación y toda la suite de pruebas.
