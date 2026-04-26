"use client";

import { LogOut } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { useAuth } from "@/providers/AuthProvider";
import { formatDateTime } from "@/lib/utils";

export default function SettingsPage() {
  const { user, logout } = useAuth();

  return (
    <div className="mx-auto max-w-3xl space-y-6 px-6 py-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
        <p className="text-sm text-muted-foreground">
          Account preferences and session management.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Profile</CardTitle>
          <CardDescription>Read-only for this build.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Field label="Username" value={user?.username ?? "—"} />
          <Field label="Email" value={user?.email ?? "—"} />
          <Field
            label="Account created"
            value={user?.created_at ? formatDateTime(user.created_at) : "—"}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Session</CardTitle>
          <CardDescription>Sign out from this device.</CardDescription>
        </CardHeader>
        <Separator />
        <CardContent className="pt-6">
          <Button variant="outline" onClick={logout}>
            <LogOut className="mr-2 h-4 w-4" />
            Sign out
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs text-muted-foreground">{label}</Label>
      <p className="text-sm">{value}</p>
    </div>
  );
}
