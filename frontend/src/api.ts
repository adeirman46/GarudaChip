import type { Chat, KnowledgeStats, Message, RunEvent } from "./types";

const J = { "Content-Type": "application/json" };

export const api = {
  async listChats(): Promise<Chat[]> {
    return (await fetch("/api/chats")).json();
  },
  async createChat(title?: string): Promise<Chat> {
    return (await fetch("/api/chats", {
      method: "POST", headers: J, body: JSON.stringify({ title }),
    })).json();
  },
  async getChat(id: string): Promise<{ chat: Chat; messages: Message[]; run: any; transcript: any[] }> {
    return (await fetch(`/api/chats/${id}`)).json();
  },
  async deleteChat(id: string): Promise<void> {
    await fetch(`/api/chats/${id}`, { method: "DELETE" });
  },
  async knowledge(): Promise<KnowledgeStats> {
    return (await fetch("/api/knowledge/stats")).json();
  },

  /** Send a prompt (+ optional files); returns the started run id. */
  async sendMessage(
    chatId: string, prompt: string, files: File[], opts: object
  ): Promise<{ message: Message; run: { id: string } }> {
    const fd = new FormData();
    fd.append("prompt", prompt);
    fd.append("opts", JSON.stringify(opts));
    for (const f of files) fd.append("files", f);
    return (await fetch(`/api/chats/${chatId}/messages`, { method: "POST", body: fd })).json();
  },

  async pauseRun(runId: string): Promise<void> {
    await fetch(`/api/runs/${runId}/pause`, { method: "POST" });
  },

  /** Subscribe to a run's SSE stream. Returns an unsubscribe fn. */
  streamRun(runId: string, onEvent: (e: RunEvent) => void): () => void {
    const es = new EventSource(`/api/runs/${runId}/stream`);
    es.onmessage = (m) => {
      try { onEvent(JSON.parse(m.data)); } catch { /* heartbeat */ }
    };
    es.onerror = () => es.close();
    return () => es.close();
  },

  fileUrl(runId: string, path: string): string {
    return `/api/runs/${runId}/file?path=${encodeURIComponent(path)}`;
  },
};
