"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { Task, TaskListItem } from "@/types";

interface ListParams {
  limit?: number;
  offset?: number;
  status?: string;
}

export function useTasks(params: ListParams = {}) {
  return useQuery({
    queryKey: ["tasks", params],
    queryFn: async () => {
      const { data } = await api.get<TaskListItem[]>("/api/tasks", { params });
      return data;
    },
  });
}

export function useTask(taskId: string | null | undefined) {
  return useQuery({
    queryKey: ["task", taskId],
    enabled: Boolean(taskId),
    queryFn: async () => {
      const { data } = await api.get<Task>(`/api/tasks/${taskId}`);
      return data;
    },
  });
}

export function useDeleteTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (taskId: string) => {
      await api.delete(`/api/tasks/${taskId}`);
      return taskId;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tasks"] });
    },
  });
}
