from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from .transcript import Cue, chunk_by_minutes

ANALYSIS_FORMAT_VERSION = 1

STOPWORDS = set("""
a acá ahí al algo algunas algunos ante antes aquí así aunque cada casi como con contra cual cuando de del desde donde dos e el ella ellas ellos en entre era eran es esa esas ese eso esos esta estaba están estar estas esté este esto estos fue han hasta hay la las le les lo los más me mi mis muy no nos o para pero por porque que se ser si sin sobre son su sus te tenía tienen tenemos todo todos tu un una unas unos y ya yo bien entonces ejemplo ahora ver voy vos qué cómo cosa cosas hacer ahí acá directamente caso gente tener tiene tengo está estoy estás estamos están vas vamos puedo podés podes puede pueden podría verdad realmente mostrar miren vean después acá abajo arriba también bien
""".split())

KNOWN_TOOLS = {
    "tailscale": "Red privada/VPN mesh para conectar dispositivos sin abrir puertos públicos.",
    "openssh": "Servidor/cliente SSH para entrar remotamente en una máquina.",
    "ssh": "Protocolo de acceso remoto seguro usado para entrar al equipo.",
    "moshi": "App móvil para gestionar conexiones SSH/Mosh y agentes desde el teléfono.",
    "herdr": "Multiplexor de terminales orientado a agentes; mantiene sesiones vivas.",
    "tmux": "Multiplexor clásico para mantener sesiones de terminal persistentes.",
    "whisper": "Sistema de transcripción/dictado de voz.",
    "claude": "Modelo/agente de IA usado para tareas de código.",
    "codex": "Agente/modelo de IA de OpenAI para tareas de código.",
    "ollama": "Herramienta para ejecutar modelos de IA localmente.",
    "llama.cpp": "Motor ligero para ejecutar modelos LLM localmente.",
    "storybook": "Herramienta para desarrollar y probar componentes UI aislados.",
    "ufw": "Firewall simple de Ubuntu/Linux.",
    "systemd": "Sistema de servicios de Linux; permite dejar procesos activos.",
    "beelink": "Mini PC mencionada como máquina encendida 24/7.",
}

@dataclass
class ToolMention:
    name: str
    count: int
    description: str
    kind: str = "known"


@dataclass
class ConceptMention:
    name: str
    score: int
    count: int
    timestamps: list[str]


@dataclass
class AnalysisResult:
    cues: list[Cue]
    text: str
    keywords: list[tuple[str, int]]
    tools: list[ToolMention]
    ideas: list[tuple[str, str]]
    sections: list[tuple[str, str, list[str]]]
    concepts: list[ConceptMention]
    questions: dict[str, list[str]]
    cards: list[dict[str, str]]
    format_version: int = ANALYSIS_FORMAT_VERSION


def full_text(cues: list[Cue]) -> str:
    return " ".join(cue.text for cue in cues)


def keywords(text: str, limit: int = 25) -> list[tuple[str, int]]:
    words = re.findall(r"[a-záéíóúñü0-9][a-záéíóúñü0-9_.-]{2,}", text.lower())
    words = [w.strip(".-_") for w in words if w not in STOPWORDS and not w.isdigit()]
    return Counter(words).most_common(limit)


def detect_tools(text: str) -> list[ToolMention]:
    lower = text.lower()
    aliases = {
        "moshi": ["moshi", "moshie", "mochi"],
        "herdr": ["herdr", "herder", "gerd"],
        "claude": ["claude", "claudio", "clou"],
    }
    mentions: list[ToolMention] = []
    for name, desc in KNOWN_TOOLS.items():
        names = aliases.get(name, [name])
        count = 0
        for alias in names:
            pattern = r"(?<![\w.-])" + re.escape(alias.lower()) + r"(?![\w.-])"
            count += len(re.findall(pattern, lower))
        if count:
            mentions.append(ToolMention(name, count, desc, "known"))
    mentions.extend(detect_unknown_tools(text, {tool.name for tool in mentions}))
    return sorted(mentions, key=lambda x: (x.kind != "known", -x.count, x.name))


def detect_unknown_tools(text: str, known_names: set[str], limit: int = 8) -> list[ToolMention]:
    """Detect possible tool/product names not present in KNOWN_TOOLS."""
    candidates = re.findall(r"\b[a-zA-Z][a-zA-Z0-9]*(?:[.-][a-zA-Z0-9]+)+\b", text)
    candidates += re.findall(r"\b[A-Z]{2,8}\b", text)
    candidates += re.findall(r"\b[A-Z][a-z]+(?:[A-Z][a-z0-9]+)+\b", text)
    counts = Counter(candidates)
    results: list[ToolMention] = []
    ignored = {"Entonces", "Ahora", "Bien", "Mirá", "Vean", "Vos", "Para", "Esto", "Como"}
    for name, count in counts.most_common():
        normalized = name.lower().strip(".-")
        if normalized in known_names or normalized in STOPWORDS or name in ignored or count < 2:
            continue
        results.append(ToolMention(name, count, "Posible herramienta o nombre propio detectado heurísticamente.", "unknown"))
        if len(results) >= limit:
            break
    return results


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text)
    if len(parts) < 10:
        parts = re.split(r"\s+(?=(?:Entonces|Ahora|Bien|Primero|Segundo|Tercero|Si vos|La idea)\b)", text)
    return [p.strip() for p in parts if len(p.strip()) > 60]


