FROM node:22.23.4-bookworm-slim AS dependencies
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

FROM dependencies AS builder
ARG INCIDENT_COPILOT_BACKEND_ORIGIN=http://app:8000
ENV INCIDENT_COPILOT_BACKEND_ORIGIN=$INCIDENT_COPILOT_BACKEND_ORIGIN \
    NEXT_TELEMETRY_DISABLED=1
COPY next.config.mjs tsconfig.json ./
COPY config ./config
COPY src ./src
COPY public ./public
RUN npm run build

FROM node:22.23.4-bookworm-slim AS runner
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3001 HOSTNAME=0.0.0.0
COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static
COPY --from=builder --chown=node:node /app/public ./public
USER node
EXPOSE 3001
CMD ["node", "server.js"]
