resource "aws_amplify_app" "this" {
  name         = var.name
  repository   = var.repository_url
  access_token = var.github_token

  platform = "WEB_COMPUTE"   # Next.js SSR

  # Amplify auto-detects Next.js 14, but we pin the build config so deploys
  # are deterministic and we can scope the build to the frontend/ subtree.
  build_spec = <<-YAML
    version: 1
    applications:
      - appRoot: frontend
        frontend:
          phases:
            preBuild:
              commands:
                - corepack enable
                - corepack prepare pnpm@9.4.0 --activate
                - pnpm install --frozen-lockfile
            build:
              commands:
                - pnpm build
          artifacts:
            baseDirectory: .next
            files:
              - "**/*"
          cache:
            paths:
              - node_modules/**/*
              - .next/cache/**/*
  YAML

  environment_variables = {
    NEXT_PUBLIC_API_URL = var.backend_api_url
    NEXT_PUBLIC_WS_URL  = var.backend_ws_url
    AMPLIFY_DIFF_DEPLOY = "false"
    AMPLIFY_MONOREPO_APP_ROOT = "frontend"
  }
}

resource "aws_amplify_branch" "main" {
  app_id      = aws_amplify_app.this.id
  branch_name = var.branch

  enable_auto_build = true
  framework         = "Next.js - SSR"
  stage             = "PRODUCTION"
}
