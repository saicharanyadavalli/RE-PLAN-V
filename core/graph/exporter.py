"""Graph artifact serialization and export."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from core.graph.models import ReachableStateGraph


def export_graph_to_json(graph: ReachableStateGraph, file_path: Path | str) -> None:
    """Exports ReachableStateGraph to a formatted JSON file."""
    p = Path(file_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(graph.model_dump(), f, indent=2)


def export_graph_to_cytoscape(graph: ReachableStateGraph) -> Dict[str, Any]:
    """Serializes ReachableStateGraph into Cytoscape.js JSON structure."""
    return graph.to_cytoscape()
