"use client";

import { motion } from "framer-motion";
import {
  ArrowRight,
  Bot,
  Brain,
  Gauge,
  Layers,
  ScrollText,
  ShieldCheck,
  Sparkles,
  Zap,
} from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/layout/ThemeToggle";

const AGENTS = [
  {
    name: "Planner",
    model: "Gemini 2.5 Flash",
    icon: Brain,
    border: "border-planner/40",
    iconBg: "bg-planner/10 text-planner",
    blurb:
      "Decomposes ambiguous tasks into a structured, dependency-aware execution plan with success criteria.",
  },
  {
    name: "Executor",
    model: "Groq · Llama 3.1 70B",
    icon: Bot,
    border: "border-executor/40",
    iconBg: "bg-executor/10 text-executor",
    blurb:
      "Runs the plan with tool calls — web search, code execution, and notebook tools — at ultra-low latency.",
  },
  {
    name: "Critic",
    model: "Gemini 2.5 Pro",
    icon: ScrollText,
    border: "border-critic/40",
    iconBg: "bg-critic/10 text-critic",
    blurb:
      "Scores the result against a 5-axis rubric and triggers a self-correcting retry loop until it accepts.",
  },
];

const FEATURES = [
  {
    icon: Layers,
    title: "LangGraph orchestration",
    body: "Stateful multi-agent graph with conditional retry edges and full audit trail per iteration.",
  },
  {
    icon: Zap,
    title: "Real-time streaming",
    body: "WebSocket fan-out streams token-by-token reasoning and tool calls straight to the UI.",
  },
  {
    icon: ShieldCheck,
    title: "Production hardening",
    body: "JWT auth, rate limiting, structured logs, security middleware, and CI-enforced static analysis.",
  },
  {
    icon: Gauge,
    title: "Observable & measurable",
    body: "Per-iteration scoring, tool latency, and end-to-end task duration captured for every run.",
  },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-40 border-b border-border/60 bg-background/70 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
          <Link href="/" className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-sm">
              <span className="text-sm font-bold">AF</span>
            </div>
            <span className="text-sm font-semibold tracking-tight">AgentForge</span>
          </Link>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <Button variant="ghost" size="sm" asChild>
              <Link href="/login">Sign in</Link>
            </Button>
            <Button variant="brand" size="sm" asChild>
              <Link href="/register">Get started</Link>
            </Button>
          </div>
        </div>
      </header>

      <section className="relative overflow-hidden">
        <div className="absolute inset-0 -z-10 bg-[radial-gradient(60%_60%_at_50%_0%,rgba(99,102,241,0.18),transparent_70%)]" />
        <div className="mx-auto max-w-7xl px-6 pt-20 pb-24 text-center">
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="inline-flex items-center gap-2 rounded-full border border-border/60 bg-card/60 px-3 py-1 text-xs text-muted-foreground"
          >
            <Sparkles className="h-3 w-3 text-brand-500" />
            Multi-Agent AI Orchestration · v0.1
          </motion.div>
          <motion.h1
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.05 }}
            className="mt-6 text-4xl font-bold tracking-tight sm:text-5xl md:text-6xl"
          >
            Three agents.{" "}
            <span className="gradient-text">One reliable answer.</span>
          </motion.h1>
          <motion.p
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.1 }}
            className="mx-auto mt-5 max-w-2xl text-base text-muted-foreground sm:text-lg"
          >
            AgentForge plans, executes, and self-critiques every task. Watch the
            pipeline reason in real time — and ship results you can trust.
          </motion.p>
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.15 }}
            className="mt-8 flex flex-wrap items-center justify-center gap-3"
          >
            <Button variant="brand" size="lg" asChild>
              <Link href="/register" className="flex items-center gap-2">
                Start building <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
            <Button variant="outline" size="lg" asChild>
              <Link href="/login">I already have an account</Link>
            </Button>
          </motion.div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-6 pb-16">
        <div className="grid gap-4 md:grid-cols-3">
          {AGENTS.map((agent, i) => {
            const Icon = agent.icon;
            return (
              <motion.div
                key={agent.name}
                initial={{ opacity: 0, y: 14 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.45, delay: i * 0.08 }}
                className={`relative overflow-hidden rounded-xl border bg-card p-6 shadow-sm ${agent.border}`}
              >
                <div
                  className={`mb-4 inline-flex h-10 w-10 items-center justify-center rounded-lg ${agent.iconBg}`}
                >
                  <Icon className="h-5 w-5" />
                </div>
                <h3 className="text-base font-semibold">{agent.name}</h3>
                <p className="text-xs text-muted-foreground">{agent.model}</p>
                <p className="mt-3 text-sm text-muted-foreground">{agent.blurb}</p>
              </motion.div>
            );
          })}
        </div>
      </section>

      <section className="border-t border-border/60 bg-muted/20">
        <div className="mx-auto max-w-7xl px-6 py-16">
          <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
            Built for production, designed for clarity.
          </h2>
          <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {FEATURES.map((f) => {
              const Icon = f.icon;
              return (
                <div
                  key={f.title}
                  className="rounded-xl border border-border/60 bg-card p-5"
                >
                  <Icon className="h-5 w-5 text-brand-500" />
                  <h3 className="mt-3 text-sm font-semibold">{f.title}</h3>
                  <p className="mt-1 text-xs text-muted-foreground">{f.body}</p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      <footer className="border-t border-border/60">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-6 text-xs text-muted-foreground">
          <span>© 2026 AgentForge. Portfolio project.</span>
          <span>Planner → Executor → Critic</span>
        </div>
      </footer>
    </div>
  );
}
