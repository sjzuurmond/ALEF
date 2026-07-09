package mps.graph.export;

/**
 * A "generator" for one concrete graph format.
 *
 * <p>{@link MpsGraphExporter} walks the MPS AST once and pushes vertices and
 * edges into a {@code GraphSink}; each output format (GraphML, DOT, GML, JSON,
 * ...) is a separate implementation. Adding a new format means adding a new
 * {@code GraphSink} - the traversal never changes.
 *
 * <p>This file is a reference implementation in plain Java. It is written to map
 * one-to-one onto MPS BaseLanguage so it can be brought into an MPS solution via
 * <i>Paste as BaseLanguage</i>. See README.md.
 */
public interface GraphSink {

  /** Called once before any vertex or edge. */
  void begin();

  /**
   * Emit a vertex. Implementations must be idempotent per {@code id}: the same
   * id may be offered more than once (e.g. a reference target seen before the
   * node itself). A later "real" vertex should win over an earlier
   * {@code external} placeholder.
   *
   * @param id         globally unique id ("&lt;model-ref&gt;/&lt;node-id&gt;")
   * @param label      human readable label (node name, else concept)
   * @param concept    short concept name
   * @param conceptFqn fully qualified concept name (may be empty)
   * @param model      owning model name
   * @param kind       "node" | "model" | "external"
   * @param role       containment role in the parent (may be empty)
   */
  void vertex(String id, String label, String concept, String conceptFqn,
              String model, String kind, String role);

  /**
   * Emit a directed edge.
   *
   * @param sourceId source vertex id
   * @param targetId target vertex id
   * @param type     "containment" | "reference"
   * @param role     link role name (may be empty)
   */
  void edge(String sourceId, String targetId, String type, String role);

  /** Called once after the last vertex/edge. */
  void end();

  /** File extension for this format, without the dot (e.g. "graphml"). */
  String extension();

  /** The rendered graph as text, valid only after {@link #end()}. */
  String render();
}
