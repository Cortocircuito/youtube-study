# Evaluación de calidad

La calidad del análisis heurístico se mide con un corpus pequeño, versionado y sin red. El evaluador no usa LLM ni comparte reglas internas con el analizador.

## Corpus automático

`tests/fixtures/quality_corpus.v2.json` describe cuatro perfiles sanitizados:

- explicación estructurada de horticultura;
- explicación técnica de bases de datos;
- explicación conceptual de seguridad;
- directo ruidoso sobre eficiencia energética.

Cada caso referencia un VTT pequeño y objetivos revisados manualmente:

- `topics`: temas que las ideas seleccionadas deben cubrir;
- `standalone_claims`: relaciones que deben aparecer completas en un solo extracto;
- `noise_rules`: contenido que no debería llegar a una salida determinada;
- `question_targets`: preguntas cuya respuesta debe contener evidencia concreta.
- `concept_targets`: unigramas y conceptos compuestos con timestamps revisados.

Los aliases aceptan variantes explícitas. Los `marker_groups` exigen todos los grupos y aceptan cualquiera de las alternativas dentro de cada grupo. Los timestamps enlazan cada objetivo con los cues que justifican la anotación.

## Métricas

| Métrica | Dirección | Interpretación |
|---|---:|---|
| `topic_coverage` | mayor | Temas de referencia presentes en ideas con evidencia correcta |
| `standalone_claim_coverage` | mayor | Afirmaciones completas presentes en un mismo extracto |
| `concept_coverage` | mayor | Conceptos de referencia detectados por nombre |
| `compound_concept_coverage` | mayor | Conceptos compuestos detectados con timestamp correcto |
| `concept_timestamp_accuracy` | mayor | Conceptos detectados que apuntan a la evidencia anotada |
| `concept_timestamp_recall` | mayor | Referencias temporales anotadas que aparecen en la salida |
| `concept_precision` | mayor | Conceptos generados incluidos en el conjunto aceptado del fixture |
| `concept_redundancy_rate` | menor | Conceptos anidados que representan las mismas apariciones |
| `noise_rule_violation_rate` | menor | Reglas de ruido incumplidas |
| `summary_duplicate_rate` | menor | Pares de ideas casi duplicadas |
| `useful_question_precision` | mayor | Preguntas generadas que cubren un objetivo útil |
| `useful_question_recall` | mayor | Objetivos de pregunta cubiertos |
| `useful_question_f1` | mayor | Equilibrio entre precisión y cobertura de preguntas |

El reporte usa promedio macro para que un dominio no oculte otro. También compara cada caso por separado.

## Línea base

`tests/fixtures/quality_baseline.v3.json` registra el mejor comportamiento revisado hasta el momento. No representa un objetivo final: su función es impedir regresiones mientras permite mejorar cualquier métrica. Un hash enlaza el baseline con el JSON del corpus y los VTT exactos para impedir comparaciones entre revisiones diferentes.

Para inspeccionar el reporte actual:

```bash
python -m src.youtube_study.quality tests/fixtures/quality_corpus.v2.json
```

Para ejecutar las pruebas relacionadas:

```bash
python -m pytest tests/test_quality.py tests/test_quality_corpus.py
```

El baseline sólo debe actualizarse después de revisar el diff del reporte y confirmar que el cambio es una mejora real. Las métricas positivas no pueden bajar y las negativas no pueden subir.

Los `question_targets` forman el conjunto cerrado de preguntas consideradas útiles para cada fixture. Deben anotar todas las formulaciones pedagógicamente aceptables mediante grupos de aliases. Una pregunta nueva que sea válida pero no coincida exige revisar las anotaciones antes de interpretar el cambio de precisión. La métrica v3 exige que el timestamp principal pertenezca a la evidencia temporal del objetivo y empareja preguntas con objetivos uno a uno.

## Reconstrucción y ruido

El análisis reconstruye unidades textuales desde cues incompletos antes de seleccionar ideas. Cada unidad conserva los rangos exactos de todos sus cues, no añade puntuación y se cierra al encontrar puntuación terminal, un salto temporal o un límite de seguridad.

El filtro de ruido sólo afecta al material de estudio. Los cues originales permanecen en `AnalysisResult` y en las transcripciones exportadas. Para reducir falsos positivos, una unidad sólo se descarta cuando combina varias señales de producción, por ejemplo promoción explícita del canal, revisión de audio o una transición vacía. Las muletillas aisladas se penalizan durante la selección, pero no se eliminan ni se reescriben.

Después de la reconstrucción, `noisy_energy.noise_rule_violation_rate` es `0.0`. La fase de preguntas eliminó también las plantillas genéricas anotadas en los otros perfiles sin filtrar palabras válidas dentro de temas específicos.

## Conceptos compuestos

El formato de análisis v3 extrae candidatos contiguos de una a tres palabras desde unidades informativas. La puntuación combina frecuencia normalizada, distribución temporal y, para frases compuestas, asociación entre sus componentes. Los filtros conservan términos individuales útiles, permiten conectores internos como `de` o `entre` y descartan acciones discursivas genéricas.

`concepts.md`, `concepts.json` y `study.md` recorren la misma lista ordenada de conceptos. Los tres conservan menciones y timestamps; Markdown añade enlaces al video cuando existe `webpage_url`. Los `concept_targets` forman el conjunto cerrado aceptado para calcular precisión. El corpus v2 exige cobertura completa de sus conceptos anotados, precisión temporal completa, precisión conceptual macro superior a `0.96` y redundancia cero.

## Preguntas específicas

Las preguntas básicas se generan desde unidades explicativas y sólo una vez por fragmento fuente. El tema se toma de un concepto que aparece antes de la relación explicada, lo que favorece sujetos como `medidor enchufable` frente a términos incidentales de la misma oración.

Las preguntas prácticas conservan una frase breve en orden textual, no una única palabra elegida por frecuencia. Las preguntas de comprensión sólo se crean cuando hay una causa o condición explícita y no es ya una recomendación. El corpus revisado contiene objetivos de comprensión y obtiene precisión, recall y F1 macro de `1.0`; estos valores corresponden únicamente a los cuatro fixtures sanitizados y no sustituyen la evaluación humana de videos largos.

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