def important_ideas(cues: list[Cue], limit: int = 12) -> list[tuple[str, str]]:
    text = full_text(cues)
    top_words = {w for w, _ in keywords(text, 20)}
    # Agrupamos varias líneas de subtítulos para evitar frases cortadas.
    grouped: list[tuple[str, str]] = []
    for i in range(0, len(cues), 3):
        chunk = cues[i:i + 3]
        if not chunk:
            continue
        grouped.append((chunk[0].start, " ".join(c.text for c in chunk)))

    scored: list[tuple[float, str, str]] = []
    priority = ["instal", "config", "ssh", "tailscale", "puerto", "llave", "teléfono", "notificacion", "agente", "multiplex", "hook", "qr", "token", "firewall"]
    for ts, sent in grouped:
        low = sent.lower()
        ws = re.findall(r"[a-záéíóúñü0-9_.-]{3,}", low)
        score = sum(1 for w in ws if w in top_words)
        score += sum(3 for p in priority if p in low)
        score += min(len(ws), 60) / 60
        if len(ws) < 12:
            score -= 4
        scored.append((score, ts, sent))
    selected = sorted(scored, reverse=True)[:limit]
    return [(ts, sent) for _, ts, sent in sorted(selected, key=lambda x: x[1])]


def section_summaries(cues: list[Cue], minutes: int = 5) -> list[tuple[str, str, list[str]]]:
    sections = []
    for start, end, text in chunk_by_minutes(cues, minutes):
        kws = [w for w, _ in keywords(text, 8)]
        sentences = split_sentences(text)
        ideas = sentences[:3] if sentences else [text[:240].strip() + "..."]
        sections.append((f"{start} - {end}", ", ".join(kws[:5]), ideas))
    return sections


def concept_mentions(cues: list[Cue], limit: int = 20) -> list[ConceptMention]:
    text = full_text(cues)
    top = keywords(text, limit)
    concepts: list[ConceptMention] = []
    for word, count in top:
        timestamps: list[str] = []
        pattern = re.compile(r"(?<![\w.-])" + re.escape(word) + r"(?![\w.-])", re.IGNORECASE)
        for cue in cues:
            if pattern.search(cue.text):
                timestamps.append(cue.start)
            if len(timestamps) >= 5:
                break
        score = count + min(len(timestamps), 5) * 2
        concepts.append(ConceptMention(word, score, count, timestamps))
    return sorted(concepts, key=lambda item: item.score, reverse=True)


def questions(cues: list[Cue], tools: list[ToolMention], limit: int = 10) -> dict[str, list[str]]:
    text = full_text(cues).lower()
    basic = [f"¿Qué es {tool.name} y para qué se menciona?" for tool in tools[:4]]
    comprehension = [f"¿Qué papel cumple {tool.name} en el flujo explicado?" for tool in tools[:6]]
    practice: list[str] = []
    if "puerto 22" in text:
        practice.append("¿Por qué no conviene abrir el puerto 22 directamente al router?")
    if "authorized keys" in text or "llave" in text:
        practice.append("¿Cuál es la diferencia entre llave pública y llave privada en SSH?")
    if "qr" in text:
        practice.append("¿Por qué el QR de emparejamiento debe mantenerse privado?")
    if tools:
        practice.append("¿Qué pasos repetirías en tu máquina después de ver el video?")
    return {
        "basicas": basic[:limit],
        "comprension": comprehension[:limit],
        "practicas": practice[:limit],
    }


def flatten_questions(qs: dict[str, list[str]]) -> list[str]:
    return [question for group in qs.values() for question in group]


def flashcards(tools: list[ToolMention], qs: dict[str, list[str]]) -> list[dict[str, str]]:
    cards = [
        {"question": f"¿Qué es {tool.name}?", "answer": tool.description, "tags": f"tool {tool.kind} {tool.name}"}
        for tool in tools[:10]
    ]
    for q in flatten_questions(qs)[:5]:
        cards.append({"question": q, "answer": "Respóndelo usando la sección correspondiente de la transcripción.", "tags": "question review"})
    return cards


def analyze_cues(cues: list[Cue]) -> AnalysisResult:
    text = full_text(cues)
    tools = detect_tools(text)
    qs = questions(cues, tools)
    return AnalysisResult(
        cues=cues,
        text=text,
        keywords=keywords(text),
        tools=tools,
        ideas=important_ideas(cues),
        sections=section_summaries(cues),
        concepts=concept_mentions(cues),
        questions=qs,
        cards=flashcards(tools, qs),
    )
