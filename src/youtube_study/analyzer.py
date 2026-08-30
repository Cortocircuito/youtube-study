from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from .transcript import Cue, chunk_by_minutes

STOPWORDS = set("""
a acá ahí al algo algunas algunos ante antes aquí así aunque cada casi como con contra cual cuando de del desde donde dos e el ella ellas ellos en entre era eran es esa esas ese eso esos esta estaba están estar estas esté este esto estos fue han hasta hay la las le les lo los más me mi mis muy no nos o para pero por porque que se ser si sin sobre son su sus te tenía tienen todo todos tu un una unas unos y ya yo bien entonces ejemplo ahora ver voy vos qué cómo cosa cosas hacer ahí acá directamente caso gente tener tiene tengo está estoy estás estamos están vas vamos puedo podés podes puede pueden podría verdad realmente mostrar miren vean después acá abajo arriba
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
    }
    mentions: list[ToolMention] = []
    for name, desc in KNOWN_TOOLS.items():
        names = aliases.get(name, [name])
        count = 0
        for alias in names:
            pattern = r"(?<![\w.-])" + re.escape(alias.lower()) + r"(?![\w.-])"
            count += len(re.findall(pattern, lower))
        if count:
            mentions.append(ToolMention(name, count, desc))
    return sorted(mentions, key=lambda x: x.count, reverse=True)


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


def questions(cues: list[Cue], tools: list[ToolMention], limit: int = 10) -> list[str]:
    qs = []
    for tool in tools[:8]:
        qs.append(f"¿Qué papel cumple {tool.name} en el flujo explicado?")
    text = full_text(cues).lower()
    if "puerto 22" in text:
        qs.append("¿Por qué no conviene abrir el puerto 22 directamente al router?")
    if "authorized keys" in text or "llave" in text:
        qs.append("¿Cuál es la diferencia entre llave pública y llave privada en SSH?")
    if "qr" in text:
        qs.append("¿Por qué el QR de emparejamiento debe mantenerse privado?")
    return qs[:limit]


def flashcards(tools: list[ToolMention], qs: list[str]) -> list[tuple[str, str]]:
    cards = [(f"¿Qué es {tool.name}?", tool.description) for tool in tools[:10]]
    for q in qs[:5]:
        cards.append((q, "Respóndelo usando la sección correspondiente de la transcripción."))
    return cards
