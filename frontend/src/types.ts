export interface Chat {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface MessageFile {
  name: string;
  kind: string; // image | pdf | file
  object_key?: string;
}

export interface Message {
  id: string;
  chat_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  files: MessageFile[];
  created_at: string;
}

export interface Block {
  kind: string; // markdown | code | success | error | image | caption | ...
  payload: any[];
}

export interface TranscriptRecord {
  node: string;
  blocks: Block[];
}

export interface RunRef {
  id: string;
  status: string;
  design_dir?: string;
}

export interface KnowledgeStats {
  total: number;
  by_kind: Record<string, number>;
}

// Build constraints (the picker shown on every new chat)
export interface RunConstraints {
  use_web: boolean;
  run_harden: boolean;
  deep_steps: boolean;
  clock_port: string;
  clock_period: number; // ns
  die_um: number;       // µm, square die
  core_util: number;    // %
}

export const DEFAULT_CONSTRAINTS: RunConstraints = {
  use_web: true,
  run_harden: false,
  deep_steps: true,
  clock_port: "clk",
  clock_period: 24,
  die_um: 600,
  core_util: 25,
};

// SSE event shapes
export type RunEvent =
  | { type: "step"; node: string }
  | { type: "block"; node: string; kind: string; payload: any[] }
  | { type: "knowledge"; total: number }   // store changed at a meaningful event
  | { type: "end"; status: string };
