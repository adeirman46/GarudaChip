import { Fragment, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { api } from "./api";
import { Artifacts } from "./Artifacts";
import { BlockView } from "./Block";
import { KnowledgePanel } from "./Knowledge";
import { DEFAULT_CONSTRAINTS } from "./types";
import type { Block, Chat, KnowledgeStats, Message, RunConstraints, RunEvent, TranscriptRecord } from "./types";

const STEP_EMOJI: Record<string, string> = {
  plan: "🧭", retrieve: "📚", web: "🌐", generate: "✍️", decompose: "🧩",
  testbench: "🧪", write: "💾", simulate: "⏱️", lint: "🔍",
  fix_design: "🔧", fix_testbench: "🔧", harden: "🏭", error: "❗",
};

// whimsical busy words (à la Claude's "Cogitating…") — Garuda + chip-design flavoured,
// rotated every couple of seconds so the wait never feels stale. 100 of them.
const BUSY_WORDS = [
  "Garudaing", "Soaring", "Winging", "Feathering", "Talon-ing", "Eagle-eyeing", "Gliding",
  "Hovering", "Circling", "Diving", "Perching", "Nesting", "Screeching", "Hunting", "Flapping",
  "Synthesizing", "Routing", "Floorplanning", "Placing", "Pipelining", "Clocking", "Latching",
  "Registering", "Buffering", "Inverting", "Muxing", "Flip-flopping", "Gatekeeping", "Fanning-out",
  "Cascading", "Carrying", "Adding", "Multiplying", "Accumulating", "Convolving", "Quantizing",
  "LUT-baking", "Tensoring", "Vectorizing", "Embedding", "Inferencing", "Verilogging", "Netlisting",
  "Decomposing", "Composing", "Assembling", "Hardening", "Tapeout-ing", "Wafering", "Etching",
  "Doping", "Siliconizing", "Transistoring", "Latticing", "Annealing", "Biasing", "Tuning",
  "Trimming", "Decoupling", "Shielding", "Grounding", "Powering", "Padringing", "Bonding",
  "Soldering", "Wiring", "Meshing", "Timing-closing", "Overclocking", "Probing", "Waveforming",
  "Sampling", "Linting", "Debugging", "Resetting", "Booting", "Architecting", "Drafting",
  "Schematicking", "Sketching", "Forging", "Smithing", "Crafting", "Conjuring", "Brewing",
  "Simmering", "Percolating", "Baking", "Curing", "Crunching", "Calculating", "Reasoning",
  "Pondering", "Cogitating", "Plotting", "Scheming", "Recalling", "Manifesting", "Solving",
];

function useBusyWord(active: boolean) {
  const [word, setWord] = useState(() => BUSY_WORDS[Math.floor(Math.random() * BUSY_WORDS.length)]);
  useEffect(() => {
    if (!active) return;
    const tick = () => setWord(BUSY_WORDS[Math.floor(Math.random() * BUSY_WORDS.length)]);
    tick();
    const id = setInterval(tick, 3500);
    return () => clearInterval(id);
  }, [active]);
  return word;
}

function BusyTag() {
  const word = useBusyWord(true);
  return (
    <span className="working">
      <span className="streamdots"><i /><i /><i /></span> {word}…
    </span>
  );
}

// --- grand-plan checklist: each item greens as the DOWNSTREAM agent reaches its phase ---
// (the planner ticks nothing itself). Phases are the pipeline steps after "plan".
const PHASE_ORDER = ["generate", "decompose", "testbench", "write", "simulate", "lint", "harden"];

function itemPhase(text: string): number {
  const t = text.toLowerCase();
  const has = (...ks: string[]) => ks.some((k) => t.includes(k));
  if (has("drc", "lvs", "antenna", "gdsii", "gds", "stream out", "streamout", "sign-off", "signoff", "tape-out", "tapeout")) return 6; // harden
  if (has("floorplan", "placement", "place-and-route", "place and route", "clock tree", " cts", "routing", "physical")) return 6;
  if (has("synthesis", "synthesize", "yosys", "netlist", "gate-level", "timing constraint", "logic synth")) return 6;
  if (has("verify", "corner case", "hazard", "reset behav", "simulat", "regression", "waveform")) return 4; // simulate
  if (has("testbench", "self-checking", "stimulus", "test case", "test bench")) return 2; // testbench
  if (has("integrate", "connect the", "wire up", "assemble", "top-level connect", "hook up")) return 3; // write/integrate
  return 0; // spec, research, design top/sub-modules, LUT/weights → generate phase
}

function planProgress(turn: TranscriptRecord[], live: boolean) {
  const nodes = turn.map((n) => n.node);
  const active = live ? nodes[nodes.length - 1] : null;
  let maxDone = -1;
  for (const n of nodes) {
    if (n === active) continue;
    const idx = PHASE_ORDER.indexOf(n);
    if (idx > maxDone) maxDone = idx;
  }
  return { maxDone, activeIdx: active ? PHASE_ORDER.indexOf(active) : -1 };
}

// the files the agent has actually written this turn — scanned from the streamed
// `write_file_disk · path=rtl/alu.v` tool-call blocks. Used to green a checklist item the
// MOMENT its file lands on disk (not just when the whole phase finishes).
function writtenFiles(turn: TranscriptRecord[]): Set<string> {
  const out = new Set<string>();
  for (const n of turn) {
    for (const b of n.blocks) {
      if (b.kind !== "markdown") continue;
      const s = String(b.payload?.[0] ?? "");
      if (!s.includes("write_file_disk")) continue;
      const m = s.match(/path=([^\s·`]+)/);
      if (m) out.add(m[1].split("/").pop()!.toLowerCase());
    }
  }
  return out;
}

function itemFile(it: string): string | null {
  const m = it.match(/([a-z0-9_]+\.(?:svh|vh|sv|v|py|mem))\b/i);
  return m ? m[1].toLowerCase() : null;
}

// stem of a filename ("alu_8bit_fp.v" → "alu_8bit_fp")
const stem = (f: string) => f.replace(/\.[^.]+$/, "");

// does any written file correspond to this plan filename? The generator often renames
// (plan "alu.v" → written "alu_8bit_fp.v"), so match on equality or a token-prefix.
function fileWritten(itemFn: string, written: Set<string>): boolean {
  const a = stem(itemFn);
  for (const w of written) {
    const b = stem(w);
    // exact, or the written file SPECIALIZES the planned name (plan "alu" → written "alu_8bit").
    // NOT the reverse — a written "fazyrv_rf" must not green the plan item "fazyrv_rf_lut".
    if (a === b || b.startsWith(a + "_")) return true;
  }
  return false;
}

function PlanChecklist({ items, turn, live }: { items: string[]; turn: TranscriptRecord[]; live: boolean }) {
  const { maxDone, activeIdx } = planProgress(turn, live);
  const written = writtenFiles(turn);
  const stateOf = (it: string): "done" | "active" | "pending" => {
    const f = itemFile(it);
    if (f)                                      // an item that names a file → green when written
      return fileWritten(f, written) ? "done" : "pending";
    const p = itemPhase(it);                    // prose item → green when its phase completes
    return p <= maxDone ? "done" : p === activeIdx ? "active" : "pending";
  };
  const states = items.map(stateOf);
  const done = states.filter((s) => s === "done").length;
  return (
    <div className="block planlist">
      <div className="planhead">
        📋 Plan <span className="plansub">— greens as each item is built</span>
        <span className="plancount">{done}/{items.length}</span>
      </div>
      <ul>
        {items.map((it, i) => {
          const st = states[i];
          return (
            <li key={i} className={"planitem " + st}>
              <span className="pmark">{st === "done" ? "✓" : st === "active" ? "▸" : ""}</span>
              <span className="ptext">{it}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

// canonical pipeline for the progress stepper (gives the user an at-a-glance map)
// One "Planning" step — recall + web/github/paper research are folded INTO it.
const PIPELINE: [string, string][] = [
  ["plan", "Planning"], ["generate", "Generate"],
  ["decompose", "Split"], ["testbench", "Testbench"], ["write", "Write"],
  ["simulate", "Simulate"], ["lint", "Lint"], ["harden", "Harden"],
];

function Stepper({ transcript, live }: { transcript: TranscriptRecord[]; live: boolean }) {
  const seen = new Set(transcript.map((n) => n.node));
  const last = transcript[transcript.length - 1]?.node;
  return (
    <div className="stepper">
      {PIPELINE.map(([key, label]) => {
        const active = live && key === last;
        const state = active ? "active" : seen.has(key) ? "done" : "pending";
        return (
          <span key={key} className={"stepchip " + state} title={label}>
            <span className="dotmark">{state === "done" ? "✓" : state === "active" ? "●" : "○"}</span>
            {label}
          </span>
        );
      })}
    </div>
  );
}

export default function App() {
  const [chats, setChats] = useState<Chat[]>([]);
  const [chatId, setChatId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [transcript, setTranscript] = useState<TranscriptRecord[]>([]);
  const [running, setRunning] = useState(false);
  const [pausing, setPausing] = useState(false);
  const [runId, setRunId] = useState<string | null>(null);
  const [knowledge, setKnowledge] = useState<KnowledgeStats | null>(null);
  const [view, setView] = useState<"chat" | "knowledge">("chat");
  // each finished run's transcript, keyed by the user message that triggered it (so the
  // chat alternates User → Assistant → User → Assistant). The LIVE run uses `transcript`,
  // anchored to `runMsgId`.
  const [pastRuns, setPastRuns] = useState<Record<string, TranscriptRecord[]>>({});
  const [runMsgId, setRunMsgId] = useState<string | null>(null);
  const [artRefresh, setArtRefresh] = useState(0);   // bump to re-list artifacts
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [confirmMsg, setConfirmMsg] = useState<string | null>(null);
  const [editTarget, setEditTarget] = useState<{ id: string; content: string } | null>(null);
  const [editText, setEditText] = useState("");
  const [theme, setTheme] = useState<"dark" | "light">(
    () => (localStorage.getItem("garuda-theme") as "dark" | "light") || "dark");

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("garuda-theme", theme);
  }, [theme]);

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
  // on reload, reopen the chat the user was in (reconnects to a live run via SSE replay)
  useEffect(() => {
    const last = localStorage.getItem("garuda-chat");
    if (last) openChat(last).catch(() => localStorage.removeItem("garuda-chat"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => { streamRef.current?.scrollTo(0, streamRef.current.scrollHeight); }, [transcript, messages]);

  async function refreshChats() { setChats(await api.listChats()); }
  async function refreshKnowledge() { try { setKnowledge(await api.knowledge()); } catch { /* */ } }

  async function openChat(id: string) {
    setView("chat");                             // selecting a chat always returns to the chat view
    // NOTE: do NOT pause the run when switching chats — a build must keep running
    // server-side while you look at another chat (like CI). Only the Stop button pauses.
    unsubRef.current?.();
    setChatId(id);
    localStorage.setItem("garuda-chat", id);     // remember it so a reload reopens this chat
    const data = await api.getChat(id);
    setMessages(data.messages || []);
    const byMsg: Record<string, TranscriptRecord[]> = {};
    (data.runs || []).forEach((r: any) => { if (r.message_id) byMsg[r.message_id] = r.transcript || []; });
    setPastRuns(byMsg);
    setRunMsgId(data.run?.message_id ?? null);
    setRunId(data.run?.id ?? null);
    setPausing(false);
    const live = (data.run?.status || "done") === "running";
    setRunning(live);
    if (live && data.run?.id) {
      // RECONNECT to the live run — SSE replays the full backlog (incl. the in-progress
      // step that isn't persisted yet), so the transcript is restored, not lost.
      setTranscript([]);
      newRunRef.current = false;
      unsubRef.current = api.streamRun(data.run.id, applyEvent);
    } else {
      setTranscript(data.run?.transcript || []);
    }
  }

  async function newChat() {
    setView("chat");                             // new chat always returns to the chat view
    // don't pause the running build — it keeps going server-side in its own chat
    unsubRef.current?.();
    localStorage.removeItem("garuda-chat");
    setChatId(null); setMessages([]); setTranscript([]); setRunId(null); setRunning(false);
    setPastRuns({}); setRunMsgId(null);
    setOpts({ ...DEFAULT_CONSTRAINTS });
    setShowConstraints(true);   // pop the constraints picker out on every new chat
  }

  function askDelete(id: string, ev?: React.MouseEvent) {
    ev?.stopPropagation();
    setConfirmDelete(id);              // open the styled confirm modal (no ugly native dialog)
  }

  async function doDelete() {
    const id = confirmDelete;
    setConfirmDelete(null);
    if (!id) return;
    await api.deleteChat(id);          // cascades: chat/messages/run + knowledge rows + MinIO blobs
    if (id === chatId) newChat();
    refreshChats(); refreshKnowledge();
  }

  // delete / edit ONE message (and its run) — open STYLED modals (no native browser dialogs).
  function deleteMessage(id: string, ev?: React.MouseEvent) {
    ev?.stopPropagation();
    if (!chatId || running) return;
    setConfirmMsg(id);
  }
  async function doDeleteMessage() {
    const id = confirmMsg; setConfirmMsg(null);
    if (!id || !chatId) return;
    await api.deleteMessage(chatId, id);
    await openChat(chatId);
    setArtRefresh((k) => k + 1); refreshKnowledge();
  }
  function editMessage(id: string, cur: string, ev?: React.MouseEvent) {
    ev?.stopPropagation();
    if (!chatId || running) return;
    setEditTarget({ id, content: cur }); setEditText(cur);
  }
  async function saveEdit() {
    if (!editTarget || !chatId) return;
    const { id, content } = editTarget;
    const next = editText.trim();
    setEditTarget(null);
    if (!next) return;
    if (next === content.trim()) return;               // no change → nothing to do
    if (running && runId) api.pauseRun(runId);          // never run two at once
    // edit AND auto re-RUN this message (the new run replaces the old) — like ChatGPT.
    setPastRuns((p) => { const c = { ...p }; delete c[id]; return c; });
    setMessages((m) => m.map((x) => (x.id === id ? { ...x, content: next } : x)));
    setTranscript([]); setRunMsgId(id); setRunning(true); setPausing(false);
    const { run } = await api.rerunMessage(chatId, id, next, opts);
    setRunId(run.id);
    newRunRef.current = true;
    unsubRef.current = api.streamRun(run.id, applyEvent);
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
      setArtRefresh((n) => n + 1);   // each step likely wrote files → refresh the shelf
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
    } else if (e.type === "trim") {
      // continue is re-running the interrupted step → remove its partial card
      setTranscript((t) => t.slice(0, -1));
    } else if (e.type === "knowledge") {
      // store changed at a meaningful event (research / fix / verified design)
      setKnowledge((k) => ({ total: e.total, by_kind: k?.by_kind || {} }));
      setArtRefresh((n) => n + 1);   // new artifacts likely landed too
    } else if (e.type === "end") {
      setRunning(false);
      setPausing(false);
      setArtRefresh((n) => n + 1);
      refreshKnowledge();
      if (chatId) api.getChat(chatId).then((d) => setMessages(d.messages || []));
    }
  }

  async function send() {
    if (!prompt.trim() || running) return;
    if (running && runId) api.pauseRun(runId);   // never run two at once in a chat
    let cid = chatId;
    if (!cid) { const c = await api.createChat(); cid = c.id; setChatId(c.id); await refreshChats(); }

    const tmpId = "tmp-" + Date.now();
    const userMsg: Message = {
      id: tmpId, chat_id: cid!, role: "user", content: prompt,
      files: files.map((f) => ({ name: f.name, kind: f.type.includes("pdf") ? "pdf" : f.type.startsWith("image") ? "image" : "file" })),
      created_at: new Date().toISOString(),
    };
    // archive the previous turn's transcript under its message, then start a FRESH turn
    setPastRuns((p) => (runMsgId ? { ...p, [runMsgId]: transcript } : p));
    setMessages((m) => [...m, userMsg]);
    setTranscript([]);
    setRunMsgId(tmpId);
    setRunning(true);
    setPausing(false);

    const sentPrompt = prompt, sentFiles = files;
    setPrompt(""); setFiles([]); setShowConstraints(false);

    const { message, run } = await api.sendMessage(cid!, sentPrompt, sentFiles, opts);
    setMessages((m) => m.map((x) => (x.id === tmpId ? { ...x, id: message.id } : x)));
    setRunMsgId(message.id);     // anchor this turn's live transcript to the real message
    setRunId(run.id);
    refreshChats();
    newRunRef.current = true;
    unsubRef.current = api.streamRun(run.id, applyEvent);
  }

  function steer() {
    if (!prompt.trim() || !runId || !running) return;
    api.steerRun(runId, prompt.trim());   // applied as feedback to the next step
    setPrompt("");
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <span className="logomark">🦅</span>
          <div className="brandtext">
            <h1>GarudaChip</h1>
            <small>prompt → RTL → GDSII</small>
          </div>
          <button className="themebtn" title="Toggle light / dark"
                  onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}>
            {theme === "dark" ? "☀️" : "🌙"}
          </button>
        </div>
        <button className="newchat" onClick={newChat}>＋ New chat</button>
        <div className="chatlist">
          {chats.map((c) => (
            <div key={c.id} className={"chatitem" + (c.id === chatId ? " active" : "")}
                 onClick={() => openChat(c.id)}>
              <span className="ctitle">{c.title}</span>
              <span className="del" title="Delete chat + its design from DB & object storage"
                    onClick={(ev) => askDelete(c.id, ev)}>🗑</span>
            </div>
          ))}
        </div>
        <div className={"kbadge clickable" + (view === "knowledge" ? " active" : "")}
             title="Browse / search / edit the knowledge store (Postgres + MinIO)"
             onClick={() => setView((v) => (v === "knowledge" ? "chat" : "knowledge"))}>
          🗄️ Knowledge store: <b>{knowledge?.total ?? "…"}</b> items
          <span className="kbadge-cta">{view === "knowledge" ? "← back to chat" : "manage →"}</span>
        </div>
      </aside>

      <main className="main">
        {view === "knowledge" ? <KnowledgePanel /> : <>
        <div className="topbar">
          <span className="title">{chats.find((c) => c.id === chatId)?.title || "New chat"}</span>
          <span className="pill">Ollama · qwen3.5:9b</span>
          {running && <span className="running"><span className="dot" /> running…</span>}
          <span className="spacer" style={{ flex: 1 }} />
          <Artifacts chatId={chatId} refreshKey={artRefresh} />
        </div>

        <div className="stream" ref={streamRef}>
          {messages.length === 0 && transcript.length === 0 ? (
            <div className="empty">
              <h2>Describe the hardware to build</h2>
              <p>e.g. “an 8-bit PWM generator with configurable period and duty cycle”.<br />
                 Attach a spec PDF or a diagram, and watch it go from prompt → RTL → GDSII.</p>
            </div>
          ) : null}

          {/* proper chat alternation: each user turn, then ITS assistant response */}
          {messages.map((m) => {
            if (m.role !== "user") {
              // assistant conclusion / pause / crash note
              return (
                <div key={m.id} className="msg assistant">
                  <div className="avatar">🦅</div>
                  <div className="body"><div className="final"><ReactMarkdown>{m.content}</ReactMarkdown></div></div>
                </div>
              );
            }
            const turn = m.id === runMsgId ? transcript : (pastRuns[m.id] || []);
            const live = m.id === runMsgId && running;
            return (
              <Fragment key={m.id}>
                <div className="msg user">
                  <div className="avatar">🧑</div>
                  <div className="body">
                    <div className="who">You
                      {!running && (
                        <span className="msgactions">
                          <button title="Edit this message" onClick={(e) => editMessage(m.id, m.content, e)}>✎</button>
                          <button title="Delete this message + its run" onClick={(e) => deleteMessage(m.id, e)}>🗑</button>
                        </span>
                      )}
                    </div>
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
                {turn.length > 0 && (
                  <div className="msg assistant">
                    <div className="avatar">🦅</div>
                    <div className="body">
                      <div className="who">
                        GarudaChip{live && <BusyTag />}
                      </div>
                      <Stepper transcript={turn} live={live} />
                      {turn.map((node, i) => (
                        <div key={i} className="node">
                          <div className="head">
                            <span>{STEP_EMOJI[node.node] || "•"}</span>
                            <span>{titleFor(node)}</span>
                          </div>
                          <div className="blocks">
                            {node.blocks.map((b, j) => b.kind === "plan"
                              ? <PlanChecklist key={j} items={(b.payload?.[0] as string[]) || []} turn={turn} live={live} />
                              : <BlockView key={j} block={b} runId={runId} />)}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </Fragment>
            );
          })}
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
              value={prompt}
              placeholder={running ? "Steer the agent — applied at the next step (Enter to send)…"
                                   : "Describe the hardware, or steer the run…"}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); running ? steer() : send(); }
              }}
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
                <>
                  <button className="iconbtn-round" disabled={!prompt.trim()} onClick={steer}
                          title="Send a steering message — applied at the next step">↑</button>
                  <button className="iconbtn-round stop"
                          onClick={() => {
                            if (runId) api.pauseRun(runId);  // tell backend to stop (kills subprocess)
                            unsubRef.current?.();             // detach the stream now
                            setRunning(false);                // UI is free immediately
                          }}
                          title="Stop (state saved — say 'continue' to resume)">
                    <span className="sq" />
                  </button>
                </>
              ) : (
                <button className="iconbtn-round" disabled={!prompt.trim()} onClick={send}
                        title="Send">↑</button>
              )}
            </div>
          </div>
        </div>
        </>}
      </main>

      {confirmDelete && (
        <div className="modal-overlay" onClick={() => setConfirmDelete(null)}>
          <div className="confirm-box" onClick={(e) => e.stopPropagation()}>
            <div className="confirm-icon">🗑</div>
            <div className="confirm-title">Delete this chat?</div>
            <div className="confirm-msg">
              This permanently removes the chat and its design from the database and object
              storage. This can’t be undone.
            </div>
            <div className="confirm-actions">
              <button className="btn-ghost" onClick={() => setConfirmDelete(null)}>Cancel</button>
              <button className="btn-danger" onClick={doDelete}>Delete</button>
            </div>
          </div>
        </div>
      )}

      {confirmMsg && (
        <div className="modal-overlay" onClick={() => setConfirmMsg(null)}>
          <div className="confirm-box" onClick={(e) => e.stopPropagation()}>
            <div className="confirm-icon">🗑</div>
            <div className="confirm-title">Delete this message?</div>
            <div className="confirm-msg">
              Removes this message and its run. Your design files are kept unless this run was their
              only owner. This can’t be undone.
            </div>
            <div className="confirm-actions">
              <button className="btn-ghost" onClick={() => setConfirmMsg(null)}>Cancel</button>
              <button className="btn-danger" onClick={doDeleteMessage}>Delete</button>
            </div>
          </div>
        </div>
      )}

      {editTarget && (
        <div className="modal-overlay" onClick={() => setEditTarget(null)}>
          <div className="edit-box" onClick={(e) => e.stopPropagation()}>
            <div className="edit-title">Edit message</div>
            <textarea
              className="edit-area"
              value={editText}
              autoFocus
              rows={4}
              onChange={(e) => setEditText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) saveEdit();
                if (e.key === "Escape") setEditTarget(null);
              }}
            />
            <div className="confirm-actions">
              <button className="btn-ghost" onClick={() => setEditTarget(null)}>Cancel</button>
              <button className="btn-primary" onClick={saveEdit}>Save</button>
            </div>
          </div>
        </div>
      )}
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
