# ci-templates — GitLab CI Pipeline for Node.js/Express Apps (CNP)

This repo contains the reusable CI pipeline for the CNP internal platform.
**Include it once in your application repo and get a full secure pipeline — no copy-pasting.**

A working example app you can use to test the pipeline end-to-end lives in [test_app/](test_app/).

---

## Table of contents

1. [What does this pipeline do?](#1-what-does-this-pipeline-do)
2. [Required setup checklist](#2-required-setup-checklist)
3. [How to use it in your app](#3-how-to-use-it-in-your-app)
4. [CI/CD variables you must configure](#4-cicd-variables-you-must-configure)
5. [What each stage checks](#5-what-each-stage-checks)
6. [What your project must have](#6-what-your-project-must-have)
7. [How deployment works](#7-how-deployment-works)
8. [Runner requirements](#8-runner-requirements)
9. [GitOps config repo structure](#9-gitops-config-repo-structure)
10. [FAQ — Common issues](#10-faq--common-issues)

---

## 1. What does this pipeline do?

Every push to `main` or `prod` triggers an automated sequence of checks:

```
main or prod
     │
     ▼
┌─────────┐   ┌──────┐   ┌────────────┐   ┌───────┐   ┌──────────────────────────────┐
│  lint   │──▶│ test │──▶│ scan-secu  │──▶│ build │──▶│            push              │
│         │   │      │   │            │   │       │   │                              │
│ ESLint  │   │ npm  │   │ Gitleaks   │   │Docker │   │ Trivy (image scan)           │
│ Hadolint│   │ test │   │ Trivy (fs) │   │ image │   │ GitOps update (ArgoCD picks  │
└─────────┘   └──────┘   └────────────┘   └───────┘   │ up the new tag and deploys)  │
                                                        └──────────────────────────────┘
```

If any stage fails, everything after it is skipped.
If the image scan fails, the image is automatically deleted from the registry.

---

## 2. Required setup checklist

Before the pipeline can run on a new app, four things must exist.

| # | What | Who | When |
|---|---|---|---|
| 1 | `CONFIG_REPO_TOKEN` CI/CD variable | App team lead or admin | Once per app repo |
| 2 | No runner setup needed — the pipeline uses Kaniko by default | — | Nothing to do |
| 3 | `prod` branch created and protected in your app repo | App team lead | Once per app repo |
| 4 | Kustomize overlay structure in the GitOps config repo | Platform/infra team | Once per app |

---

### 1 — `CONFIG_REPO_TOKEN`

The pipeline pushes the new image tag to the GitOps config repo after each build. It needs a token with write access to do that. Developers never see the token — it is stored encrypted in GitLab and injected automatically at runtime.

**Who sets this up:** a team lead or GitLab admin, once, before the first push.

Steps:
1. Open the **GitOps config repo** on GitLab → **Settings → Access Tokens → Add new token**
   - Name: `ci-pipeline-bot`
   - Role: **Developer**
   - Scope: **`write_repository`**
   - Expiry: 1 year from today
2. **Copy the token value** — it is shown only once
3. Open your **app repo** → **Settings → CI/CD → Variables → Add variable**
   - Key: `CONFIG_REPO_TOKEN`
   - Value: the token you just copied
   - Masked: ✅ Yes
   - Protected: ✅ Yes

> **Tip:** if all your app repos are in the same GitLab group, set `CONFIG_REPO_TOKEN` at the **group level** once — every repo in the group inherits it automatically and you never have to repeat this step.

---

### 2 — Runners: nothing to do

The pipeline uses **Kaniko** to build Docker images. Kaniko runs entirely inside the container — it does not need a Docker daemon, privileged mode, or any special runner configuration. It works on EPITA's shared runners and any standard GitLab runner out of the box.

You do not need to install, configure, or tag any runner.

---

### 3 — `prod` branch

The pipeline only runs on `main` and `prod` branches. The `prod` branch must exist and be **protected** (requires a Merge Request — no direct push allowed).

```bash
# In your app repo, run once:
git checkout -b prod
git push origin prod
```

Then on GitLab: **Settings → Repository → Protected branches**
- Branch: `prod`
- Allowed to merge: Maintainers
- Allowed to push: No one

> Without this, pushing to `prod` will either be blocked or won't trigger the production pipeline.

---

### 4 — Kustomize structure in the GitOps config repo

The pipeline updates image tags in the `k8s-config` repo. That repo must contain this directory structure for each app (created once by the platform team):

```
k8s-config/
  apps/
    <app_name>/            ← must match your app_name input exactly
      overlays/
        dev/
          kustomization.yaml
        prod/
          kustomization.yaml
```

Each `kustomization.yaml` must contain a `newTag:` line (the pipeline replaces it automatically). Full template: [section 9](#9-gitops-config-repo-structure).

---

### Step 1 — Copy the configuration file

In **your application repo**, create `.gitlab-ci.yml` at the root.
Copy the content from [example-app/.gitlab-ci.yml](example-app/.gitlab-ci.yml) and fill in the two values below.

```yaml
workflow:
  rules:
    - if: '$CI_COMMIT_BRANCH == "main"'
    - if: '$CI_COMMIT_BRANCH == "prod"'

include:
  - project: 'my_project/ci-templates' # Change this
    ref: main                  # pin to a release tag in production: ref: v1.0.0
    file: 'pipeline.yml'
    inputs:
      app_name: "my-app"                   # ← CHANGE THIS
      app_port: "8080"                     # ← port your app listens on
      config_repo_url: "https://gitlab.example.com/platform/k8s-config.git"  # ← CHANGE THIS
```

### Step 2 — Fill in the inputs

| Field | What to put |
|---|---|
| `app_name` | Your app name. Must match the directory in `k8s-config/apps/<app_name>/` |
| `app_port` | The port your app listens on (same as `EXPOSE` in your Dockerfile) |
| `config_repo_url` | The HTTPS URL of the GitOps repo watched by ArgoCD |

### Step 3 — Set CI/CD variables in GitLab

→ See [section 4](#4-cicd-variables-you-must-configure)

### Step 4 — Make sure your project meets the requirements

→ See [section 6](#6-what-your-project-must-have)

### Step 5 — Push and watch

Push to `main`. In GitLab go to your project → **CI/CD → Pipelines** to see it run.

---

## 4. CI/CD variables you must configure

> **Who does this?** A team lead or GitLab admin does this **once per application repo**, before the first pipeline run. Individual developers never need to touch tokens or variables.

### Variables to add to your application repo

Your app repo → **Settings** → **CI/CD** → **Variables** → **Add variable**

| Variable | Masked | Protected | Value |
|---|---|---|---|
| `CONFIG_REPO_TOKEN` | ✅ Yes | ✅ Yes | The token created in step below — lets the pipeline push the new image tag to the GitOps config repo |

> **These variables are injected automatically by GitLab — nothing to do:**
> `CI_REGISTRY`, `CI_REGISTRY_USER`, `CI_REGISTRY_IMAGE`, `CI_REGISTRY_PASSWORD`,
> `CI_JOB_TOKEN`, `CI_PROJECT_ID`, `CI_COMMIT_SHORT_SHA`

### How to create the token (admin, one-time)

This token authorizes the pipeline to write to the **GitOps config repo** (the repo that holds your Kubernetes manifests, not your app code).

1. Open the **GitOps config repo** on GitLab
2. **Settings** → **Access Tokens** → **Add new token**
3. Name: `ci-pipeline-bot` (just a label so you can identify it later)
4. Description: `Used by CI pipeline to update kustomization image tags`
5. Expiry: 1 year from today
6. Role: **Developer**
7. Scope: **`write_repository`** only
8. Click **Create project access token**
9. **Copy the token value** — it is shown only once
10. Go to your **application repo** → Settings → CI/CD → Variables → add `CONFIG_REPO_TOKEN` with that value

---

## 5. What each stage checks

### `lint` — Code quality

| Job | What it does | Blocks on |
|---|---|---|
| `lint-eslint` | Runs `npm run lint` on your JS source | Any ESLint error |
| `lint-hadolint` | Analyzes your `Dockerfile` for best-practice violations | Any Hadolint error |

### `test` — Automated tests

| Job | What it does | Blocks on |
|---|---|---|
| `test` | Runs `npm test` | Any test failure |

JUnit XML reports (`test-results.xml`) are uploaded as artifacts and displayed inline on MRs when present.

### `scan-secu` — Security before the build

| Job | Tool | Blocks on |
|---|---|---|
| `scan-secrets` | Gitleaks | Any committed secret found in git history |
| `scan-deps` | Trivy (filesystem) | CRITICAL CVE in npm deps — HIGH/MEDIUM is a warning only |

### `build` — Docker image

| Job | What it does |
|---|---|
| `build` | Builds the Docker image with BuildKit (rootless, no DinD) and pushes it to the GitLab Container Registry tagged with the commit SHA |

The image is **never tagged `latest`** — always a short commit SHA (e.g. `a1b2c3d4`).

### `push` — Image scan + deployment

| Job | What it does | Blocks on |
|---|---|---|
| `scan-image` | Trivy scans the built image | CRITICAL CVE in the image |
| `cleanup-on-scan-failure` | Deletes the image from the registry if `scan-image` fails | — |
| `update-config-dev` | Updates `newTag` in `overlays/dev/kustomization.yaml` — ArgoCD deploys to dev | Only runs on `main`, automatic |
| `update-config-prod` | Updates `newTag` in `overlays/prod/kustomization.yaml` | Only runs on `prod`, **manual click required** |

---

## 6. What your project must have

### Required files at the root

```
my-app/
├── Dockerfile              ← required
├── package.json            ← must have "lint" and "test" scripts
├── package-lock.json       ← required (the pipeline uses npm ci)
└── .gitlab-ci.yml          ← the file you copied from example-app/
```

### `package.json` — required scripts

```json
{
  "scripts": {
    "lint": "eslint src --ext .js",
    "test": "jest --forceExit"
  },
  "devDependencies": {
    "eslint": "^8.0.0",
    "jest": "^29.0.0"
  }
}
```

> Don't have ESLint yet?
> ```bash
> npm install --save-dev eslint
> npx eslint --init
> ```

### `Dockerfile` — CNP requirements

Your Dockerfile **must**:
- Use `node:20-alpine` as the base image (not `ubuntu`, not `node:latest`)
- `EXPOSE` the same port as `app_port`
- Run as a non-root user

Minimal compliant example:

```dockerfile
FROM node:20-alpine

WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production

COPY src/ ./src/

RUN adduser -D appuser
USER appuser

EXPOSE 8080
CMD ["node", "src/index.js"]
```

### Healthcheck endpoints — required by CNP contracts

Your Express app **must** expose these two routes:

```javascript
// Kubernetes checks this to know the pod is alive
app.get('/healthz', (req, res) => res.sendStatus(200));

// Kubernetes checks this before sending traffic to the pod
app.get('/ready', (req, res) => res.sendStatus(200));
```

---

## 7. How deployment works

### Deploy to dev (automatic)

```
1. git checkout main
2. git merge my-feature-branch
3. git push origin main
         ↓
   GitLab pipeline starts automatically
         ↓
   All stages pass → update-config-dev updates overlays/dev/
         ↓
   ArgoCD detects the change → syncs the dev cluster
```

### Deploy to prod (manual)

```
1. Open a Merge Request: main → prod on GitLab
2. Get it approved and merged
         ↓
   GitLab pipeline starts on the prod branch
         ↓
   lint / test / scan-secu / build / scan-image all run automatically
         ↓
   update-config-prod WAITS for a human to click Run
         ↓
   GitLab → CI/CD → Pipelines → click the job → click ▶ Run
         ↓
   ArgoCD syncs the prod cluster
```

---

## 8. Runner requirements

The pipeline uses **Kaniko** by default. Kaniko builds Docker images entirely inside the container, without a Docker daemon or any special kernel permissions. It works on EPITA's shared runners and any standard GitLab runner — no configuration needed.

The error `operation not permitted` / `failed to start the child` means a previous version of the pipeline was using BuildKit rootless, which requires user namespaces. Kaniko does not have this requirement. If you see that error, make sure you are on the latest version of this template (`ref: main`).

---

## 9. GitOps config repo structure

The config repo (watched by ArgoCD) must have this layout:

```
k8s-config/
  apps/
    <app_name>/           ← must match your app_name input exactly
      overlays/
        dev/
          kustomization.yaml    ← must contain a "newTag:" line
        prod/
          kustomization.yaml    ← must contain a "newTag:" line
```

Minimal `kustomization.yaml`:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ../../base
images:
  - name: registry.gitlab.example.com/my-org/my-app
    newTag: placeholder      # ← the pipeline replaces this value
```

---

## 10. FAQ — Common issues

**`lint-eslint` fails: "Cannot find module 'eslint'"**

ESLint is not in your `devDependencies`. Add it:
```bash
npm install --save-dev eslint
npx eslint --init
git add package.json package-lock.json .eslintrc.js
git commit -m "chore: add eslint"
```

---

**`lint-eslint` fails: "Missing script: lint"**

Your `package.json` has no `lint` script. Add:
```json
"scripts": {
  "lint": "eslint src --ext .js"
}
```

---

**`build` fails: "operation not permitted" / "failed to start the child"**

This was the BuildKit rootless error. Make sure your `.gitlab-ci.yml` uses `ref: main` (the latest template) — the pipeline now uses Kaniko by default and this error no longer occurs.

---

**`scan-image` fails and the image is deleted — what do I do?**

Trivy found a CRITICAL CVE. The full report is in the job artifacts (`trivy-report.txt`).

Next steps:
1. Update the vulnerable npm package: `npm update <package-name>`
2. If the CVE comes from the Alpine base image, try `FROM node:20-alpine` — Alpine releases security patches quickly

---

**`update-config-dev` fails: "required variable CONFIG_REPO_TOKEN is not set"**

The `CONFIG_REPO_TOKEN` variable is not configured. See [section 4](#4-cicd-variables-you-must-configure).

---

**I want to pin the template version to avoid breaking changes**

Replace `ref: main` with a specific tag:
```yaml
include:
  - project: 'nazim.lameche/ci-templates'
    ref: v1.0.0    # ← pin to a specific release
    file: 'pipeline.yml'
```

---

## Repository structure

```
ci-templates/
  pipeline.yml                   # Entry point — include this in your app repos
  templates/
    .lint.yml                    # ESLint + Hadolint
    .test.yml                    # npm test
    .scan-secu.yml               # Gitleaks + Trivy filesystem
    .build.yml                   # BuildKit rootless build
    .scan-image.yml              # Trivy image scan
    .cleanup.yml                 # Registry cleanup on scan failure
    .update-config.yml           # GitOps promotion (dev auto, prod manual)
  example-app/
    .gitlab-ci.yml               # Copy this into your app repo
  test_app/                      # Working example app — use it to test the pipeline
  .gitlab-ci.yml                 # Self-validation of this repo
  README.md                      # This file
```
