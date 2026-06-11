import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import { BlockView } from "./Block";
import { DEFAULT_CONSTRAINTS } from "./types";
import type { Block, Chat, KnowledgeStats, Message, RunConstraints, RunEvent, TranscriptRecord } from "./types";

const STEP_EMOJI: Record<string, string> = {
  plan: "🧭", retrieve: "📚", web: "🌐", generate: "✍️", decompose: "🧩",
  testbench: "🧪", write: "💾", simulate: "⏱️", lint: "🔍",
  fix_design: "🔧", fix_testbench: "🔧", harden: "🏭", error: "❗",
};

export default function App() {
  const [chats, setChats] = useState<Chat[]>([]);
  const [chatId, setChatId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [transcript, setTranscript] = useState<TranscriptRecord[]>([]);
  const [running, setRunning] = useState(false);
  const [pausing, setPausing] = useState(false);
  const [runId, setRunId] = useState<string | null>(null);
  const [knowledge, setKnowledge] = useState<KnowledgeStats | null>(null);

  const [prompt, setPrompt] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [opts, setOpts] = useState<RunConstraints>({ ...DEFAULT_CONSTRAINTS });
  const [showConstraints, setShowConstraints] = useState(true);
  const streamRef = useRef<HTMLDivElement>(null);
  const unsubRef = useRef<() => void>();
  const newRunRef = useRef(false);   // force the next step into a FRESH card (continue → new blocks below)
  const setOpt = <K extends keyof RunConstraints>(k: K, v: RunConstraints[K]) =>
    setOpts((o) => ({ ...o, [k]: v }));

  useEffect(() => { refreshChats(); refreshKnowledge(); }, []);
  useEffect(() => { streamRef.current?.scrollTo(0, streamRef.current.scrollHeight); }, [transcript, messages]);

  async function refreshChats() { setChats(await api.listChats()); }
  async function refreshKnowledge() { try { setKnowledge(await api.knowledge()); } catch { /* */ } }

  async function openChat(id: string) {
    if (running && runId) api.pauseRun(runId);   // leaving a chat stops its run (state saved)
    unsubRef.current?.();
    setChatId(id);
    const data = await api.getChat(id);
    setMessages(data.messages || []);
    setTranscript(data.transcript || []);
    setRunId(data.run?.id ?? null);
    setRunning((data.run?.status || "done") === "running");
    setPausing(false);
  }

  async function newChat() {
    if (running && runId) api.pauseRun(runId);   // starting a new chat stops the current run
    unsubRef.current?.();
    setChatId(null); setMessages([]); setTranscript([]); setRunId(null); setRunning(false);
    setOpts({ ...DEFAULT_CONSTRAINTS });
    setShowConstraints(true);   // pop the constraints picker out on every new chat
  }

  async function removeChat(id: string, ev?: React.MouseEvent) {
    ev?.stopPropagation();
    if (!confirm("Delete this chat and its design from the database + object storage?")) return;
    await api.deleteChat(id);          // cascades: chat/messages/run + knowledge rows + MinIO blobs
    if (id === chatId) newChat();
    refreshChats(); refreshKnowledge();
  }

  function applyEvent(e: RunEvent) {
    // The first event of a (new or resumed) run starts a FRESH card, so a continuation
    // appends BELOW the retained previous transcript instead of merging into it.
    const forceNew = (e.type === "step" || e.type === "block") && newRunRef.current;
    if (forceNew) newRunRef.current = false;

    if (e.type === "step") {
      setTranscript((t) =>
        !forceNew && t.length && t[t.length - 1].node === e.node
          ? t : [...t, { node: e.node, blocks: [] }]);
    } else if (e.type === "block") {
      // IMMUTABLE update — never mutate the previous state.
      setTranscript((t) => {
        const block = { kind: e.kind, payload: e.payload } as Block;
        const last = t[t.length - 1];
        if (forceNew || !last || last.node !== e.node) {
          return [...t, { node: e.node, blocks: [block] }];
        }
        const updated = { ...last, blocks: [...last.blocks, block] };
        return [...t.slice(0, -1), updated];
      });
    } else if (e.type === "knowledge") {
      // store changed at a meaningful event (research / fix / verified design)
      setKnowledge((k) => ({ total: e.total, by_kind: k?.by_kind || {} }));
    } else if (e.type === "end") {
      setRunning(false);
      setPausing(false);
      refreshKnowledge();
      if (chatId) api.getChat(chatId).then((d) => setMessages(d.messages || []));
    }
  }

  async function send() {
    if (!prompt.trim() || running) return;
    let cid = chatId;
    if (!cid) { const c = await api.createChat(); cid = c.id; setChatId(c.id); await refreshChats(); }

    const userMsg: Message = {
      id: "tmp", chat_id: cid!, role: "user", content: prompt,
      files: files.map((f) => ({ name: f.name, kind: f.type.includes("pdf") ? "pdf" : f.type.startsWith("image") ? "image" : "file" })),
      created_at: new Date().toISOString(),
    };
    const isContinue = /^(continue|please continue|keep going|resume|carry on|lanjut)/i.test(prompt.trim());
    setMessages((m) => [...m, userMsg]);
    if (!isContinue) setTranscript([]);   // continue → keep the existing transcript, append to it
    setRunning(true);
    setPausing(false);

    const sentPrompt = prompt, sentFiles = files;
    setPrompt(""); setFiles([]); setShowConstraints(false);

    const { run } = await api.sendMessage(cid!, sentPrompt, sentFiles, opts);
    setRunId(run.id);
    refreshChats();
    newRunRef.current = true;     // this run's first step starts a fresh card below
    unsubRef.current = api.streamRun(run.id, applyEvent);
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <span className="logo">🦅</span>
          <h1>GarudaChip<br /><small>prompt → RTL → GDSII</small></h1>
        </div>
        <button className="newchat" onClick={newChat}>＋ New chat</button>
        <div className="chatlist">
          {chats.map((c) => (
            <div key={c.id} className={"chatitem" + (c.id === chatId ? " active" : "")}
                 onClick={() => openChat(c.id)}>
              <span className="ctitle">{c.title}</span>
              <span className="del" title="Delete chat + its design from DB & object storage"
                    onClick={(ev) => removeChat(c.id, ev)}>🗑</span>
            </div>
          ))}
        </div>
        <div className="kbadge">
          🗄️ Knowledge store: <b>{knowledge?.total ?? "…"}</b> items
        </div>
      </aside>

      <main className="main">
        <div className="topbar">
          <span className="title">{chats.find((c) => c.id === chatId)?.title || "New chat"}</span>
          <span className="pill">Ollama · qwen3.5:9b</span>
          {running && <span className="running"><span className="dot" /> running…</span>}
        </div>

        <div className="stream" ref={streamRef}>
          {messages.length === 0 && transcript.length === 0 ? (
            <div className="empty">
              <h2>Describe the hardware to build</h2>
              <p>e.g. “an 8-bit PWM generator with configurable period and duty cycle”.<br />
                 Attach a spec PDF or a diagram, and watch it go from prompt → RTL → GDSII.</p>
            </div>
          ) : null}

          {messages.map((m) => (
            <div key={m.id} className={"msg " + m.role}>
              <div className="avatar">{m.role === "user" ? "🧑" : "🦅"}</div>
              <div className="body">
                <div className="who">{m.role === "user" ? "You" : "GarudaChip"}</div>
                <div>{m.content}</div>
                {m.files?.length ? (
                  <div className="files">
                    {m.files.map((f, i) => (
                      <span key={i} className="chip">{f.kind === "image" ? "🖼️" : f.kind === "pdf" ? "📄" : "📎"} {f.name}</span>
                    ))}
                  </div>
                ) : null}
              </div>
            </div>
          ))}

          {transcript.map((node, i) => (
            <div key={i} className="node">
              <div className="head">
                <span>{STEP_EMOJI[node.node] || "•"}</span>
                <span>{titleFor(node)}</span>
              </div>
              <div className="blocks">
                {node.blocks.map((b, j) => <BlockView key={j} block={b} runId={runId} />)}
              </div>
            </div>
          ))}
        </div>

        <div className="composer">
          {showConstraints && (
            <ConstraintsPanel opts={opts} setOpt={setOpt} onClose={() => setShowConstraints(false)} />
          )}
          <div className="box">
            {files.length > 0 && (
              <div className="attachments">
                {files.map((f, i) => (
                  <span key={i} className="chip">
                    {f.type.startsWith("image") ? "🖼️" : f.type.includes("pdf") ? "📄" : "📎"} {f.name}
                    <span style={{ cursor: "pointer", marginLeft: 6 }}
                          onClick={() => setFiles(files.filter((_, k) => k !== i))}>✕</span>
                  </span>
                ))}
              </div>
            )}
            <textarea
              value={prompt} placeholder="Describe the hardware, or steer the run…"
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
            />
            <div className="row">
              <label className="iconbtn" title="Attach image / PDF / spec">
                📎 Attach
                <input type="file" multiple accept="image/*,.pdf,.txt,.md,.v,.vh,.csv,.json"
                       style={{ display: "none" }}
                       onChange={(e) => setFiles([...files, ...Array.from(e.target.files || [])])} />
              </label>
              <button className={"iconbtn" + (showConstraints ? " active" : "")}
                      onClick={() => setShowConstraints((s) => !s)} title="Build constraints">
                ⚙️ Constraints
              </button>
              <span className="constsum">
                {opts.clock_period}ns · {opts.die_um}µm · {opts.core_util}% · {opts.run_harden ? "GDSII" : "RTL"}
              </span>
              <span className="spacer" />
              {running ? (
                <button className="iconbtn-round stop"
                        onClick={() => {
                          if (runId) api.pauseRun(runId);  // tell backend to stop (kills subprocess)
                          unsubRef.current?.();             // detach the stream now
                          setRunning(false);                // UI is free immediately
                        }}
                        title="Stop (state saved — say 'continue' to resume)">
                  <span className="sq" />
                </button>
              ) : (
                <button className="iconbtn-round" disabled={!prompt.trim()} onClick={send}
                        title="Send">↑</button>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

function titleFor(node: TranscriptRecord): string {
  const header = node.blocks.find((b) => b.kind === "header");
  if (header) return String(header.payload[1] ?? node.node);
  return node.node;
}

function ConstraintsPanel({ opts, setOpt, onClose }: {
  opts: RunConstraints;
  setOpt: <K extends keyof RunConstraints>(k: K, v: RunConstraints[K]) => void;
  onClose: () => void;
}) {
  return (
    <div className="constraints">
      <div className="chead">
        <span>⚙️ Build constraints</span>
        <span className="x" onClick={onClose}>✕</span>
      </div>
      <div className="cgrid">
        <label>Clock port
          <input value={opts.clock_port} onChange={(e) => setOpt("clock_port", e.target.value)} />
        </label>
        <label>Clock period (ns)
          <input type="number" min={1} step={1} value={opts.clock_period}
                 onChange={(e) => setOpt("clock_period", Number(e.target.value))} />
        </label>
        <label>Die size (µm, square)
          <input type="number" min={50} step={50} value={opts.die_um}
                 onChange={(e) => setOpt("die_um", Number(e.target.value))} />
        </label>
        <label>Core utilization (%)
          <input type="range" min={10} max={80} value={opts.core_util}
                 onChange={(e) => setOpt("core_util", Number(e.target.value))} />
          <span className="val">{opts.core_util}%</span>
        </label>
      </div>
      <div className="ctoggles">
        <label><input type="checkbox" checked={opts.use_web}
                      onChange={(e) => setOpt("use_web", e.target.checked)} /> Web research</label>
        <label><input type="checkbox" checked={opts.deep_steps}
                      onChange={(e) => setOpt("deep_steps", e.target.checked)} /> RLM deep agents</label>
        <label><input type="checkbox" checked={opts.run_harden}
                      onChange={(e) => setOpt("run_harden", e.target.checked)} /> Harden to GDSII</label>
      </div>
    </div>
  );
}
