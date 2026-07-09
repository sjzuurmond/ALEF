package mps.graph.export;

import java.util.LinkedHashMap;
import java.util.Map;

/** Writes <a href="https://graphviz.org/">Graphviz</a> DOT. */
public class DotSink implements GraphSink {

  private final StringBuilder body = new StringBuilder();
  private final Map<String, String> vertices = new LinkedHashMap<String, String>();

  @Override
  public void begin() {
    // header written in render()
  }

  @Override
  public void vertex(String id, String label, String concept, String conceptFqn,
                     String model, String kind, String role) {
    if (vertices.containsKey(id) && !"external".equals(kind)) {
      // overwrite placeholder with the real node
    } else if (vertices.containsKey(id)) {
      return;
    }
    String shown = esc(concept);
    if (label != null && !label.isEmpty() && !label.equals(concept)) {
      shown = shown + "\\n" + esc(label);
    }
    StringBuilder b = new StringBuilder();
    b.append("  \"").append(esc(id)).append("\" [label=\"").append(shown).append("\"");
    if ("model".equals(kind)) {
      b.append(", shape=folder, style=filled, fillcolor=\"#dddddd\"");
    } else if ("external".equals(kind)) {
      b.append(", style=dashed, color=\"#999999\"");
    }
    b.append("];\n");
    vertices.put(id, b.toString());
  }

  @Override
  public void edge(String sourceId, String targetId, String type, String role) {
    body.append("  \"").append(esc(sourceId)).append("\" -> \"")
        .append(esc(targetId)).append("\" [");
    if ("reference".equals(type)) {
      body.append("style=dashed, color=\"#3366cc\"");
    } else {
      body.append("color=\"#000000\"");
    }
    String shownRole = "root".equals(role) ? "" : role;
    if (shownRole != null && !shownRole.isEmpty()) {
      body.append(", label=\"").append(esc(shownRole)).append("\"");
    }
    body.append("];\n");
  }

  @Override
  public void end() {
    // nothing
  }

  @Override
  public String extension() {
    return "dot";
  }

  @Override
  public String render() {
    StringBuilder out = new StringBuilder();
    out.append("digraph MPS {\n");
    out.append("  rankdir=LR;\n");
    out.append("  node [shape=box, fontname=\"Helvetica\"];\n");
    for (String block : vertices.values()) {
      out.append(block);
    }
    out.append(body);
    out.append("}\n");
    return out.toString();
  }

  private static String esc(String s) {
    if (s == null) {
      return "";
    }
    return s.replace("\\", "\\\\").replace("\"", "\\\"");
  }
}
