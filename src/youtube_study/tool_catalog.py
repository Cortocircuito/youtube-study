from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CATALOG_PATH = Path(__file__).with_suffix(".json")


def load_tool_catalog(path: Path = CATALOG_PATH) -> tuple[dict[str, dict[str, Any]], set[str]]:
    """Load the versioned tool catalog used by the heuristic analyzer."""
    data = json.loads(path.read_text(encoding="utf-8"))
    tools = data.get("tools", [])
    if not isinstance(tools, list):
        raise ValueError("El catálogo de herramientas debe contener una lista 'tools'.")

    catalog: dict[str, dict[str, Any]] = {}
    for tool in tools:
        if not isinstance(tool, dict) or not all(isinstance(tool.get(field), str) for field in ("name", "description", "category")):
            raise ValueError("Cada herramienta del catálogo necesita name, description y category.")
        catalog[tool["name"].lower()] = tool

    exclusions = data.get("unknown_candidate_exclusions", [])
    if not isinstance(exclusions, list) or not all(isinstance(item, str) for item in exclusions):
        raise ValueError("unknown_candidate_exclusions debe ser una lista de texto.")
    return catalog, {item.lower() for item in exclusions}


TOOL_CATALOG, UNKNOWN_CANDIDATE_EXCLUSIONS = load_tool_catalog()
