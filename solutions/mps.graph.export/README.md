# mps.graph.export — in-IDE MPS AST → graph exporter

An MPS solution that exports a JetBrains MPS AST to standard graph formats
(GraphML, Graphviz DOT, …) from **inside the MPS IDE**, using the MPS **Open
API**. It is the native counterpart of the offline
[`scripts/mps-graph-export`](../../scripts/mps-graph-export/) tool:

| | `scripts/mps-graph-export` | `mps.graph.export` (this solution) |
|---|---|---|
| Reads | `.mps` files on disk (persistence XML) | the **live** model via the Open API |
| Runs | anywhere, no MPS needed | inside MPS (Tools / context menu action) |
| Needs MPS | no | yes |
| Graph produced | identical: SNodes + containment + references | identical |

Both are **MPS-generic** — they know the MPS meta-model and nothing about ALEF
or any particular language.

## Architecture

The traversal is separated from the output format so that **each format is one
class** — "a generator per export language":

```
        ┌────────────────────┐        vertex()/edge()      ┌──────────────┐
 SModel │  MpsGraphExporter  │ ─────────────────────────▶ │  GraphSink   │
 SNode  │  (Open API walk)   │                            │  (interface) │
        └────────────────────┘                            └──────┬───────┘
                                                                 │ implementations
                                          ┌──────────────────────┼───────────────────┐
                                    GraphmlSink              DotSink            (GmlSink, JsonSink, …)
```

* `MpsGraphExporter` walks `SModel.getRootNodes()` / `SNode.getChildren()`
  (containment) and `SNode.getReferences()` (references), resolving concept and
  role names reflectively, and pushes vertices/edges into a `GraphSink`.
* `GraphSink` is the format contract; adding SVG, Cypher, GEXF, … means adding
  one class and never touching the traversal.
* `ExportAstToGraphAction` is the thin menu action that picks the selected model
  or node, runs the exporter under a read action, and writes the files.

The mapping to the AST is exactly the same as the offline tool:

| AST | Graph |
|-----|-------|
| `SNode` | vertex (label = node name, else concept) |
| parent → child | **containment** edge (child role) |
| `SReference` | **reference** edge (reference role), incl. cross-model |
| `SModel` | optional synthetic vertex owning its roots |

## Status — read this

The exporter logic lives under [`reference/exporter/`](reference/exporter/) as
plain Java. It is complete and the format-agnostic writers (`GraphSink`,
`GraphmlSink`, `DotSink`) are compiled and tested (they emit well-formed GraphML
with unique keys and valid DOT). `MpsGraphExporter` and `ExportAstToGraphAction`
target the MPS Open API, so they compile only against the MPS SDK.

**The `.mps` plugin model is intentionally not committed.** MPS models are
GUID-bearing XML that must be authored/validated in the MPS editor; a
hand-written one that has never been opened in MPS risks failing to load the
whole module. This solution ships as a valid, empty module plus the reference
code, ready to be realised in MPS.

### Realising it in MPS (a few minutes in the editor)

1. Open this project in MPS and locate the `mps.graph.export` solution (its
   dependencies are already declared in `mps.graph.export.msd`:
   MPS.OpenAPI / Core / Platform / IDEA + `lang.plugin`).
2. Add a **plugin** aspect model (e.g. `models/plugin.mps`) using
   `jetbrains.mps.lang.plugin`.
3. Create the classes by pasting the reference Java into BaseLanguage classes —
   MPS supports **Edit ▸ Paste as ▸ BaseLanguage** for exactly this. Paste
   `GraphSink`, `GraphmlSink`, `DotSink`, `MpsGraphExporter`.
4. Add an **Action** `ExportAstToGraph` with an `execute` block containing the
   body of `ExportAstToGraphAction.doExecute` (get `CONTEXT_MODEL` / `NODE` via
   action data parameters, run the exporter under `runReadAction`, write files),
   and add it to an ActionGroup on the model/node popup.
5. Build the solution; MPS generates and compiles the Java.

Once the action exists, extend to more formats by pasting another `GraphSink`
implementation and adding it to the action's sink list.

## Why not MPS *generators*?

MPS "generators" are template-based, per-language model-to-model
transformations (ending in TextGen). A *generic* "any AST → graph" export is not
expressible that way without a target graph language plus per-language mapping
rules. The reflective Open API traversal here is the right tool; the
"generator per format" split (one `GraphSink` per output) gives the same
pluggability people want from generators, at the output stage.
