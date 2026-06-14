import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";

interface Art { name: string; path: string; kind: string; size: number; }

const ICON: Record<string, string> = {
  code: "💻", pdf: "📄", image: "🖼️", gds: "🏭", waveform: "📈",
  doc: "📝", log: "📋", data: "🔧", file: "📎",
};
const TEXTY = ["code", "doc", "log", "data"];

/** A "shelf" of the design's artifacts (papers, code, GDS, waveforms, uploads). Click a
 *  tile to open its full content — transparent + understandable. */
export function Artifacts({ chatId, refreshKey }: { chatId: string | null; refreshKey: number }) {
  const [items, setItems] = useState<Art[]>([]);
  const [open, setOpen] = useState(false);
  const [view, setView] = useState<Art | null>(null);
  const [content, setContent] = useState("");
  const [exportState, setExportState] = useState<"idle" | "exporting" | "exported">("idle");
  const [exportCount, setExportCount] = useState(0);

  useEffect(() => {
    if (!chatId) { setItems([]); return; }
    fetch(`/api/chats/${chatId}/artifacts`).then((r) => r.json())
      .then((d) => setItems(d.artifacts || [])).catch(() => {});
  }, [chatId, refreshKey, open]);   // refetch when (re)opened too, so fresh RTL shows

  useEffect(() => {                 // already exported? reflect it on the button
    if (!chatId) { setExportState("idle"); return; }
    fetch(`/api/chats/${chatId}/export-knowledge`).then((r) => r.json())
      .then((d) => { if (d.exported) { setExportState("exported"); setExportCount(d.count || 0); } })
      .catch(() => {});
  }, [chatId, open]);

  async function exportKnowledge() {
    if (!chatId || exportState === "exporting") return;
    setExportState("exporting");
    try {
      const d = await (await fetch(`/api/chats/${chatId}/export-knowledge`, { method: "POST" })).json();
      setExportCount(d.count || 0);
      setExportState("exported");
    } catch { setExportState("idle"); }
  }

  if (!chatId) return null;
  const fileUrl = (p: string) => `/api/chats/${chatId}/file?path=${encodeURIComponent(p)}`;

  async function openItem(a: Art) {
    setView(a); setContent("");
    if (TEXTY.includes(a.kind)) {
      try { setContent(await (await fetch(fileUrl(a.path))).text()); }
      catch { setContent("(could not load)"); }
    }
  }

  const byKind = (k: string) => items.filter((a) => a.kind === k);
  const groups: [string, string][] = [
    ["code", "RTL / Code"], ["pdf", "Papers"], ["doc", "Notes"],
    ["image", "Images"], ["waveform", "Waveforms"], ["gds", "GDSII"],
    ["log", "Logs"], ["data", "Data"], ["file", "Files"],
  ];

  return (
    <>
      <button className="artbtn" onClick={() => setOpen((o) => !o)}
              title="Artifacts — papers, code, GDS, waveforms">
        📦 Artifacts <span className="cnt">{items.length}</span>
      </button>

      {open && (
        <div className="artpanel">
          <div className="arthead">
            <span>📦 Artifacts <small>{items.length} item(s)</small></span>
            <span className="x" onClick={() => setOpen(false)}>✕</span>
          </div>
          <div className="artscroll">
            {items.length === 0 && <div className="artempty">Nothing yet — artifacts appear as the run produces RTL, references and GDS.</div>}
            {groups.map(([k, label]) => {
              const list = byKind(k);
              if (!list.length) return null;
              return (
                <div key={k} className="artsec">
                  <div className="artsec-h">{ICON[k]} {label} <span>{list.length}</span></div>
                  <div className="artgrid">
                    {list.map((a) => (
                      <div key={a.path} className="arttile" onClick={() => openItem(a)} title={a.path}>
                        <div className="ico">{ICON[a.kind] || "📎"}</div>
                        <div className="nm">{a.name}</div>
                        <div className="kd">{(a.size / 1024).toFixed(1)} KB</div>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
          <div className="artfoot">
            <button className={"artexport " + exportState}
                    disabled={exportState !== "idle" || items.length === 0}
                    onClick={exportKnowledge}
                    title="Save this design (RTL/notes/refs/GDS) to the knowledge store (Postgres + MinIO). It survives deleting the chat.">
              {exportState === "exported"
                ? `✅ Exported to knowledge store${exportCount ? ` (${exportCount})` : ""}`
                : exportState === "exporting" ? "⏳ Exporting…"
                : "📤 Export to knowledge store"}
            </button>
            <div className="artfoot-note">
              Exported knowledge stays in db/pg/object storage even if you delete this chat.
            </div>
          </div>
        </div>
      )}

      {view && (
        <div className="artmodal" onClick={() => setView(null)}>
          <div className="artmodal-box" onClick={(e) => e.stopPropagation()}>
            <div className="arthead">
              <span>{ICON[view.kind] || "📎"} {view.name}</span>
              <span>
                <a className="dl" href={fileUrl(view.path)} target="_blank" rel="noreferrer">open ↗</a>
                <span className="x" onClick={() => setView(null)}>✕</span>
              </span>
            </div>
            <div className="artbody">
              {view.kind === "image" && <img src={fileUrl(view.path)} alt={view.name} />}
              {view.kind === "pdf" && <iframe src={fileUrl(view.path)} title={view.name} />}
              {view.kind === "gds" && <div className="artnote">GDSII layout — <a href={fileUrl(view.path)} target="_blank" rel="noreferrer">download</a> and open in KLayout.</div>}
              {view.kind === "waveform" && <div className="artnote">VCD waveform — <a href={fileUrl(view.path)} target="_blank" rel="noreferrer">download</a> to view, or ask the agent to render it.</div>}
              {view.kind === "doc" && <ReactMarkdown>{content || "loading…"}</ReactMarkdown>}
              {TEXTY.includes(view.kind) && view.kind !== "doc" && <pre className="code">{content || "loading…"}</pre>}
              {view.kind === "file" && <div className="artnote"><a href={fileUrl(view.path)} target="_blank" rel="noreferrer">download {view.name}</a></div>}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
