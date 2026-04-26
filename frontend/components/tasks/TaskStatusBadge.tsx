import { CheckCircle2, CircleDashed, Loader2, XCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { TaskStatus } from "@/types";

const CONFIG: Record<
  TaskStatus,
  { label: string; className: string; icon: typeof CircleDashed }
> = {
  pending: {
    label: "Pending",
    className: "bg-muted text-muted-foreground",
    icon: CircleDashed,
  },
  planning: {
    label: "Planning",
    className: "bg-planner/15 text-planner border-planner/30",
    icon: Loader2,
  },
  executing: {
    label: "Executing",
    className: "bg-executor/15 text-executor border-executor/30",
    icon: Loader2,
  },
  critiquing: {
    label: "Critiquing",
    className: "bg-critic/15 text-critic border-critic/30",
    icon: Loader2,
  },
  completed: {
    label: "Completed",
    className: "bg-emerald-500/15 text-emerald-600 border-emerald-500/30 dark:text-emerald-400",
    icon: CheckCircle2,
  },
  failed: {
    label: "Failed",
    className: "bg-rose-500/15 text-rose-600 border-rose-500/30 dark:text-rose-400",
    icon: XCircle,
  },
};

interface TaskStatusBadgeProps {
  status: TaskStatus;
  className?: string;
}

export function TaskStatusBadge({ status, className }: TaskStatusBadgeProps) {
  const { label, className: variantClass, icon: Icon } = CONFIG[status];
  const spinning = status === "planning" || status === "executing" || status === "critiquing";
  return (
    <Badge
      variant="outline"
      className={cn("gap-1.5 border font-medium", variantClass, className)}
    >
      <Icon className={cn("h-3 w-3", spinning && "animate-spin")} />
      {label}
    </Badge>
  );
}
