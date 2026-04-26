"use client";

import { useTaskStore } from "@/stores/taskStore";
import type { AgentName, AgentStatus } from "@/types";

export function useAgentStatus(): Record<AgentName, AgentStatus> {
  const planner = useTaskStore((s) => s.planner.status);
  const executor = useTaskStore((s) => s.executor.status);
  const critic = useTaskStore((s) => s.critic.status);
  return { planner, executor, critic };
}
