# MPS AST → graph exporter

`mps_graph_export.py` turns a [JetBrains MPS](https://www.jetbrains.com/mps/)
abstract syntax tree into a standard graph file (GraphML, Graphviz DOT, GML or
node-link JSON) so it can be inspected, diffed or visualised in tools such as
[yEd](https://www.yworks.com/products/yed), [Gephi](https://gephi.org/),
[Cytoscape](https://cytoscape.org/) or Graphviz.

It is **MPS-generic**: it understands the MPS persistence format and nothing
about ALEF or any particular language, so it works on any MPS project.

## What it does

MPS stores every model as an `.mps` XML file whose `<node>` elements *are* the
serialized AST. The exporter reads those files directly — **no running MPS
instance is required** — and emits a directed graph:

| AST concept | Graph element |
|-------------|---------------|
| `SNode` | vertex (labelled with concept + `name` property) |
| parent → child | **containment** edge (labelled with the child role) |
| `SReference` | **reference** edge (labelled with the reference role) |
| model | optional synthetic vertex owning its root nodes |

Concept and role names are resolved through the `<registry>` block MPS embeds
in each model, so output is readable (`ConceptDeclaration`, `items`, `target`)
rather than short ids. References that cross model boundaries are resolved via
the model's `<imports>`; the referenced node appears as an `external`
placeholder vertex when its model is not part of the export.

## Usage

Requires only Python 3.8+ (standard library, no dependencies).

```bash
# One model to GraphML on stdout
scripts/mps-graph-export/mps_graph_export.py languages/regelspraak/languageModels/structure.mps

# A whole module/project tree to a GraphML file
scripts/mps-graph-export/mps_graph_export.py solutions/ -o ast.graphml

# Only the containment tree, as Graphviz DOT
scripts/mps-graph-export/mps_graph_export.py model.mps --format dot --edges containment -o tree.dot

# Several formats at once, carrying SNode properties along
scripts/mps-graph-export/mps_graph_export.py model.mps --format graphml,json --with-properties -o ast
```

Any mix of `.mps` files and directories may be given; directories are scanned
recursively for `.mps` files.

### Options

| Option | Description |
|--------|-------------|
| `-f, --format` | Comma-separated: `graphml` (default), `dot`, `gml`, `json`. |
| `-o, --output` | Output file, or basename when several formats are requested. Defaults to stdout for a single format. |
| `--edges` | `both` (default), `containment`, or `references`. |
| `--with-properties` | Carry SNode properties into the output. |
| `--no-model-nodes` | Do not add a synthetic vertex per model; root SNodes become graph roots instead. |

When several formats are requested the extension is appended to `--output`
(e.g. `-o ast -f graphml,json` writes `ast.graphml` and `ast.json`).

## Output attributes

* **Nodes** carry `label`, `concept`, `conceptFqn`, `model`, `kind`
  (`node` / `model` / `external`) and the containment `role`. With
  `--with-properties` the SNode properties are attached too.
* **Edges** carry `type` (`containment` / `reference`) and the role name.

Vertex ids are globally unique (`<model-uuid>:<node-id>`) so several models can
be exported into a single connected graph and cross-model references line up.

## Tests

```bash
python3 -m unittest discover -s scripts/mps-graph-export/tests
```

The tests run against a small synthetic model (`tests/sample.mps`) and cover
concept/role resolution, containment and (same- and cross-model) reference
edges, edge filtering, and every output writer.

## Running it as an MPS plugin instead

This script deliberately works offline against `.mps` files, which makes it
portable and testable. If you would rather trigger the export from inside the
MPS IDE (e.g. a *Tools* menu action that exports the currently selected model
or node), the same graph-building logic maps directly onto the MPS Open API:

* iterate `SModel.getRootNodes()` / `SNode.getChildren()` for containment;
* iterate `SNode.getReferences()` for reference edges;
* read `SNode.getConcept().getName()` and `link.getRole()` for labels.

Wrapping that in a `jetbrains.mps.lang.plugin` action and reusing the writers
here would give an in-IDE exporter with identical output. Ask if you'd like
that plugin variant added.
