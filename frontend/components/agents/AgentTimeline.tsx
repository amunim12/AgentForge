"use client";

import { ArrowRight } from "lucide-react";

import { AGENT_COLORS } from "@/lib/constants";
import { cn } from "@/lib/utils";
import type { AgentName, AgentStatus } from "@/types";

interface AgentTimelineProps {
  statuses: Record<AgentName, AgentStatus>;
  iteration: number;
}

const ORDER: AgentName[] = ["planner", "executor", "critic"];
const LABEL: Record<AgentName, string> = {
  planner: "Planner",
  executor: "Executor",
  critic: "Critic",
};

export function AgentTimeline({ statuses, iteration }: AgentTimelineProps) {
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border/60 bg-muted/30 px-3 py-2 text-xs">
      {ORDER.map((agent, index) => {
        const status = statuses[agent];
        const colors = AGENT_COLORS[agent];
        return (
          <div key={agent} className="flex items-center gap-2">
            <div
              className={cn(
                "flex items-center gap-2 rounded-full border px-2.5 py-1 font-medium",
                status === "running"
                  ? [colors.bg, colors.border, colors.text]
                  : status === "done"
                  ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                  : status === "error"
                  ? "border-rose-500/40 bg-rose-500/10 text-rose-600 dark:text-rose-400"
                  : "border-border text-muted-foreground",
              )}
            >
              <span
                className={cn(
                  "h-1.5 w-1.5 rounded-full bg-current",
                  status === "running" && "animate-pulse",
                )}
              />
              {LABEL[agent]}
            </div>
            {index < ORDER.length - 1 ? (
              <ArrowRight className="h-3 w-3 text-muted-foreground" />
            ) : null}
          </div>
        );
      })}
      {iteration > 0 ? (
        <span className="ml-auto text-muted-foreground">
          Iteration <span className="font-semibold text-foreground">{iteration + 1}</span>
        </span>
      ) : null}
    </div>
  );
}
