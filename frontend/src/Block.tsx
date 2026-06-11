import ReactMarkdown from "react-markdown";
import type { Block } from "./types";

/** Renders one Recorder block (the same block kinds the pipeline emits). */
export function BlockView({ block, runId }: { block: Block; runId: string | null }) {
  const p = block.payload || [];
  switch (block.kind) {
    case "markdown":
    case "write":
      return <div className="block"><ReactMarkdown>{String(p[0] ?? "")}</ReactMarkdown></div>;
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
