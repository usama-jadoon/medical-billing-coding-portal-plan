FROM node:20-alpine AS builder

WORKDIR /app

RUN corepack enable && corepack prepare pnpm@latest --activate

COPY package.json pnpm-workspace.yaml ./
COPY packages/ ./packages/
COPY apps/web/ ./apps/web/

RUN pnpm --filter @medical-portal/web install --frozen-lockfile=false
RUN pnpm --filter @medical-portal/web build

FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production \
    PORT=3000

COPY --from=builder /app/apps/web/.next/standalone ./
COPY --from=builder /app/apps/web/.next/static ./.next/static
COPY --from=builder /app/apps/web/public ./public

EXPOSE 3000

CMD ["node", "server.js"]
