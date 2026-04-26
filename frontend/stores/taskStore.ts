"use client";

import { create } from "zustand";

import type { AgentName, AgentStatus } from "@/types";

export interface AgentSlice {
  status: AgentStatus;
  streamText: string;
  output: Record<string, unknown> | null;
}

export interface ToolCallEntry {
  id: string;
  tool: string;
  input: string;
  output_preview?: string;
  duration_ms?: number;
  timestamp: number;
}

interface TaskStoreState {
  taskId: string | null;
  planner: AgentSlice;
  executor: AgentSlice;
  critic: AgentSlice;
  toolCalls: ToolCallEntry[];
  iteration: number;
  finalResult: string | null;
  finalScore: number | null;
  error: string | null;
  isComplete: boolean;

  reset: (taskId: string) => void;
  setAgentStatus: (agent: AgentName, status: AgentStatus) => void;
  appendStream: (agent: AgentName, delta: string) => void;
  setAgentOutput: (agent: AgentName, output: Record<string, unknown>) => void;
  addToolCall: (entry: Omit<ToolCallEntry, "id" | "timestamp">) => void;
  setTaskComplete: (result: string, score: number) => void;
  setTaskFailed: (error: string) => void;
  bumpIteration: () => void;
}

const emptyAgent: AgentSlice = {
  status: "idle",
  streamText: "",
  output: null,
};

export const useTaskStore = create<TaskStoreState>((set) => ({
  taskId: null,
  planner: { ...emptyAgent },
  executor: { ...emptyAgent },
  critic: { ...emptyAgent },
  toolCalls: [],
  iteration: 0,
  finalResult: null,
  finalScore: null,
  error: null,
  isComplete: false,

  reset: (taskId) =>
    set({
      taskId,
      planner: { ...emptyAgent },
      executor: { ...emptyAgent },
      critic: { ...emptyAgent },
      toolCalls: [],
      iteration: 0,
      finalResult: null,
      finalScore: null,
      error: null,
      isComplete: false,
    }),

  setAgentStatus: (agent, status) =>
    set((state) => {
      const slice = state[agent];
      // Starting a new run for this agent clears prior streamText so the
      // stream panel doesn't mix old iterations with new ones.
      const next: AgentSlice =
        status === "running"
          ? { status, streamText: "", output: slice.output }
          : { ...slice, status };
      return { [agent]: next } as Partial<TaskStoreState>;
    }),

  appendStream: (agent, delta) =>
    set((state) => ({
      [agent]: { ...state[agent], streamText: state[agent].streamText + delta },
    })) as never,

  setAgentOutput: (agent, output) =>
    set((state) => ({
      [agent]: { ...state[agent], output, status: "done" },
    })) as never,

  addToolCall: (entry) =>
    set((state) => ({
      toolCalls: [
        ...state.toolCalls,
        {
          ...entry,
          id: `${state.toolCalls.length}-${Date.now()}`,
          timestamp: Date.now(),
        },
      ],
    })),

  setTaskComplete: (result, score) =>
    set({ finalResult: result, finalScore: score, isComplete: true }),

  setTaskFailed: (error) => set({ error, isComplete: true }),

  bumpIteration: () => set((state) => ({ iteration: state.iteration + 1 })),
}));
