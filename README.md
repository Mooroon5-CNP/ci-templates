# ci-templates — GitLab CI Pipeline for Node.js/Express Apps (CNP)

This repo contains the reusable CI pipeline for the CNP internal platform.
**Include it once in your application repo and get a full secure pipeline — no copy-pasting.**

A working example app you can use to test the pipeline end-to-end lives in [test_app/](test_app/).

---

## Table of contents

1. [What does this pipeline do?](#1-what-does-this-pipeline-do)
2. [How to use it in your app](#2-how-to-use-it-in-your-app)
3. [CI/CD variables you must configure](#3-cicd-variables-you-must-configure)
4. [What each stage checks](#4-what-each-stage-checks)
5. [What your project must have](#5-what-your-project-must-have)
6. [How deployment works](#6-how-deployment-works)
7. [Runner requirements](#7-runner-requirements)
8. [GitOps config repo structure](#8-gitops-config-repo-structure)
9. [FAQ — Common issues](#9-faq--common-issues)

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

## 2. How to use it in your app

### Step 1 — Copy the configuration file

In **your application repo**, create `.gitlab-ci.yml` at the root.
Copy the content from [example-app/.gitlab-ci.yml](example-app/.gitlab-ci.yml) and fill in the two values below.

```yaml
workflow:
  rules:
    - if: '$CI_COMMIT_BRANCH == "main"'
    - if: '$CI_COMMIT_BRANCH == "prod"'

include:
  - project: 'nazim.lameche/ci-templates'
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

→ See [section 3](#3-cicd-variables-you-must-configure)

### Step 4 — Make sure your project meets the requirements

→ See [section 5](#5-what-your-project-must-have)

### Step 5 — Push and watch

Push to `main`. In GitLab go to your project → **CI/CD → Pipelines** to see it run.

---

## 3. CI/CD variables you must configure

**How to add a variable in GitLab:**
Your project → **Settings** → **CI/CD** → **Variables** → **Add variable**

| Variable | Masked | Protected | Description |
|---|---|---|---|
| `CONFIG_REPO_TOKEN` | ✅ Yes | ✅ Yes | GitLab token with `write_repository` scope on the GitOps config repo. Lets the pipeline push the new image tag so ArgoCD picks it up. |
| `CI_REGISTRY_PASSWORD` | ✅ Yes | No | GitLab Container Registry password. **Auto-injected by GitLab in most cases** — only set this manually if you use an external registry. |

> **These variables are injected automatically by GitLab (nothing to do):**
> `CI_REGISTRY`, `CI_REGISTRY_USER`, `CI_REGISTRY_IMAGE`, `CI_PROJECT_ID`,
> `CI_JOB_TOKEN`, `CI_COMMIT_SHORT_SHA`

### How to create CONFIG_REPO_TOKEN

1. Go to GitLab, open the **GitOps config repo** (not your app repo)
2. **Settings** → **Access Tokens** → **Add new token**
3. Name: `ci-pipeline-bot`
4. Expiry: pick a date (e.g. 1 year from now)
5. Scope: check **`write_repository`** only
6. Click **Create project access token**
7. **Copy the token shown** — it is only visible once!
8. Go to **your application repo** → Settings → CI/CD → Variables → add `CONFIG_REPO_TOKEN`

---

## 4. What each stage checks

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

## 5. What your project must have

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

## 6. How deployment works

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

## 7. Runner requirements

The `build` job requires a runner tagged `dind` configured for BuildKit rootless.

**Runner prerequisites:**
- User namespaces enabled: `/proc/sys/kernel/unprivileged_userns_clone = 1`
- Overlayfs available for the OCI worker

If user namespaces are not available on your runner, override the variable in
your app's `.gitlab-ci.yml`:

```yaml
build:
  extends: .build
  variables:
    BUILDKITD_FLAGS: "--oci-worker-no-process-sandbox --oci-worker-snapshotter=native"
```

---

## 8. GitOps config repo structure

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

## 9. FAQ — Common issues

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

**`build` fails: "user namespaces not enabled"**

The runner doesn't have user namespaces. See [section 7](#7-runner-requirements).

---

**`scan-image` fails and the image is deleted — what do I do?**

Trivy found a CRITICAL CVE. The full report is in the job artifacts (`trivy-report.txt`).

Next steps:
1. Update the vulnerable npm package: `npm update <package-name>`
2. If the CVE comes from the Alpine base image, try `FROM node:20-alpine` — Alpine releases security patches quickly

---

**`update-config-dev` fails: "required variable CONFIG_REPO_TOKEN is not set"**

The `CONFIG_REPO_TOKEN` variable is not configured. See [section 3](#3-cicd-variables-you-must-configure).

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
