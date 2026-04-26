"use client";

import { CheckCircle2, Circle, Wrench } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { StreamingText } from "@/components/shared/StreamingText";
import { cn } from "@/lib/utils";
import type { PlanStep, TaskPlan } from "@/types";

interface PlannerOutputProps {
  streaming: boolean;
  streamText: string;
  plan: TaskPlan | null;
}

const TOOL_BADGE: Record<PlanStep["tool"], string> = {
  web_search: "Web Search",
  code_executor: "Code",
  file_tool: "File",
  reasoning: "Reasoning",
  none: "—",
};

export function PlannerOutput({ streaming, streamText, plan }: PlannerOutputProps) {
  if (plan) {
    return (
      <div className="space-y-3">
        <div className="rounded-md border border-border/60 bg-muted/30 p-3">
          <p className="text-xs text-muted-foreground">Summary</p>
          <p className="mt-1 text-sm">{plan.task_summary}</p>
          <div className="mt-2 flex flex-wrap gap-2 text-xs">
            <Badge variant="outline" className="font-normal">
              Complexity · {plan.complexity}
            </Badge>
            <Badge variant="outline" className="font-normal">
              Steps · {plan.estimated_steps}
            </Badge>
          </div>
        </div>

        <ol className="space-y-2">
          {plan.steps.map((step) => (
            <li
              key={step.step_id}
              className="flex gap-3 rounded-md border border-border/60 bg-card/50 p-3"
            >
              <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-planner/40 bg-planner/10 text-[10px] font-semibold text-planner">
                {step.step_id}
              </div>
              <div className="min-w-0 flex-1 space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium">{step.title}</span>
                  {step.critical ? (
                    <Badge variant="outline" className="border-amber-500/50 text-amber-600 dark:text-amber-400">
                      Critical
                    </Badge>
                  ) : null}
                </div>
                <p className="text-xs text-muted-foreground">{step.description}</p>
                <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                  <span
                    className={cn(
                      "inline-flex items-center gap-1 rounded-full border border-border px-2 py-0.5",
                      step.tool !== "none" && "text-foreground",
                    )}
                  >
                    <Wrench className="h-3 w-3" />
                    {TOOL_BADGE[step.tool]}
                  </span>
                  {step.dependencies.length > 0 ? (
                    <span>Depends on {step.dependencies.join(", ")}</span>
                  ) : null}
                </div>
              </div>
            </li>
          ))}
        </ol>

        <div className="flex items-start gap-2 rounded-md border border-emerald-500/30 bg-emerald-500/5 p-3 text-xs">
          <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-500" />
          <div>
            <p className="font-medium text-emerald-600 dark:text-emerald-400">
              Success criteria
            </p>
            <p className="mt-0.5 text-muted-foreground">{plan.success_criteria}</p>
          </div>
        </div>
      </div>
    );
  }

  if (streaming || streamText) {
    return <StreamingText text={streamText} streaming={streaming} />;
  }

  return (
    <div className="flex items-center gap-2 text-xs text-muted-foreground">
      <Circle className="h-3 w-3" />
      Awaiting plan…
    </div>
  );
}
