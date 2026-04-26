import type { Metadata } from "next";
import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";
import { Toaster } from "react-hot-toast";

import { AuthProvider } from "@/providers/AuthProvider";
import { QueryProvider } from "@/providers/QueryProvider";
import { ThemeProvider } from "@/providers/ThemeProvider";

import "./globals.css";

export const metadata: Metadata = {
  title: "AgentForge — Multi-Agent AI Orchestration",
  description:
    "Enterprise-grade AI orchestration platform. Planner, Executor, and Critic agents collaborate to deliver high-quality structured results.",
  applicationName: "AgentForge",
  keywords: ["AI agents", "LangGraph", "multi-agent", "AI orchestration"],
  openGraph: {
    title: "AgentForge",
    description: "Multi-Agent AI Orchestration Platform",
    type: "website",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${GeistSans.variable} ${GeistMono.variable}`}
      suppressHydrationWarning
    >
      <body className="min-h-screen bg-background font-sans text-foreground antialiased">
        <ThemeProvider attribute="class" defaultTheme="dark" enableSystem>
          <QueryProvider>
            <AuthProvider>{children}</AuthProvider>
          </QueryProvider>
          <Toaster
            position="bottom-right"
            toastOptions={{
              className:
                "bg-card border border-border text-foreground rounded-md text-sm",
              duration: 4000,
            }}
          />
        </ThemeProvider>
      </body>
    </html>
  );
}
