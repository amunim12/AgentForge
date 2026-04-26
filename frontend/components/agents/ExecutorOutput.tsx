"use client";

import { Circle, Terminal } from "lucide-react";
import ReactMarkdown from "react-markdown";

import { StreamingText } from "@/components/shared/StreamingText";
import { Badge } from "@/components/ui/badge";
import type { ToolCallEntry } from "@/stores/taskStore";
import type { ExecutorResult } from "@/types";

interface ExecutorOutputProps {
  streaming: boolean;
  streamText: string;
  result: ExecutorResult | null;
  toolCalls: ToolCallEntry[];
}

export function ExecutorOutput({
  streaming,
  streamText,
  result,
  toolCalls,
}: ExecutorOutputProps) {
  if (result) {
    return (
      <div className="space-y-3">
        <div className="flex flex-wrap gap-2 text-xs">
          <Badge variant="outline" className="font-normal">
            Steps completed · {result.steps_completed}
          </Badge>
          <Badge variant="outline" className="font-normal">
            Tool calls · {result.tool_calls.length}
          </Badge>
          {typeof result.duration_ms === "number" ? (
            <Badge variant="outline" className="font-normal">
              Duration · {(result.duration_ms / 1000).toFixed(1)}s
            </Badge>
          ) : null}
        </div>

        <div className="markdown-block rounded-md border border-border/60 bg-card/50 p-3 text-sm leading-relaxed">
          <ReactMarkdown>{result.formatted_output || "_No output_"}</ReactMarkdown>
        </div>

        {result.tool_calls.length ? (
          <ToolCallList calls={result.tool_calls.map((c, i) => ({
            id: `rc-${i}`,
            tool: c.tool,
            input: c.input,
            output_preview: c.output_preview,
            duration_ms: c.duration_ms,
            timestamp: 0,
          }))} />
        ) : null}
      </div>
    );
  }

  if (streaming || streamText || toolCalls.length) {
    return (
      <div className="space-y-3">
        {toolCalls.length ? <ToolCallList calls={toolCalls} /> : null}
        {streaming || streamText ? (
          <StreamingText text={streamText} streaming={streaming} />
        ) : null}
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 text-xs text-muted-foreground">
      <Circle className="h-3 w-3" />
      Waiting for plan to complete…
    </div>
  );
}

function ToolCallList({ calls }: { calls: ToolCallEntry[] }) {
  return (
    <ul className="space-y-1.5">
      {calls.map((call) => (
        <li
          key={call.id}
          className="rounded-md border border-executor/30 bg-executor/5 px-3 py-2 text-xs"
        >
          <div className="flex items-center gap-2 font-medium text-executor">
            <Terminal className="h-3 w-3" />
            {call.tool}
            {typeof call.duration_ms === "number" ? (
              <span className="ml-auto text-[10px] font-normal text-muted-foreground">
                {call.duration_ms}ms
              </span>
            ) : null}
          </div>
          <p className="mt-1 truncate font-mono text-[11px] text-muted-foreground">
            {call.input}
          </p>
          {call.output_preview ? (
            <p className="mt-1 line-clamp-2 text-[11px] text-foreground/80">
              {call.output_preview}
            </p>
          ) : null}
        </li>
      ))}
    </ul>
  );
}
