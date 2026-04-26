"use client";

import { useEffect, useRef } from "react";

import { getAccessToken } from "@/lib/auth";
import { WS_URL } from "@/lib/constants";
import { useTaskStore } from "@/stores/taskStore";
import type { AgentEvent } from "@/types";

interface UseTaskStreamOptions {
  taskId: string | null;
  enabled?: boolean;
}

const TASK_STATUS_TO_AGENT: Record<string, "planner" | "executor" | "critic"> = {
  planning: "planner",
  executing: "executor",
  critiquing: "critic",
};

export function useTaskStream({ taskId, enabled = true }: UseTaskStreamOptions) {
  const reset = useTaskStore((s) => s.reset);
  const setAgentStatus = useTaskStore((s) => s.setAgentStatus);
  const appendStream = useTaskStore((s) => s.appendStream);
  const setAgentOutput = useTaskStore((s) => s.setAgentOutput);
  const addToolCall = useTaskStore((s) => s.addToolCall);
  const setTaskComplete = useTaskStore((s) => s.setTaskComplete);
  const setTaskFailed = useTaskStore((s) => s.setTaskFailed);
  const bumpIteration = useTaskStore((s) => s.bumpIteration);

  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!taskId || !enabled) return;
    const token = getAccessToken();
    if (!token) return;

    reset(taskId);
    let cancelled = false;

    const url = `${WS_URL}/ws/tasks/${taskId}?token=${encodeURIComponent(token)}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onmessage = (msg) => {
      if (cancelled) return;
      let event: AgentEvent;
      try {
        event = JSON.parse(msg.data);
      } catch {
        return;
      }

      switch (event.type) {
        case "agent_start":
          if (event.agent === "planner" && useTaskStore.getState().planner.status !== "idle") {
            bumpIteration();
          }
          setAgentStatus(event.agent, "running");
          break;
        case "agent_stream":
          appendStream(event.agent, event.delta);
          break;
        case "agent_tool_call":
          addToolCall({
            tool: event.tool,
            input: event.input,
            output_preview: event.output_preview,
            duration_ms: event.duration_ms,
          });
          break;
        case "agent_done":
          setAgentOutput(event.agent, event.output);
          break;
        case "task_complete":
          setTaskComplete(event.result, event.score);
          break;
        case "task_failed":
          setTaskFailed(event.error);
          break;
      }
    };

    ws.onerror = () => {
      // socket-level errors are surfaced through close
    };

    return () => {
      cancelled = true;
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close();
      }
      wsRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [taskId, enabled]);
}

export function deriveAgentFromTaskStatus(status: string) {
  return TASK_STATUS_TO_AGENT[status] ?? null;
}
