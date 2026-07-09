package mps.graph.export;

import java.util.LinkedHashMap;
import java.util.Map;

/** Writes <a href="http://graphml.graphdrawing.org/">GraphML</a>. */
public class GraphmlSink implements GraphSink {

  private final boolean withProperties;
  private final StringBuilder nodes = new StringBuilder();
  private final StringBuilder edges = new StringBuilder();
  // id -> rendered <node> block; lets a real vertex replace an "external" one.
  private final Map<String, String> vertices = new LinkedHashMap<String, String>();
  private int edgeSeq = 0;

  public GraphmlSink(boolean withProperties) {
    this.withProperties = withProperties;
  }

  @Override
  public void begin() {
    // nothing; header is written in render()
  }

  @Override
  public void vertex(String id, String label, String concept, String conceptFqn,
                     String model, String kind, String role) {
    // A real node must win over a previously created external placeholder.
    if (vertices.containsKey(id) && !"external".equals(kind)) {
      // fall through and overwrite
    } else if (vertices.containsKey(id)) {
      return;
    }
    StringBuilder b = new StringBuilder();
    b.append("    <node id=\"").append(esc(id)).append("\">\n");
    data(b, "label", label);
    data(b, "concept", concept);
    data(b, "conceptFqn", conceptFqn);
    data(b, "model", model);
    data(b, "kind", kind);
    if (role != null && !role.isEmpty()) {
      data(b, "role", role);
    }
    b.append("    </node>\n");
    vertices.put(id, b.toString());
  }

  @Override
  public void edge(String sourceId, String targetId, String type, String role) {
    edges.append("    <edge id=\"e").append(edgeSeq++).append("\" source=\"")
        .append(esc(sourceId)).append("\" target=\"").append(esc(targetId))
        .append("\">\n");
    data(edges, "type", type);
    if (role != null && !role.isEmpty()) {
      data(edges, "edgeRole", role);
    }
    edges.append("    </edge>\n");
  }

  @Override
  public void end() {
    for (String block : vertices.values()) {
      nodes.append(block);
    }
  }

  @Override
  public String extension() {
    return "graphml";
  }

  @Override
  public String render() {
    StringBuilder out = new StringBuilder();
    out.append("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n");
    out.append("<graphml xmlns=\"http://graphml.graphdrawing.org/xmlns\">\n");
    key(out, "label", "node");
    key(out, "concept", "node");
    key(out, "conceptFqn", "node");
    key(out, "model", "node");
    key(out, "kind", "node");
    key(out, "role", "node");
    key(out, "type", "edge");
    key(out, "edgeRole", "edge");
    out.append("  <graph edgedefault=\"directed\">\n");
    out.append(nodes);
    out.append(edges);
    out.append("  </graph>\n");
    out.append("</graphml>\n");
    return out.toString();
  }

  private static void key(StringBuilder out, String id, String domain) {
    out.append("  <key id=\"").append(id).append("\" for=\"").append(domain)
        .append("\" attr.name=\"").append(id).append("\" attr.type=\"string\"/>\n");
  }

  private static void data(StringBuilder out, String key, String value) {
    out.append("      <data key=\"").append(key).append("\">")
        .append(esc(value)).append("</data>\n");
  }

  private static String esc(String s) {
    if (s == null) {
      return "";
    }
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace("\"", "&quot;");
  }
}
