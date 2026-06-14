import ReactMarkdown from "react-markdown";
import type { Block } from "./types";

// The deep-agent sub-plan (write_todos) arrives as a markdown block like:
//   **📋 Plan:**
//   - ✅ done item
//   - 🔄 in-progress item
//   - ⬜ pending item
// Render it with the SAME styled checklist as the design "Plan" (green ✓ squares),
// instead of raw emoji markdown.
function parseTodos(text: string): { text: string; st: string }[] | null {
  if (!/📋\s*Plan/.test(text) && !/[⬜✅🔄]/.test(text)) return null;
  const items: { text: string; st: string }[] = [];
  for (const raw of text.split("\n")) {
    const m = raw.match(/^\s*[-*]?\s*([✅🔄⬜☑️])\s*(.+)$/u);
    if (!m) continue;
    const mark = m[1];
    const st = mark === "✅" || mark === "☑️" ? "done" : mark === "🔄" ? "active" : "pending";
    items.push({ text: m[2].trim(), st });
  }
  return items.length ? items : null;
}

function TodoList({ items }: { items: { text: string; st: string }[] }) {
  const done = items.filter((i) => i.st === "done").length;
  return (
    <div className="block planlist">
      <div className="planhead">
        📋 Plan <span className="plansub">— this step’s sub-tasks</span>
        <span className="plancount">{done}/{items.length}</span>
      </div>
      <ul>
        {items.map((it, i) => (
          <li key={i} className={"planitem " + it.st}>
            <span className="pmark">{it.st === "done" ? "✓" : it.st === "active" ? "▸" : ""}</span>
            <span className="ptext">{it.text}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Renders one Recorder block (the same block kinds the pipeline emits). */
export function BlockView({ block, runId }: { block: Block; runId: string | null }) {
  const p = block.payload || [];
  switch (block.kind) {
    case "markdown":
    case "write": {
      const text = String(p[0] ?? "");
      const todos = parseTodos(text);
      if (todos) return <TodoList items={todos} />;
      return <div className="block"><ReactMarkdown>{text}</ReactMarkdown></div>;
    }
    case "caption":
      return <div className="block caption">{String(p[0] ?? "")}</div>;
    case "success":
      return <div className="block success">✅ {String(p[0] ?? "")}</div>;
    case "error":
      return <div className="block error">❌ {String(p[0] ?? "")}</div>;
    case "warning":
      return <div className="block warning">⚠️ {String(p[0] ?? "")}</div>;
    case "info":
      return <div className="block info">ℹ️ {String(p[0] ?? "")}</div>;
    case "code":
      return <pre className="code">{String(p[0] ?? "")}</pre>;
    case "expander_code":
      return (
        <details className="exp block">
          <summary>{String(p[0] ?? "details")}</summary>
          <pre className="code">{String(p[1] ?? "")}</pre>
        </details>
      );
    case "image": {
      const path = String(p[0] ?? "");
      const src = runId ? `/api/runs/${runId}/file?path=${encodeURIComponent(path)}` : path;
      return (
        <div className="block">
          {p[1] ? <div className="caption">{String(p[1])}</div> : null}
          <img src={src} alt={String(p[1] ?? "image")} />
        </div>
      );
    }
    case "header":
      return null; // node header is rendered by the card itself
    default:
      return <div className="block caption">{String(p[0] ?? "")}</div>;
  }
}
