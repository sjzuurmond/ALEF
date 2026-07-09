# The MPS Open API, and how this exporter uses it

This note explains `org.jetbrains.mps.openapi` — the API `MpsGraphExporter`
(see [`reference/exporter/`](reference/exporter/)) is written against — and
maps each piece directly onto the graph export. It assumes you've read the
[solution README](README.md) for the bigger picture (Open API exporter vs. the
offline [`scripts/mps-graph-export`](../../scripts/mps-graph-export/) tool).

## What "Open API" means in MPS

MPS ships two layers of API for working with models:

* **`jetbrains.mps.smodel.*`** — the original, concrete implementation. Fast,
  MPS-internal, but ties calling code to MPS's own classes.
* **`org.jetbrains.mps.openapi.*`** — a smaller, stable, *interface-only*
  facade over the same data (`SNode`, `SModel`, `SReference`, …). It's the
  supported way to write MPS-version-tolerant tooling: plugins, checkers,
  migrations, and — here — an exporter.

"Open API" is not a language in the MPS-DSL sense (it defines no concepts of
its own). It's a plain Java API for asking *any* model, in any language,
questions like "what's your concept?", "what are your children?", "what do you
reference?" — without the caller needing to know the language beforehand.
That reflective, language-agnostic quality is exactly why it fits an AST
exporter: the exporter must work on regelspraak models, gegevensspraak models,
a language's own structure model, or a model from a project nobody involved in
this tool has ever seen.

## The core interfaces, and their graph meaning

| Open API type | What it represents | Graph element it becomes |
|---|---|---|
| `SNode` | one AST node (an instance of some concept) | a **vertex** |
| `SModel` | a model (a set of root `SNode`s) | an optional **vertex** whose children are the roots |
| `SModule` | a language/solution/devkit (a set of models) | not modelled directly; used only to enumerate `SModel`s |
| `SConcept` / `SAbstractConcept` | the node's concept (e.g. `ConceptDeclaration`, or any concept declared in a project's own languages) | the vertex's `concept` / `conceptFqn` attributes |
| `SContainmentLink` | the *role* a child is held under (e.g. `items`, `method`, `linkDeclaration`) | the **role** label on a containment edge |
| `SReference` | one resolved-or-not link from a node to a target node | a **reference edge** |
| `SReferenceLink` | the *role* a reference plays (e.g. `target`, `extends`, `concept`) | the **role** label on a reference edge |
| `SNodeReference` | an address (model + node id) that may or may not currently resolve to a live `SNode` | how the exporter builds a stable vertex id, even for a node it can't load |
| `SModelReference` | an address for a whole model | the `model` part of a vertex/edge id |
| `SProperty` | a leaf value on a node (e.g. a name, a literal) | with `--with-properties`-style output, extra vertex attributes; not an edge (properties don't point at other nodes) |

Two distinctions worth being precise about, because they map onto specific
method calls in `MpsGraphExporter`:

* **Containment vs. reference** is not a naming convention, it's structural:
  containment is "this node's `SModel` is reached by walking `getChildren()`
  from a root"; a reference is "this node points at another node's *address*,
  which may live in the same model, a different model, or may not resolve at
  all (a dangling reference)." The exporter mirrors this exactly:
  `node.getChildren()` for containment, `node.getReferences()` for
  references — two separate loops in `visit(...)`, producing two edge kinds.
* **Link vs. link declaration.** `SContainmentLink`/`SReferenceLink` are
  *runtime* handles — "the `items` child-role of concept `Root`, right now."
  MPS produces them from `ChildDeclaration` / `ReferenceLinkDeclaration`
  nodes that live in a language's `structure.mps` aspect model — itself just
  an ordinary MPS model, walkable by this same exporter like any other. The
  exporter only ever touches the runtime handles — it asks
  `node.getContainmentLink().getName()`, never the declaration nodes — which
  is what keeps it independent of any specific language.

## Reading `MpsGraphExporter` against this table

```java
void visit(SNode node, String parentGid, GraphSink sink) {
  String concept   = node.getConcept().getName();          // SConcept -> vertex "concept"
  String role      = node.getContainmentLink().getName();  // SContainmentLink -> containment edge role
  ...
  for (SReference ref : node.getReferences()) {             // SReference -> reference edge
    SReferenceLink link = ref.getLink();                    // SReferenceLink -> reference edge role
    SNodeReference target = ref.getTargetNodeReference();   // address, resolves or not
    ...
  }
  for (SNode child : node.getChildren()) {                  // containment
    visit(child, gid, sink);
  }
}
```

`ref.getTargetNodeReference()` (rather than `ref.getTargetNode()`) is the
important choice: it returns the *address* without forcing MPS to resolve and
load the target. That means the exporter still emits a reference edge — to an
`external` placeholder vertex — for references that cross into a module that
isn't part of the export, or that are currently unresolved. The offline
persistence-based tool gets this "for free" by construction (a `<ref
to="idx:id">` in the XML is already just an address); `getTargetNodeReference()`
is how the live-model exporter gets the same non-resolving behaviour.

## Further reading

* JetBrains MPS documentation — "Open API" section of the platform docs.
* `org.jetbrains.mps.openapi.model` — `SNode`, `SModel`, `SReference`,
  `SNodeReference`, `SModelReference`.
* `org.jetbrains.mps.openapi.language` — `SConcept`, `SAbstractConcept`,
  `SContainmentLink`, `SReferenceLink`, `SProperty`.
* `org.jetbrains.mps.openapi.module` — `SModule`, `SRepository`.
