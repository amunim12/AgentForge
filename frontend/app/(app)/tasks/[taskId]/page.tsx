"use client";

import { motion } from "framer-motion";
import { ArrowLeft, RotateCcw, Sparkles } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo } from "react";
import ReactMarkdown from "react-markdown";

import { AgentCard } from "@/components/agents/AgentCard";
import { AgentTimeline } from "@/components/agents/AgentTimeline";
import { CriticOutput } from "@/components/agents/CriticOutput";
import { ExecutorOutput } from "@/components/agents/ExecutorOutput";
import { PlannerOutput } from "@/components/agents/PlannerOutput";
import { TaskStatusBadge } from "@/components/tasks/TaskStatusBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { useAgentStatus } from "@/hooks/useAgentStatus";
import { useTaskStream } from "@/hooks/useTaskStream";
import { useTask } from "@/hooks/useTasks";
import { cn } from "@/lib/utils";
import { useTaskStore } from "@/stores/taskStore";
import type {
  AgentName,
  AgentStatus,
  CriticVerdict,
  ExecutorResult,
  TaskPlan,
} from "@/types";

export default function TaskDetailPage() {
  const params = useParams<{ taskId: string }>();
  const taskId = params?.taskId ?? null;

  const { data: task, isLoading, refetch } = useTask(taskId);
  useTaskStream({ taskId });

  const liveStatuses = useAgentStatus();
  const planner = useTaskStore((s) => s.planner);
  const executor = useTaskStore((s) => s.executor);
  const critic = useTaskStore((s) => s.critic);
  const toolCalls = useTaskStore((s) => s.toolCalls);
  const iteration = useTaskStore((s) => s.iteration);
  const finalResult = useTaskStore((s) => s.finalResult);
  const finalScore = useTaskStore((s) => s.finalScore);
  const error = useTaskStore((s) => s.error);
  const isComplete = useTaskStore((s) => s.isComplete);

  useEffect(() => {
    if (isComplete) {
      refetch();
    }
  }, [isComplete, refetch]);

  const statuses: Record<AgentName, AgentStatus> = useMemo(() => {
    if (task && task.status === "completed" && !isComplete) {
      return { planner: "done", executor: "done", critic: "done" };
    }
    if (task && task.status === "failed" && !isComplete) {
      return {
        planner: liveStatuses.planner === "idle" ? "done" : liveStatuses.planner,
        executor: liveStatuses.executor === "idle" ? "done" : liveStatuses.executor,
        critic: "error",
      };
    }
    return liveStatuses;
  }, [task, isComplete, liveStatuses]);

  const plan: TaskPlan | null = useMemo(() => {
    if (planner.output) return planner.output as unknown as TaskPlan;
    return task?.planner_output ?? null;
  }, [planner.output, task?.planner_output]);

  const executorResult: ExecutorResult | null = useMemo(() => {
    if (executor.output) return executor.output as unknown as ExecutorResult;
    return task?.executor_output ?? null;
  }, [executor.output, task?.executor_output]);

  const criticVerdict: CriticVerdict | null = useMemo(() => {
    if (critic.output) return critic.output as unknown as CriticVerdict;
    return task?.critic_output ?? null;
  }, [critic.output, task?.critic_output]);

  const resolvedFinalResult = finalResult ?? task?.final_result ?? null;
  const resolvedFinalScore =
    finalScore ?? (typeof task?.critic_score === "number" ? task.critic_score : null);
  const resolvedError = error ?? task?.error_message ?? null;
  const totalIterations = task?.iteration_count ?? iteration + 1;

  if (isLoading || !task) {
    return (
      <div className="mx-auto max-w-7xl space-y-4 px-6 py-8">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-32 w-full" />
        <div className="grid gap-3 lg:grid-cols-3">
          <Skeleton className="h-80" />
          <Skeleton className="h-80" />
          <Skeleton className="h-80" />
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6 px-6 py-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="h-3 w-3" />
            Back to dashboard
          </Link>
          <h1 className="mt-1 text-2xl font-bold tracking-tight">{task.title}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <TaskStatusBadge status={task.status} />
            {task.category ? (
              <Badge variant="secondary" className="font-normal">
                {task.category}
              </Badge>
            ) : null}
            {totalIterations > 1 ? (
              <Badge variant="outline" className="font-normal">
                <RotateCcw className="mr-1 h-3 w-3" />
                {totalIterations} iterations
              </Badge>
            ) : null}
          </div>
        </div>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            Description
          </CardTitle>
        </CardHeader>
        <CardContent className="text-sm leading-relaxed">{task.description}</CardContent>
      </Card>

      <AgentTimeline statuses={statuses} iteration={iteration} />

      <div className="grid gap-3 lg:grid-cols-3">
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          <AgentCard agent="planner" status={statuses.planner}>
            <PlannerOutput
              streaming={statuses.planner === "running"}
              streamText={planner.streamText}
              plan={plan}
            />
          </AgentCard>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
        >
          <AgentCard agent="executor" status={statuses.executor}>
            <ExecutorOutput
              streaming={statuses.executor === "running"}
              streamText={executor.streamText}
              result={executorResult}
              toolCalls={toolCalls}
            />
          </AgentCard>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <AgentCard agent="critic" status={statuses.critic}>
            <CriticOutput
              streaming={statuses.critic === "running"}
              streamText={critic.streamText}
              verdict={criticVerdict}
            />
          </AgentCard>
        </motion.div>
      </div>

      {resolvedError ? (
        <Card className="border-rose-500/40 bg-rose-500/5">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-rose-600 dark:text-rose-400">
              Pipeline failed
            </CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-muted-foreground">
            {resolvedError}
          </CardContent>
        </Card>
      ) : null}

      {resolvedFinalResult ? (
        <Card className="border-emerald-500/40">
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-emerald-500" />
              Final result
            </CardTitle>
            {resolvedFinalScore !== null ? (
              <Badge
                variant="outline"
                className={cn(
                  "font-medium",
                  resolvedFinalScore >= 0.85
                    ? "border-emerald-500/40 text-emerald-600 dark:text-emerald-400"
                    : "border-amber-500/40 text-amber-600 dark:text-amber-400",
                )}
              >
                Score · {Math.round(resolvedFinalScore * 100)}%
              </Badge>
            ) : null}
          </CardHeader>
          <Separator />
          <CardContent className="markdown-block pt-4 text-sm leading-relaxed">
            <ReactMarkdown>{resolvedFinalResult}</ReactMarkdown>
          </CardContent>
          <CardContent className="pt-0">
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" asChild>
                <Link href="/tasks/new">Run another task</Link>
              </Button>
              <Button
                variant="ghost"
                onClick={() => navigator.clipboard.writeText(resolvedFinalResult)}
              >
                Copy result
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
