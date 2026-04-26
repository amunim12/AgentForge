"use client";

import { useState } from "react";

import { TaskCard } from "@/components/tasks/TaskCard";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useTasks } from "@/hooks/useTasks";
import { cn } from "@/lib/utils";
import type { TaskStatus } from "@/types";

const FILTERS: Array<{ value: TaskStatus | "all"; label: string }> = [
  { value: "all", label: "All" },
  { value: "completed", label: "Completed" },
  { value: "executing", label: "Running" },
  { value: "failed", label: "Failed" },
];

export default function HistoryPage() {
  const [filter, setFilter] = useState<TaskStatus | "all">("all");
  const params = filter === "all" ? { limit: 100 } : { limit: 100, status: filter };
  const { data: tasks, isLoading } = useTasks(params);

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Task history</h1>
        <p className="text-sm text-muted-foreground">
          Every run, scored and archived.
        </p>
      </div>

      <div className="mt-5 flex flex-wrap gap-2">
        {FILTERS.map((f) => {
          const active = filter === f.value;
          return (
            <button
              key={f.value}
              onClick={() => setFilter(f.value)}
              className={cn(
                "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                active
                  ? "border-brand-500 bg-brand-500/10 text-brand-600 dark:text-brand-400"
                  : "border-border text-muted-foreground hover:border-foreground/40 hover:text-foreground",
              )}
            >
              {f.label}
            </button>
          );
        })}
      </div>

      <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {isLoading ? (
          Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-40" />
          ))
        ) : tasks && tasks.length > 0 ? (
          tasks.map((task) => <TaskCard key={task.id} task={task} />)
        ) : (
          <Card className="col-span-full">
            <CardContent className="py-12 text-center text-sm text-muted-foreground">
              No tasks match this filter.
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
