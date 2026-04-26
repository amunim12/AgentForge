import { TaskForm } from "@/components/tasks/TaskForm";

export default function NewTaskPage() {
  return (
    <div className="mx-auto max-w-3xl px-6 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">New task</h1>
        <p className="text-sm text-muted-foreground">
          The Planner will receive your description, decompose it, and trigger the pipeline.
        </p>
      </div>
      <TaskForm />
    </div>
  );
}
