"use client";

import { useEffect, useRef } from "react";

import { cn } from "@/lib/utils";

interface StreamingTextProps {
  text: string;
  streaming?: boolean;
  className?: string;
  autoScroll?: boolean;
}

export function StreamingText({
  text,
  streaming = false,
  className,
  autoScroll = true,
}: StreamingTextProps) {
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (autoScroll && ref.current) {
      ref.current.scrollTop = ref.current.scrollHeight;
    }
  }, [text, autoScroll]);

  return (
    <div
      ref={ref}
      className={cn(
        "max-h-80 overflow-y-auto whitespace-pre-wrap rounded-md bg-muted/40 p-3 font-mono text-xs leading-relaxed text-foreground/90",
        className,
      )}
    >
      {text || (streaming ? "" : <span className="text-muted-foreground">Waiting…</span>)}
      {streaming && <span className="streaming-cursor" aria-hidden />}
    </div>
  );
}
