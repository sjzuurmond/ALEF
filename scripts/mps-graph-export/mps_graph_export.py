#!/usr/bin/env python3
"""Export a JetBrains MPS AST to standard graph formats.

MPS persists every model as an ``.mps`` XML file whose ``<node>`` elements *are*
the serialized abstract syntax tree.  This tool reads those files directly (no
running MPS instance required) and turns the AST into a graph:

* every ``SNode`` becomes a **vertex**;
* every parent -> child relationship becomes a **containment** edge (labelled
  with the child role);
* every ``SReference`` becomes a **reference** edge (labelled with the reference
  role), including references that cross model boundaries.

Concept names and role names are resolved through the ``<registry>`` that MPS
embeds in each model, so the output is human readable rather than a soup of
short ids.

The tool is deliberately **MPS-generic**: it knows about the MPS persistence
format (version 7-9) and nothing about any particular language or project.

Supported output formats: ``graphml`` (default), ``dot`` (Graphviz), ``gml``
and ``json`` (node-link).

Usage examples
--------------

    # One model to GraphML on stdout
    mps_graph_export.py path/to/model.mps

    # A whole module/project tree, containment + references, to a file
    mps_graph_export.py solutions/ -o ast.graphml

    # Only the containment tree, as Graphviz DOT
    mps_graph_export.py model.mps --format dot --edges containment -o tree.dot

    # Several formats at once, carrying node properties along
    mps_graph_export.py model.mps --format graphml,json --with-properties -o ast
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #


@dataclass
class Node:
    """A single MPS SNode (or a synthetic model root)."""

    gid: str                     # globally unique id: "<model-uuid>:<node-id>"
    node_id: str                 # id local to the owning model
    concept: str                 # resolved concept short name, or a raw index
    concept_fqn: str             # fully qualified concept name (may be empty)
    model_uuid: str              # owning model uuid
    model_name: str              # owning model name
    role: Optional[str]          # containment role in its parent (None for roots)
    label: str                   # display label (the "name" property when present)
    kind: str = "node"           # node | model | external
    properties: Dict[str, str] = field(default_factory=dict)


@dataclass
class Edge:
    source: str                  # source gid
    target: str                  # target gid
    kind: str                    # "containment" | "reference"
    role: str                    # role name (resolved when possible)


@dataclass
class Graph:
    nodes: Dict[str, Node] = field(default_factory=dict)
    edges: List[Edge] = field(default_factory=list)

    def add_node(self, node: Node) -> None:
        # First definition wins, but let a real node upgrade an "external"
        # placeholder that was created by a reference seen earlier.
        existing = self.nodes.get(node.gid)
        if existing is None or existing.kind == "external":
            self.nodes[node.gid] = node

    def ensure_external(self, gid: str, model_uuid: str, model_name: str,
                        node_id: str) -> None:
        if gid not in self.nodes:
            self.nodes[gid] = Node(
                gid=gid, node_id=node_id, concept="<external>",
                concept_fqn="", model_uuid=model_uuid, model_name=model_name,
                role=None, label=node_id, kind="external",
            )


# --------------------------------------------------------------------------- #
# Parsing MPS persistence
# --------------------------------------------------------------------------- #

_MODEL_REF_RE = re.compile(r"^[a-z]:([0-9a-fA-F-]+)\(([^)]*)\)")


def _parse_model_ref(ref: str) -> Tuple[str, str]:
    """Turn an MPS model reference into ``(uuid, name)``.

    Handles the common ``r:<uuid>(<name>)`` form and falls back to using the
    whole string as the uuid for anything exotic (java stubs, devkits, ...).
    """
    if not ref:
        return "", ""
    m = _MODEL_REF_RE.match(ref.strip())
    if m:
        return m.group(1), m.group(2)
    return ref.strip(), ref.strip()


class ModelFile:
    """Parsed view of a single ``.mps`` file."""

    def __init__(self, path: str, root: ET.Element):
        self.path = path
        self.root = root
        self.uuid, self.name = _parse_model_ref(root.get("ref", ""))

        # index -> human readable name, for concepts and roles alike.
        self.index_name: Dict[str, str] = {}
        self.index_fqn: Dict[str, str] = {}
        # import index -> (model uuid, model name)
        self.imports: Dict[str, Tuple[str, str]] = {}

        self._read_registry()
        self._read_imports()

    # -- registry / imports ------------------------------------------------- #

    def _read_registry(self) -> None:
        registry = self.root.find("registry")
        if registry is None:
            return
        for language in registry.findall("language"):
            for concept in language.findall("concept"):
                idx = concept.get("index")
                fqn = concept.get("name", "")
                if idx:
                    self.index_name[idx] = _short_concept(fqn)
                    self.index_fqn[idx] = fqn
                # Property / child / reference role indexes live under concepts.
                for role in list(concept):
                    ridx = role.get("index")
                    rname = role.get("name")
                    if ridx and rname:
                        self.index_name.setdefault(ridx, rname)

    def _read_imports(self) -> None:
        imports = self.root.find("imports")
        if imports is None:
            return
        for imp in imports.findall("import"):
            idx = imp.get("index")
            uuid, name = _parse_model_ref(imp.get("ref", ""))
            if idx:
                self.imports[idx] = (uuid, name)

    # -- resolution helpers ------------------------------------------------- #

    def concept_name(self, index: Optional[str]) -> str:
        if not index:
            return "<unknown>"
        return self.index_name.get(index, index)

    def concept_fqn(self, index: Optional[str]) -> str:
        if not index:
            return ""
        return self.index_fqn.get(index, "")

    def role_name(self, index: Optional[str]) -> str:
        if not index:
            return ""
        return self.index_name.get(index, index)


def _short_concept(fqn: str) -> str:
    """``jetbrains.mps.lang.core.structure.BaseConcept`` -> ``BaseConcept``."""
    if not fqn:
        return "<unknown>"
    if ".structure." in fqn:
        fqn = fqn.split(".structure.", 1)[1]
    return fqn.rsplit(".", 1)[-1]


# --------------------------------------------------------------------------- #
# Building the graph
# --------------------------------------------------------------------------- #

# The MPS "name" property (jetbrains.mps.lang.core.structure.INamedConcept.name)
# always carries this stable role index.
_NAME_ROLE_INDEX = "TrG5h"


class GraphBuilder:
    def __init__(self, with_properties: bool, model_nodes: bool):
        self.graph = Graph()
        self.with_properties = with_properties
        self.model_nodes = model_nodes

    def add_model(self, mf: ModelFile) -> None:
        model_gid = mf.uuid
        if self.model_nodes:
            self.graph.add_node(Node(
                gid=model_gid, node_id=mf.uuid, concept="<model>",
                concept_fqn="", model_uuid=mf.uuid, model_name=mf.name,
                role=None, label=mf.name or mf.uuid, kind="model",
            ))

        model_el = mf.root
        for node_el in _direct_children(model_el, "node"):
            self._walk(mf, node_el, parent_gid=model_gid if self.model_nodes else None)

    # -- recursion ---------------------------------------------------------- #

    def _walk(self, mf: ModelFile, el: ET.Element, parent_gid: Optional[str]) -> None:
        node_id = el.get("id")
        if node_id is None:
            return
        gid = f"{mf.uuid}:{node_id}"

        properties: Dict[str, str] = {}
        label = ""
        for prop in _direct_children(el, "property"):
            role_idx = prop.get("role")
            value = prop.get("value", "")
            role = mf.role_name(role_idx)
            properties[role] = value
            if role_idx == _NAME_ROLE_INDEX:
                label = value

        concept_idx = el.get("concept")
        concept = mf.concept_name(concept_idx)
        node = Node(
            gid=gid, node_id=node_id, concept=concept,
            concept_fqn=mf.concept_fqn(concept_idx),
            model_uuid=mf.uuid, model_name=mf.name,
            role=mf.role_name(el.get("role")),
            label=label or concept,
            properties=properties if self.with_properties else {},
        )
        self.graph.add_node(node)

        # Containment edge from parent.
        if parent_gid is not None:
            self.graph.edges.append(Edge(
                source=parent_gid, target=gid, kind="containment",
                role=node.role or "root",
            ))

        # Reference edges.
        for ref in _direct_children(el, "ref"):
            self._add_reference(mf, gid, ref)

        # Recurse into child nodes.
        for child in _direct_children(el, "node"):
            self._walk(mf, child, parent_gid=gid)

    def _add_reference(self, mf: ModelFile, source_gid: str, ref: ET.Element) -> None:
        role = mf.role_name(ref.get("role"))
        local = ref.get("node")
        remote = ref.get("to")

        if local is not None:                       # same-model reference
            target_gid = f"{mf.uuid}:{local}"
            self.graph.ensure_external(target_gid, mf.uuid, mf.name, local)
        elif remote is not None:                    # cross-model reference
            imp_idx, _, target_id = remote.partition(":")
            tgt_uuid, tgt_name = mf.imports.get(imp_idx, (imp_idx, imp_idx))
            target_gid = f"{tgt_uuid}:{target_id}"
            self.graph.ensure_external(target_gid, tgt_uuid, tgt_name, target_id)
        else:
            return

        self.graph.edges.append(Edge(
            source=source_gid, target=target_gid, kind="reference", role=role,
        ))


def _direct_children(el: ET.Element, tag: str) -> Iterable[ET.Element]:
    for child in el:
        if child.tag == tag:
            yield child


# --------------------------------------------------------------------------- #
# Discovery / loading
# --------------------------------------------------------------------------- #


def iter_mps_files(paths: Iterable[str]) -> Iterable[str]:
    seen = set()
    for p in paths:
        if os.path.isdir(p):
            for dirpath, _dirs, files in os.walk(p):
                for name in sorted(files):
                    if name.endswith(".mps"):
                        full = os.path.join(dirpath, name)
                        if full not in seen:
                            seen.add(full)
                            yield full
        elif p.endswith(".mps") and os.path.isfile(p):
            if p not in seen:
                seen.add(p)
                yield p
        else:
            print(f"warning: skipping non-model path {p!r}", file=sys.stderr)


def load_model(path: str) -> Optional[ModelFile]:
    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        print(f"warning: failed to parse {path}: {exc}", file=sys.stderr)
        return None
    root = tree.getroot()
    if root.tag != "model":
        return None
    return ModelFile(path, root)


# --------------------------------------------------------------------------- #
# Writers
# --------------------------------------------------------------------------- #


def _xml_escape(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def write_graphml(graph: Graph, out, with_properties: bool) -> None:
    out.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    out.write('<graphml xmlns="http://graphml.graphdrawing.org/xmlns">\n')

    node_keys = [
        ("label", "label", "string"),
        ("concept", "concept", "string"),
        ("conceptFqn", "conceptFqn", "string"),
        ("model", "model", "string"),
        ("kind", "kind", "string"),
        ("role", "role", "string"),
    ]
    edge_keys = [
        ("type", "type", "string"),
        ("edgeRole", "edgeRole", "string"),
    ]
    for key_id, name, typ in node_keys:
        out.write(f'  <key id="{key_id}" for="node" '
                  f'attr.name="{name}" attr.type="{typ}"/>\n')
    for key_id, name, typ in edge_keys:
        out.write(f'  <key id="{key_id}" for="edge" '
                  f'attr.name="{name}" attr.type="{typ}"/>\n')
    if with_properties:
        out.write('  <key id="properties" for="node" '
                  'attr.name="properties" attr.type="string"/>\n')

    out.write('  <graph edgedefault="directed">\n')
    for node in graph.nodes.values():
        out.write(f'    <node id="{_xml_escape(node.gid)}">\n')
        _graphml_data(out, "label", node.label)
        _graphml_data(out, "concept", node.concept)
        _graphml_data(out, "conceptFqn", node.concept_fqn)
        _graphml_data(out, "model", node.model_name)
        _graphml_data(out, "kind", node.kind)
        if node.role:
            _graphml_data(out, "role", node.role)
        if with_properties and node.properties:
            joined = "; ".join(f"{k}={v}" for k, v in node.properties.items())
            _graphml_data(out, "properties", joined)
        out.write('    </node>\n')

    for i, edge in enumerate(graph.edges):
        out.write(f'    <edge id="e{i}" source="{_xml_escape(edge.source)}" '
                  f'target="{_xml_escape(edge.target)}">\n')
        _graphml_data(out, "type", edge.kind)
        if edge.role:
            _graphml_data(out, "edgeRole", edge.role)
        out.write('    </edge>\n')

    out.write('  </graph>\n')
    out.write('</graphml>\n')


def _graphml_data(out, key: str, value: str) -> None:
    out.write(f'      <data key="{key}">{_xml_escape(value)}</data>\n')


def _dot_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def write_dot(graph: Graph, out, with_properties: bool) -> None:
    out.write("digraph MPS {\n")
    out.write("  rankdir=LR;\n")
    out.write('  node [shape=box, fontname="Helvetica"];\n')
    for node in graph.nodes.values():
        # Escape parts separately, then join with the DOT newline escape "\n".
        label = _dot_escape(node.concept)
        if node.label and node.label != node.concept:
            label += "\\n" + _dot_escape(node.label)
        attrs = f'label="{label}"'
        if node.kind == "model":
            attrs += ', shape=folder, style=filled, fillcolor="#dddddd"'
        elif node.kind == "external":
            attrs += ', style=dashed, color="#999999"'
        out.write(f'  "{_dot_escape(node.gid)}" [{attrs}];\n')
    for edge in graph.edges:
        if edge.kind == "reference":
            style = f'style=dashed, color="#3366cc", label="{_dot_escape(edge.role)}"'
        else:
            role = edge.role if edge.role != "root" else ""
            style = f'color="#000000", label="{_dot_escape(role)}"'
        out.write(f'  "{_dot_escape(edge.source)}" -> '
                  f'"{_dot_escape(edge.target)}" [{style}];\n')
    out.write("}\n")


def _gml_escape(text: str) -> str:
    return text.replace('"', "'")


def write_gml(graph: Graph, out, with_properties: bool) -> None:
    ids = {gid: i for i, gid in enumerate(graph.nodes)}
    out.write("graph [\n  directed 1\n")
    for node in graph.nodes.values():
        out.write("  node [\n")
        out.write(f"    id {ids[node.gid]}\n")
        out.write(f'    label "{_gml_escape(node.label)}"\n')
        out.write(f'    concept "{_gml_escape(node.concept)}"\n')
        out.write(f'    model "{_gml_escape(node.model_name)}"\n')
        out.write(f'    kind "{node.kind}"\n')
        out.write("  ]\n")
    for edge in graph.edges:
        if edge.source not in ids or edge.target not in ids:
            continue
        out.write("  edge [\n")
        out.write(f"    source {ids[edge.source]}\n")
        out.write(f"    target {ids[edge.target]}\n")
        out.write(f'    label "{_gml_escape(edge.role)}"\n')
        out.write(f'    type "{edge.kind}"\n')
        out.write("  ]\n")
    out.write("]\n")


def write_json(graph: Graph, out, with_properties: bool) -> None:
    import json

    nodes = []
    for node in graph.nodes.values():
        entry = {
            "id": node.gid,
            "label": node.label,
            "concept": node.concept,
            "conceptFqn": node.concept_fqn,
            "model": node.model_name,
            "modelUuid": node.model_uuid,
            "kind": node.kind,
        }
        if node.role:
            entry["role"] = node.role
        if with_properties and node.properties:
            entry["properties"] = node.properties
        nodes.append(entry)
    links = [
        {"source": e.source, "target": e.target, "type": e.kind, "role": e.role}
        for e in graph.edges
    ]
    json.dump({"directed": True, "nodes": nodes, "links": links}, out, indent=2)
    out.write("\n")


WRITERS = {
    "graphml": write_graphml,
    "dot": write_dot,
    "gml": write_gml,
    "json": write_json,
}

_EXTENSIONS = {"graphml": ".graphml", "dot": ".dot", "gml": ".gml", "json": ".json"}


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def build_graph(paths: List[str], edges: str, with_properties: bool,
                model_nodes: bool) -> Graph:
    builder = GraphBuilder(with_properties=with_properties, model_nodes=model_nodes)
    count = 0
    for path in iter_mps_files(paths):
        mf = load_model(path)
        if mf is None:
            continue
        builder.add_model(mf)
        count += 1
    if count == 0:
        print("warning: no MPS models found", file=sys.stderr)

    graph = builder.graph
    if edges != "both":
        wanted = "containment" if edges == "containment" else "reference"
        graph.edges = [e for e in graph.edges if e.kind == wanted]
    return graph


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export a JetBrains MPS AST to GraphML and other graph formats.",
    )
    parser.add_argument("paths", nargs="+",
                        help="One or more .mps files or directories to scan.")
    parser.add_argument("-f", "--format", default="graphml",
                        help="Comma-separated output formats: "
                             "graphml, dot, gml, json (default: graphml).")
    parser.add_argument("-o", "--output",
                        help="Output file, or basename when several formats are "
                             "requested. Defaults to stdout for a single format.")
    parser.add_argument("--edges", choices=["both", "containment", "references"],
                        default="both",
                        help="Which edges to emit (default: both).")
    parser.add_argument("--with-properties", action="store_true",
                        help="Carry SNode properties into the output.")
    parser.add_argument("--no-model-nodes", action="store_true",
                        help="Do not add a synthetic vertex per model; root "
                             "SNodes become graph roots instead.")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])

    formats = [f.strip() for f in args.format.split(",") if f.strip()]
    for fmt in formats:
        if fmt not in WRITERS:
            print(f"error: unknown format {fmt!r} "
                  f"(choose from {', '.join(WRITERS)})", file=sys.stderr)
            return 2

    graph = build_graph(
        args.paths, edges=args.edges,
        with_properties=args.with_properties,
        model_nodes=not args.no_model_nodes,
    )

    n_nodes = len(graph.nodes)
    n_cont = sum(1 for e in graph.edges if e.kind == "containment")
    n_ref = sum(1 for e in graph.edges if e.kind == "reference")
    print(f"exported {n_nodes} nodes, {n_cont} containment edges, "
          f"{n_ref} reference edges", file=sys.stderr)

    # Single format to stdout when no output given.
    if len(formats) == 1 and not args.output:
        WRITERS[formats[0]](graph, sys.stdout, args.with_properties)
        return 0

    for fmt in formats:
        if len(formats) == 1:
            path = args.output
        else:
            base = args.output or "mps-ast"
            base = _strip_known_ext(base)
            path = base + _EXTENSIONS[fmt]
        with open(path, "w", encoding="utf-8") as out:
            WRITERS[fmt](graph, out, args.with_properties)
        print(f"wrote {path}", file=sys.stderr)
    return 0


def _strip_known_ext(base: str) -> str:
    for ext in _EXTENSIONS.values():
        if base.endswith(ext):
            return base[: -len(ext)]
    return base


if __name__ == "__main__":
    raise SystemExit(main())
