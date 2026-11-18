FROM node:20-alpine
WORKDIR /app
COPY package.json package-lock.json ./
# npm is only needed to install dependencies. It is removed right after, so
# the final image doesn't ship it: the npm bundled in node:20-alpine carries a
# vulnerable tar (CVE-2026-59873) that fails the pipeline's scan-image job,
# and the container never uses npm at runtime (CMD runs node directly).
RUN npm ci --omit=dev \
  && rm -rf /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/corepack \
            /usr/local/bin/npm /usr/local/bin/npx /usr/local/bin/corepack \
            /opt/yarn-* /usr/local/bin/yarn /usr/local/bin/yarnpkg
COPY src/ ./src/
USER 1000
EXPOSE {{APP_PORT}}
ENV PORT={{APP_PORT}}
HEALTHCHECK --interval=30s --timeout=5s CMD ["wget", "-qO-", "http://localhost:{{APP_PORT}}/healthz"]
CMD ["node", "src/index.js"]
