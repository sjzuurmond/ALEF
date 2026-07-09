package mps.graph.export;

import org.jetbrains.mps.openapi.language.SReferenceLink;
import org.jetbrains.mps.openapi.model.SModel;
import org.jetbrains.mps.openapi.model.SNode;
import org.jetbrains.mps.openapi.model.SNodeReference;
import org.jetbrains.mps.openapi.model.SReference;

/**
 * Walks an MPS AST through the Open API and pushes it into a {@link GraphSink}.
 *
 * <p>This is the in-IDE, MPS-native counterpart of the offline
 * {@code scripts/mps-graph-export} tool: it produces exactly the same graph
 * (vertices = SNodes; containment edges = parent/child; reference edges =
 * SReferences), but reads the live model rather than the {@code .mps} files.
 *
 * <p>It is deliberately language-agnostic: it only uses the reflective Open API
 * and knows nothing about any particular MPS language or about ALEF.
 *
 * <p>Reference implementation in plain Java; maps one-to-one onto MPS
 * BaseLanguage (see README.md).
 */
public class MpsGraphExporter {

  /** Which edges to emit. */
  public enum Edges { BOTH, CONTAINMENT, REFERENCES }

  private final boolean modelNodes;
  private final Edges edges;

  public MpsGraphExporter() {
    this(true, Edges.BOTH);
  }

  public MpsGraphExporter(boolean modelNodes, Edges edges) {
    this.modelNodes = modelNodes;
    this.edges = edges;
  }

  /** Export every root of {@code model} into {@code sink}. */
  public void export(SModel model, GraphSink sink) {
    sink.begin();
    addModel(model, sink);
    sink.end();
  }

  /** Export several models into one connected graph. */
  public void export(Iterable<SModel> models, GraphSink sink) {
    sink.begin();
    for (SModel model : models) {
      addModel(model, sink);
    }
    sink.end();
  }

  /** Export the subtree rooted at a single node. */
  public void exportNode(SNode root, GraphSink sink) {
    sink.begin();
    visit(root, null, sink);
    sink.end();
  }

  private void addModel(SModel model, GraphSink sink) {
    String modelName = model.getReference().getModelName();
    String modelGid = modelGid(model);
    if (modelNodes) {
      sink.vertex(modelGid, modelName, "<model>", "", modelName, "model", "");
    }
    for (SNode root : model.getRootNodes()) {
      visit(root, modelNodes ? modelGid : null, sink);
    }
  }

  private void visit(SNode node, String parentGid, GraphSink sink) {
    String gid = nodeGid(node);
    String concept = node.getConcept().getName();
    String conceptFqn = node.getConcept().getQualifiedName();
    String modelName = node.getModel() == null
        ? "" : node.getModel().getReference().getModelName();
    String role = node.getContainmentLink() == null
        ? "" : node.getContainmentLink().getName();
    String label = node.getName();
    if (label == null || label.isEmpty()) {
      label = concept;
    }
    sink.vertex(gid, label, concept, conceptFqn, modelName, "node", role);

    if (parentGid != null && edges != Edges.REFERENCES) {
      sink.edge(parentGid, gid, "containment", role.isEmpty() ? "root" : role);
    }

    if (edges != Edges.CONTAINMENT) {
      for (SReference ref : node.getReferences()) {
        addReference(node, gid, ref, sink);
      }
    }

    for (SNode child : node.getChildren()) {
      visit(child, gid, sink);
    }
  }

  private void addReference(SNode source, String sourceGid, SReference ref,
                            GraphSink sink) {
    SReferenceLink link = ref.getLink();
    String role = link == null ? "" : link.getName();

    // getTargetNodeReference() resolves the target address without forcing the
    // reference to resolve to a live node, so cross-model / unresolved targets
    // still produce an edge.
    SNodeReference target = ref.getTargetNodeReference();
    if (target == null) {
      return;
    }
    String targetModel = target.getModelReference() == null
        ? "" : target.getModelReference().getModelName();
    String targetGid = target.getModelReference() + "/" + target.getNodeId();

    // Make sure the target has at least a placeholder vertex.
    sink.vertex(targetGid, String.valueOf(target.getNodeId()), "<external>", "",
        targetModel, "external", "");
    sink.edge(sourceGid, targetGid, "reference", role);
  }

  private static String modelGid(SModel model) {
    return String.valueOf(model.getReference());
  }

  private static String nodeGid(SNode node) {
    return node.getModel().getReference() + "/" + node.getNodeId();
  }
}
