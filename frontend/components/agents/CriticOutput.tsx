"use client";

import { CheckCircle2, Circle, XCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { StreamingText } from "@/components/shared/StreamingText";
import { cn } from "@/lib/utils";
import type { CriticVerdict } from "@/types";

interface CriticOutputProps {
  streaming: boolean;
  streamText: string;
  verdict: CriticVerdict | null;
}

const RUBRIC_LABELS: Array<[keyof CriticVerdict["rubric"], string]> = [
  ["accuracy", "Accuracy"],
  ["completeness", "Completeness"],
  ["clarity", "Clarity"],
  ["relevance", "Relevance"],
  ["depth", "Depth"],
];

export function CriticOutput({ streaming, streamText, verdict }: CriticOutputProps) {
  if (verdict) {
    const accepted = verdict.verdict === "accept";
    const scorePct = Math.round(verdict.score * 100);
    return (
      <div className="space-y-3">
        <div
          className={cn(
            "flex items-start gap-3 rounded-md border p-3",
            accepted
              ? "border-emerald-500/30 bg-emerald-500/5"
              : "border-amber-500/30 bg-amber-500/5",
          )}
        >
          {accepted ? (
            <CheckCircle2 className="mt-0.5 h-5 w-5 text-emerald-500" />
          ) : (
            <XCircle className="mt-0.5 h-5 w-5 text-amber-500" />
          )}
          <div className="flex-1">
            <p
              className={cn(
                "text-sm font-semibold",
                accepted
                  ? "text-emerald-600 dark:text-emerald-400"
                  : "text-amber-600 dark:text-amber-400",
              )}
            >
              {accepted ? "Accepted" : "Revise"} · Score {scorePct}%
            </p>
            <Progress value={scorePct} className="mt-2" />
          </div>
        </div>

        <div className="space-y-2">
          {RUBRIC_LABELS.map(([key, label]) => {
            const entry = verdict.rubric[key];
            const pct = Math.round(entry.score * 100);
            return (
              <div key={key} className="rounded-md border border-border/60 bg-card/40 p-2.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-medium">{label}</span>
                  <span className="text-muted-foreground">{pct}%</span>
                </div>
                <Progress value={pct} className="mt-1.5 h-1" />
                {entry.comment ? (
                  <p className="mt-1.5 text-[11px] text-muted-foreground">{entry.comment}</p>
                ) : null}
              </div>
            );
          })}
        </div>

        {verdict.strengths.length ? (
          <div className="space-y-1">
            <p className="text-xs font-semibold text-emerald-600 dark:text-emerald-400">
              Strengths
            </p>
            <ul className="space-y-1 text-xs">
              {verdict.strengths.map((s, i) => (
                <li key={i} className="flex gap-2">
                  <span className="text-emerald-500">+</span>
                  <span className="text-muted-foreground">{s}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {verdict.improvements_needed.length ? (
          <div className="space-y-1">
            <p className="text-xs font-semibold text-amber-600 dark:text-amber-400">
              Improvements needed
            </p>
            <ul className="space-y-1 text-xs">
              {verdict.improvements_needed.map((s, i) => (
                <li key={i} className="flex gap-2">
                  <span className="text-amber-500">!</span>
                  <span className="text-muted-foreground">{s}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {!accepted && verdict.specific_instructions_for_next_iteration ? (
          <div className="rounded-md border border-border/60 bg-muted/30 p-3 text-xs">
            <p className="font-semibold">Next iteration guidance</p>
            <p className="mt-1 text-muted-foreground">
              {verdict.specific_instructions_for_next_iteration}
            </p>
          </div>
        ) : null}

        <div className="flex flex-wrap gap-2">
          <Badge variant="outline">Verdict · {verdict.verdict}</Badge>
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
      Awaiting executor output…
    </div>
  );
}
