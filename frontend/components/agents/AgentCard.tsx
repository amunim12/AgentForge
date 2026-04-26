"use client";

import { Bot, Brain, ScrollText } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { LoadingDots } from "@/components/shared/LoadingDots";
import { AGENT_COLORS } from "@/lib/constants";
import { cn } from "@/lib/utils";
import type { AgentName, AgentStatus } from "@/types";

const META: Record<AgentName, { label: string; subtitle: string; icon: LucideIcon }> = {
  planner: {
    label: "Planner",
    subtitle: "Gemini 2.5 Flash",
    icon: Brain,
  },
  executor: {
    label: "Executor",
    subtitle: "Groq · Llama 3.1 70B",
    icon: Bot,
  },
  critic: {
    label: "Critic",
    subtitle: "Gemini 2.5 Pro",
    icon: ScrollText,
  },
};

const STATUS_BADGE: Record<AgentStatus, { label: string; className: string }> = {
  idle: { label: "Idle", className: "bg-muted text-muted-foreground" },
  running: { label: "Running", className: "bg-brand-500/15 text-brand-600 dark:text-brand-400" },
  done: { label: "Done", className: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400" },
  error: { label: "Error", className: "bg-rose-500/15 text-rose-600 dark:text-rose-400" },
};

interface AgentCardProps {
  agent: AgentName;
  status: AgentStatus;
  children?: ReactNode;
}

export function AgentCard({ agent, status, children }: AgentCardProps) {
  const meta = META[agent];
  const colors = AGENT_COLORS[agent];
  const badge = STATUS_BADGE[status];
  const Icon = meta.icon;
  const active = status === "running";

  return (
    <Card
      className={cn(
        "relative flex h-full flex-col overflow-hidden border transition-all",
        colors.border,
        active && ["agent-running", colors.glow],
      )}
    >
      {active ? (
        <div className={cn("absolute inset-x-0 top-0 h-0.5", colors.bg)} />
      ) : null}
      <CardHeader className="flex flex-row items-center justify-between gap-3 pb-3">
        <div className="flex items-center gap-3">
          <div
            className={cn(
              "flex h-10 w-10 items-center justify-center rounded-lg border",
              colors.bg,
              colors.border,
              colors.text,
            )}
          >
            <Icon className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-sm font-semibold">{meta.label}</h3>
            <p className="text-xs text-muted-foreground">{meta.subtitle}</p>
          </div>
        </div>
        <Badge variant="outline" className={cn("gap-1.5 border-0 font-medium", badge.className)}>
          {active ? <LoadingDots className="text-current" /> : null}
          {badge.label}
        </Badge>
      </CardHeader>
      <CardContent className="flex-1 pt-0">{children}</CardContent>
    </Card>
  );
}
