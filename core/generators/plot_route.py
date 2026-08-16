# SPDX-License-Identifier: Fair-Source-1.0
"""Shared plot-ordered cross-area route extraction (issue #159, slice 159-C).

Dependency-neutral pure helper imported by BOTH the classic finalizer
(`module_builder.finalize_locations_and_connections`) and the report-only detector
(`story_first.validators.validate_plot_route_agreement`), so they agree on the
expected cross-area edge set by construction. This module imports nothing from
`module_builder` or the heavy validators to avoid a circular dependency.

Contract:
- `nextPoints` is AUTHORITATIVE for graph structure whenever it yields at least one
  usable cross-area edge (do NOT union raw plotPoints-adjacency into a branched
  nextPoints graph -- that would invent sibling edges).
- The plotPoints-order ADJACENCY fallback fires ONLY when the nextPoints graph has
  ZERO usable cross-area edges (legacy/degenerate plots).
- Every PLOT-REFERENCED area is guaranteed reachable: if `nextPoints` leaves one
  unreachable (partial coverage), code HEALS the gap by adding the minimal
  plot-order adjacency connection(s). A module is always produced and always fully
  connected -- the build is NEVER aborted for an unreachable area. The healing
  edges are reported so the detector can surface them as information.
"""

from typing import Any, Dict, List, Set, Tuple


def _plot_area_sequence(plot: Dict[str, Any], valid_areas: Set[str]) -> List[str]:
    """Ordered plotPoints area IDs restricted to real areas (consecutive dupes collapsed)."""
    seq: List[str] = []
    for point in plot.get("plotPoints") or []:
        area = point.get("location")
        if area in valid_areas and (not seq or seq[-1] != area):
            seq.append(area)
    return seq


def _dedupe_directed(pairs: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """Keep first-seen direction per UNDIRECTED area pair (the physical door is bidirectional)."""
    out: List[Tuple[str, str]] = []
    seen: Set[frozenset] = set()
    for a, b in pairs:
        if a == b:
            continue
        key = frozenset((a, b))
        if key in seen:
            continue
        seen.add(key)
        out.append((a, b))
    return out


def _nextpoints_edges(plot: Dict[str, Any], valid_areas: Set[str]) -> List[Tuple[str, str]]:
    """Directed cross-area edges from every nextPoints link (authoritative structure)."""
    point_by_id = {p.get("id"): p for p in (plot.get("plotPoints") or []) if p.get("id")}
    pairs: List[Tuple[str, str]] = []
    for point in plot.get("plotPoints") or []:
        a = point.get("location")
        if a not in valid_areas:
            continue
        for nxt in point.get("nextPoints") or []:
            b = point_by_id.get(nxt, {}).get("location")
            if b in valid_areas and b != a:
                pairs.append((a, b))
    return _dedupe_directed(pairs)


def _adjacency_edges(plot: Dict[str, Any], valid_areas: Set[str]) -> List[Tuple[str, str]]:
    """Directed cross-area edges from plotPoints ADJACENCY (legacy fallback only)."""
    seq = _plot_area_sequence(plot, valid_areas)
    return _dedupe_directed(list(zip(seq, seq[1:])))


def _reachable(edges: List[Tuple[str, str]], roots: List[str]) -> Set[str]:
    """Undirected BFS closure from roots (edges are physical bidirectional doors)."""
    adj: Dict[str, Set[str]] = {}
    for a, b in edges:
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    seen: Set[str] = set()
    stack = [r for r in roots]
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(adj.get(node, ()))
    return seen


def extract_plot_route(areas_by_id: Dict[str, Any], plot: Dict[str, Any]) -> Dict[str, Any]:
    """Return the shared cross-area route facts for a module.

    Result dict:
      edges: ordered list of directed (from_area, to_area), first-occurrence direction,
             deduped per undirected pair -- the expected cross-area gateway set.
      source: "nextpoints" | "adjacency_fallback" | "none".
      plot_areas: ordered distinct area IDs referenced by plot points (real areas).
      unreachable_plot_areas: plot-referenced areas NOT reachable from the plot root
             via the edge graph (case (a) hard-defect candidates).
    """
    if not isinstance(areas_by_id, dict) or not isinstance(plot, dict):
        return {"edges": [], "source": "none", "plot_areas": [], "unreachable_plot_areas": []}
    valid_areas = set(areas_by_id)
    seq = _plot_area_sequence(plot, valid_areas)
    plot_areas = list(dict.fromkeys(seq))  # ordered distinct

    edges = _nextpoints_edges(plot, valid_areas)
    if edges:
        source = "nextpoints"
    else:
        edges = _adjacency_edges(plot, valid_areas)
        source = "adjacency_fallback" if edges else "none"

    # HEAL any plot-referenced area left unreachable (partial nextPoints coverage):
    # add the minimal plot-order adjacency connection so the module is always fully
    # connected. Agentic-first (plot drives the route) with a code safeguard that
    # corrects -- never an abort.
    healed_edges: List[Tuple[str, str]] = []
    if len(plot_areas) > 1:
        root = plot_areas[0]
        existing = {frozenset(e) for e in edges}
        reached = _reachable(edges, [root]) | {root}
        for idx, area in enumerate(plot_areas):
            if area in reached:
                continue
            # connect this orphan to its plot-order predecessor (already connected
            # because we walk in order), falling back to the plot root.
            neighbor = plot_areas[idx - 1] if idx > 0 else root
            connector = (neighbor, area)
            if frozenset(connector) not in existing:
                edges = edges + [connector]
                existing.add(frozenset(connector))
                healed_edges.append(connector)
            reached = _reachable(edges, [root]) | {root}

    return {
        "edges": edges,
        "source": source,
        "plot_areas": plot_areas,
        "healed_edges": healed_edges,
        # kept for compatibility; always empty now (every plot area is healed reachable)
        "unreachable_plot_areas": [],
    }
