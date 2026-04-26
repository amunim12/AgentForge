// Backend-aligned TypeScript interfaces.

export type TaskStatus =
  | "pending"
  | "planning"
  | "executing"
  | "critiquing"
  | "completed"
  | "failed";

export type AgentStatus = "idle" | "running" | "done" | "error";

export type AgentName = "planner" | "executor" | "critic";

export interface User {
  id: string;
  email: string;
  username: string;
  is_active: boolean;
  created_at: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface PlanStep {
  step_id: number;
  title: string;
  description: string;
  tool: "web_search" | "code_executor" | "file_tool" | "reasoning" | "none";
  tool_input_hint: string;
  expected_output: string;
  dependencies: number[];
  critical: boolean;
}

export interface TaskPlan {
  task_summary: string;
  complexity: "low" | "medium" | "high";
  estimated_steps: number;
  steps: PlanStep[];
  success_criteria: string;
}

export interface ToolCall {
  type: "agent_tool_call";
  agent: "executor";
  tool: string;
  input: string;
  output_preview?: string;
  duration_ms?: number;
}

export interface ExecutorResult {
  formatted_output: string;
  steps_completed: number;
  tool_calls: ToolCall[];
  duration_ms?: number;
}

export interface RubricEntry {
  score: number;
  comment: string;
}

export interface CriticVerdict {
  score: number;
  rubric: {
    accuracy: RubricEntry;
    completeness: RubricEntry;
    clarity: RubricEntry;
    relevance: RubricEntry;
    depth: RubricEntry;
  };
  strengths: string[];
  improvements_needed: string[];
  specific_instructions_for_next_iteration: string;
  verdict: "accept" | "revise";
}

export interface TaskListItem {
  id: string;
  title: string;
  status: TaskStatus;
  category: string | null;
  critic_score: number | null;
  iteration_count: number;
  created_at: string;
  completed_at: string | null;
}

export interface Task {
  id: string;
  title: string;
  description: string;
  status: TaskStatus;
  category: string | null;
  planner_output: TaskPlan | null;
  executor_output: ExecutorResult | null;
  critic_output: CriticVerdict | null;
  final_result: string | null;
  iteration_count: number;
  critic_score: number | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

// ---------- WebSocket event envelope ----------
export type AgentEvent =
  | { type: "agent_start"; agent: AgentName }
  | { type: "agent_stream"; agent: AgentName; delta: string }
  | {
      type: "agent_tool_call";
      agent: "executor";
      tool: string;
      input: string;
      output_preview?: string;
      duration_ms?: number;
    }
  | { type: "agent_done"; agent: AgentName; output: Record<string, unknown> }
  | { type: "task_complete"; result: string; score: number }
  | { type: "task_failed"; error: string };
