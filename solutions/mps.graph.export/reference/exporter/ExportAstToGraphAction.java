package mps.graph.export;

import com.intellij.openapi.actionSystem.AnActionEvent;
import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.util.Arrays;
import java.util.List;
import jetbrains.mps.ide.actions.MPSCommonDataKeys;
import jetbrains.mps.workbench.action.BaseAction;
import org.jetbrains.mps.openapi.model.SModel;
import org.jetbrains.mps.openapi.model.SNode;

/**
 * "Export AST to Graph" - an MPS action that writes the selected model (or the
 * selected node's subtree) to graph files next to the project.
 *
 * <p>This is the thin IDE wrapper; all of the real work lives in
 * {@link MpsGraphExporter} and the {@link GraphSink} implementations, which is
 * why adding a format is a one-class change.
 *
 * <p>Reference implementation. In MPS this is normally expressed as a
 * {@code jetbrains.mps.lang.plugin} Action node; the body below is what that
 * action's {@code execute} block does. See README.md for wiring.
 */
public class ExportAstToGraphAction extends BaseAction {

  public ExportAstToGraphAction() {
    super("Export AST to Graph…");
  }

  @Override
  protected boolean isApplicable(AnActionEvent event, java.util.Map<String, Object> params) {
    return event.getData(MPSCommonDataKeys.CONTEXT_MODEL) != null
        || event.getData(MPSCommonDataKeys.NODE) != null;
  }

  @Override
  protected void doExecute(AnActionEvent event, java.util.Map<String, Object> params) {
    // One sink per requested format - the "generator per export language".
    List<GraphSink> sinks = Arrays.asList(
        (GraphSink) new GraphmlSink(false),
        (GraphSink) new DotSink());

    final SNode node = event.getData(MPSCommonDataKeys.NODE);
    final SModel model = event.getData(MPSCommonDataKeys.CONTEXT_MODEL);

    // Read access is required to traverse the model.
    event.getData(MPSCommonDataKeys.MPS_PROJECT).getRepository().getModelAccess()
        .runReadAction(new Runnable() {
          @Override
          public void run() {
            MpsGraphExporter exporter = new MpsGraphExporter();
            for (GraphSink sink : sinks) {
              if (node != null) {
                exporter.exportNode(node, sink);
              } else {
                exporter.export(model, sink);
              }
            }
          }
        });

    String base = model != null
        ? model.getReference().getModelName()
        : node.getName();
    for (GraphSink sink : sinks) {
      write(new File(base + "." + sink.extension()), sink.render());
    }
  }

  private static void write(File file, String text) {
    try {
      FileWriter w = new FileWriter(file);
      try {
        w.write(text);
      } finally {
        w.close();
      }
    } catch (IOException e) {
      throw new RuntimeException("Failed to write " + file, e);
    }
  }
}
