"use client";

import Link from "next/link";
import { ArrowRight, CheckCircle2, ListTodo, PlusCircle, TrendingUp } from "lucide-react";
import { useMemo } from "react";

import { AnimatedCounter } from "@/components/shared/AnimatedCounter";
import { TaskCard } from "@/components/tasks/TaskCard";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useTasks } from "@/hooks/useTasks";
import { useAuth } from "@/providers/AuthProvider";

export default function DashboardPage() {
  const { user } = useAuth();
  const { data: tasks, isLoading } = useTasks({ limit: 12 });

  const stats = useMemo(() => {
    if (!tasks) return { total: 0, completed: 0, avgScore: 0 };
    const total = tasks.length;
    const completed = tasks.filter((t) => t.status === "completed").length;
    const scored = tasks.filter((t) => typeof t.critic_score === "number");
    const avgScore = scored.length
      ? scored.reduce((s, t) => s + (t.critic_score ?? 0), 0) / scored.length
      : 0;
    return { total, completed, avgScore };
  }, [tasks]);

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            Welcome back{user?.username ? `, ${user.username}` : ""}.
          </h1>
          <p className="text-sm text-muted-foreground">
            Three agents stand ready. Hand them something interesting.
          </p>
        </div>
        <Button variant="brand" asChild>
          <Link href="/tasks/new" className="flex items-center gap-2">
            <PlusCircle className="h-4 w-4" />
            New task
          </Link>
        </Button>
      </div>

      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        <StatCard
          icon={<ListTodo className="h-4 w-4" />}
          label="Total tasks"
          value={stats.total}
        />
        <StatCard
          icon={<CheckCircle2 className="h-4 w-4 text-emerald-500" />}
          label="Completed"
          value={stats.completed}
        />
        <StatCard
          icon={<TrendingUp className="h-4 w-4 text-brand-500" />}
          label="Avg critic score"
          value={Math.round(stats.avgScore * 100)}
          suffix="%"
        />
      </div>

      <div className="mt-8 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Recent tasks</h2>
        <Link
          href="/history"
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          View all <ArrowRight className="h-3 w-3" />
        </Link>
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {isLoading ? (
          Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-40 w-full" />
          ))
        ) : tasks && tasks.length > 0 ? (
          tasks.map((task) => <TaskCard key={task.id} task={task} />)
        ) : (
          <EmptyState />
        )}
      </div>
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
  suffix,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  suffix?: string;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
        {icon}
      </CardHeader>
      <CardContent>
        <div className="text-3xl font-bold tracking-tight">
          <AnimatedCounter value={value} />
          {suffix ? <span className="text-base font-medium text-muted-foreground">{suffix}</span> : null}
        </div>
      </CardContent>
    </Card>
  );
}

function EmptyState() {
  return (
    <Card className="col-span-full">
      <CardContent className="flex flex-col items-center justify-center gap-3 py-12 text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-brand-500/10 text-brand-500">
          <PlusCircle className="h-6 w-6" />
        </div>
        <div>
          <p className="text-sm font-semibold">No tasks yet</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Create your first task to see the agent pipeline come alive.
          </p>
        </div>
        <Button variant="brand" asChild>
          <Link href="/tasks/new">Create a task</Link>
        </Button>
      </CardContent>
    </Card>
  );
}
