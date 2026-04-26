"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2, Sparkles } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import toast from "react-hot-toast";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api, extractErrorMessage } from "@/lib/api";
import { TASK_CATEGORIES } from "@/lib/constants";
import { cn } from "@/lib/utils";
import type { Task } from "@/types";

const schema = z.object({
  title: z.string().min(4, "Title must be at least 4 characters").max(200),
  description: z
    .string()
    .min(10, "Describe the task in at least 10 characters")
    .max(5000),
  category: z.string().optional(),
});

type FormValues = z.infer<typeof schema>;

const EXAMPLES = [
  "Research the 3 best open-source vector databases in 2026 with pros/cons",
  "Write and execute a Python script that fetches current BTC price and charts the last hour",
  "Summarize the latest papers on mixture-of-experts routing and list the open problems",
];

export function TaskForm() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { title: "", description: "", category: "" },
  });

  const selectedCategory = watch("category");

  const onSubmit = handleSubmit(async (values) => {
    setSubmitting(true);
    try {
      const payload = {
        title: values.title,
        description: values.description,
        category: values.category || null,
      };
      const { data } = await api.post<Task>("/api/tasks", payload);
      toast.success("Task created. Launching agents…");
      router.push(`/tasks/${data.id}`);
    } catch (err) {
      toast.error(extractErrorMessage(err, "Failed to create task"));
    } finally {
      setSubmitting(false);
    }
  });

  return (
    <form onSubmit={onSubmit}>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-brand-500" />
            Describe your task
          </CardTitle>
          <CardDescription>
            The Planner will break it down, the Executor will run it, and the Critic will judge.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="title">Title</Label>
            <Input
              id="title"
              placeholder="E.g., Compare Postgres vs. SQLite for an edge RAG workload"
              {...register("title")}
            />
            {errors.title ? (
              <p className="text-xs text-destructive">{errors.title.message}</p>
            ) : null}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              rows={6}
              placeholder="Be specific about the output you want. Include constraints, sources to use, format preferences, etc."
              {...register("description")}
            />
            {errors.description ? (
              <p className="text-xs text-destructive">{errors.description.message}</p>
            ) : null}
          </div>

          <div className="space-y-1.5">
            <Label>Category (optional)</Label>
            <div className="flex flex-wrap gap-2">
              {TASK_CATEGORIES.map((cat) => {
                const active = selectedCategory === cat;
                return (
                  <button
                    type="button"
                    key={cat}
                    onClick={() => setValue("category", active ? "" : cat)}
                    className={cn(
                      "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                      active
                        ? "border-brand-500 bg-brand-500/10 text-brand-600 dark:text-brand-400"
                        : "border-border text-muted-foreground hover:border-foreground/40 hover:text-foreground",
                    )}
                  >
                    {cat}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="rounded-md border border-border/50 bg-muted/30 p-3">
            <p className="text-xs font-medium text-muted-foreground">Examples</p>
            <ul className="mt-1.5 space-y-1">
              {EXAMPLES.map((ex) => (
                <li key={ex}>
                  <button
                    type="button"
                    onClick={() =>
                      setValue("description", ex, { shouldValidate: true })
                    }
                    className="text-left text-xs text-muted-foreground hover:text-foreground"
                  >
                    → {ex}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </CardContent>
        <CardFooter className="flex justify-end">
          <Button type="submit" variant="brand" disabled={submitting}>
            {submitting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Creating…
              </>
            ) : (
              <>
                <Sparkles className="mr-2 h-4 w-4" />
                Launch agents
              </>
            )}
          </Button>
        </CardFooter>
      </Card>
    </form>
  );
}
