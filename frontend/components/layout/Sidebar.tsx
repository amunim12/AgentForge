"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { History, LayoutDashboard, PlusCircle, Settings, Sparkles } from "lucide-react";

import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/tasks/new", label: "New Task", icon: PlusCircle },
  { href: "/history", label: "History", icon: History },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden w-60 shrink-0 flex-col border-r border-border/60 bg-muted/20 p-4 lg:flex">
      <div className="mb-6 flex items-center gap-2 px-2 py-1">
        <Sparkles className="h-4 w-4 text-brand-500" />
        <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          Orchestration
        </span>
      </div>

      <nav className="flex flex-col gap-1">
        {NAV_ITEMS.map((item) => {
          const active =
            pathname === item.href ||
            (item.href !== "/dashboard" && pathname.startsWith(item.href));
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-brand-500/10 text-brand-600 dark:text-brand-400"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto rounded-lg border border-border/60 bg-card/60 p-4">
        <p className="text-xs font-semibold">Planner → Executor → Critic</p>
        <p className="mt-1 text-xs text-muted-foreground">
          Multi-agent pipeline powered by Gemini &amp; Groq.
        </p>
      </div>
    </aside>
  );
}
