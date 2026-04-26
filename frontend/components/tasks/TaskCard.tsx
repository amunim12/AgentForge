"use client";

import Link from "next/link";
import { ArrowRight, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { TaskStatusBadge } from "@/components/tasks/TaskStatusBadge";
import { timeAgo } from "@/lib/utils";
import type { TaskListItem } from "@/types";

interface TaskCardProps {
  task: TaskListItem;
}

export function TaskCard({ task }: TaskCardProps) {
  const scorePct = typeof task.critic_score === "number" ? Math.round(task.critic_score * 100) : null;
  return (
    <Link href={`/tasks/${task.id}`} className="group block">
      <Card className="h-full transition-all group-hover:border-brand-500/40 group-hover:shadow-md">
        <CardHeader className="flex flex-row items-start justify-between gap-3 pb-3">
          <CardTitle className="line-clamp-2 text-base">{task.title}</CardTitle>
          <TaskStatusBadge status={task.status} />
        </CardHeader>
        <CardContent className="pb-3">
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            {task.category ? (
              <Badge variant="secondary" className="font-normal">
                {task.category}
              </Badge>
            ) : null}
            {task.iteration_count > 1 ? (
              <span className="inline-flex items-center gap-1">
                <Sparkles className="h-3 w-3" />
                {task.iteration_count} iterations
              </span>
            ) : null}
            <span>Created {timeAgo(task.created_at)}</span>
          </div>
        </CardContent>
        <CardFooter className="flex items-center justify-between text-xs text-muted-foreground">
          <div>
            {scorePct !== null ? (
              <span className="font-medium text-foreground">Score: {scorePct}%</span>
            ) : (
              <span>Score pending</span>
            )}
          </div>
          <ArrowRight className="h-4 w-4 opacity-50 transition-transform group-hover:translate-x-1 group-hover:opacity-100" />
        </CardFooter>
      </Card>
    </Link>
  );
}
