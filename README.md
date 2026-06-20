# ci-templates — GitHub Actions Pipeline for CNP Apps

Reusable CI/CD pipeline (`workflow_call`) for all CNP application repositories.
Reference it once in your app repo and get a full secure pipeline — linting, testing, security scans, multi-cloud image push, and GitOps promotion.

---

## Table of contents

1. [What the pipeline does](#1-what-the-pipeline-does)
2. [How to use it in your app](#2-how-to-use-it-in-your-app)
3. [Inputs and secrets](#3-inputs-and-secrets)
4. [target_cloud — choosing your registry](#4-target_cloud--choosing-your-registry)
5. [Pipeline stages in order](#5-pipeline-stages-in-order)
6. [Multi-cloud image push](#6-multi-cloud-image-push)
7. [Keyless authentication](#7-keyless-authentication)
8. [GitOps promotion](#8-gitops-promotion)
9. [What your app must provide](#9-what-your-app-must-provide)
10. [FAQ](#10-faq)

---

## 1. What the pipeline does

Every push to `main` or `prod` runs:

```
lint (ESLint + Hadolint)  — parallel
         │
         ▼
       test (npm test)
         │
         ▼
scan-secrets (Gitleaks)   scan-deps (Trivy FS)  — parallel
         │                       │
         └──────────┬────────────┘
                    ▼
               build (Docker image → GCP AR and/or AWS ECR)
                    │
                    ▼
           scan-image (Trivy image scan)
                    │
          ┌─────────┼─────────────────────┐
          ▼         ▼                     ▼
  cleanup-on-  update-config-dev    update-config-prod
  scan-failure  (main, auto)         (prod, manual gate)
```

If any stage fails, everything after it is skipped.
If the image scan fails, the image is automatically deleted from the registry.

---

## 2. How to use it in your app

Create `.github/workflows/ci.yml` in your **application repo**:

```yaml
on:
  push:
    branches: [main, prod]

permissions:
  contents: read
  id-token: write   # required for keyless auth (GCP WIF and/or AWS OIDC)

jobs:
  pipeline:
    uses: Mooroon5-CNP/ci-templates/.github/workflows/pipeline.yml@main
    with:
      app_name: "my-app"
      app_port: "8080"
      target_cloud: "both"           # gcp | aws | both  (default: both)
      config_repo_url: "https://github.com/Mooroon5-CNP/config-repo"
    secrets:
      CONFIG_REPO_TOKEN: ${{ secrets.CONFIG_REPO_TOKEN }}
```

> The `permissions:` block **must** appear at the calling workflow level, not inside the job.
> `id-token: write` is required so the runner can obtain OIDC tokens for GCP WIF and AWS STS.

---

## 3. Inputs and secrets

### Inputs (`with:`)

| Input | Required | Default | Description |
|---|---|---|---|
| `app_name` | yes | — | App identifier. Used as the image name and the directory under `apps/` in config-repo |
| `app_port` | no | `"8080"` | Port the container listens on — passed as `APP_PORT` build-arg to Docker |
| `config_repo_url` | yes | — | HTTPS URL of the GitOps config repository |
| `target_cloud` | no | `"both"` | Registry target: `gcp`, `aws`, or `both` — see [section 4](#4-target_cloud--choosing-your-registry) |

### Secrets

| Secret | Required | Description |
|---|---|---|
| `CONFIG_REPO_TOKEN` | yes | PAT with `contents: write` on the GitOps config repo — lets the pipeline push new image tags |

**How to create `CONFIG_REPO_TOKEN`** (admin, one-time per org):

1. GitHub → **Settings → Developer settings → Personal access tokens → Fine-grained tokens**
2. Repository access: config-repo only — **Contents: Read and write**
3. Add the token to your app repo: **Settings → Secrets and variables → Actions → `CONFIG_REPO_TOKEN`**

> Tip: set it as an **organization secret** once and all app repos inherit it automatically.

---

## 4. `target_cloud` — choosing your registry

| Value | GCP Artifact Registry | AWS ECR | GKE update-config |
|---|---|---|---|
| `gcp` | push ✅ | skip | runs ✅ |
| `aws` | skip | push ✅ | **skipped** (AWS apps don't deploy to GKE) |
| `both` (default) | push ✅ | push ✅ | runs ✅ |

The image tag is always the full commit SHA (`${{ github.sha }}`).

---

## 5. Pipeline stages in order

### Stage 1 — Lint (parallel)

| Job | What it runs | Blocks on |
|---|---|---|
| `lint-eslint` | `npm ci` then `npm run lint` | Any ESLint error; also fails if `package-lock.json` is missing |
| `lint-hadolint` | `hadolint/hadolint:latest-alpine` on `Dockerfile` | Any Hadolint error |

### Stage 2 — Test

| Job | What it runs | Artifact |
|---|---|---|
| `test` | `npm ci` then `npm test` | `test-results.xml` (7-day retention, `if-no-files-found: ignore`) |

### Stage 3 — Security scans (parallel, after test)

| Job | Tool | Blocks on |
|---|---|---|
| `scan-secrets` | `zricethezav/gitleaks:latest` (full git history, `fetch-depth: 0`) | Any secret detected — report saved as `gitleaks-report.json` |
| `scan-deps` | `aquasec/trivy:latest fs` | **CRITICAL** CVEs in dependencies (blocking); HIGH/MEDIUM logged only |

### Stage 4 — Build

Job: **`build`** (needs: `scan-secrets`, `scan-deps`)

Steps in order:
1. Authenticate to GCP via Workload Identity Federation *(skipped if `target_cloud == aws`)*
2. `docker/setup-buildx-action@v3`
3. Docker login to Artifact Registry *(skipped if `target_cloud == aws`)*
4. Authenticate to AWS via OIDC *(skipped if `target_cloud == gcp`)*
5. ECR login + auto-create repo if it doesn't exist *(skipped if `target_cloud == gcp`)*
6. Compute image refs (sets `TAGS`, `IMAGE_REF`, `CACHE_REF`, `ECR_REF` in `$GITHUB_ENV`)
7. `docker/build-push-action@v5` — single build, pushes to all selected registries; uses GCP registry-backed layer cache when available

### Stage 5 — Image scan

Job: **`scan-image`** (needs: `build`)

- Authenticates to the relevant registry (same gating as build)
- Pulls the image from GCP AR (priority) or ECR (if `target_cloud == aws`)
- `aquasec/trivy:latest image` — **CRITICAL** blocking, HIGH/MEDIUM non-blocking
- Uploads `trivy-report.txt` (7-day retention)

### Stage 6 — Cleanup on scan failure

Job: **`cleanup-on-scan-failure`** — runs only when `scan-image` fails

- Deletes the vulnerable image from GCP Artifact Registry via `gcloud artifacts docker images delete` *(skipped if `target_cloud == aws`)*
- Deletes the vulnerable image from ECR via `aws ecr batch-delete-image` *(skipped if `target_cloud == gcp`)*

### Stage 7 — GitOps promotion

| Job | Trigger | Gate |
|---|---|---|
| `update-config-dev` | push to `main`, scan OK | `target_cloud != aws` |
| `update-config-prod` | push to `prod`, scan OK | `target_cloud != aws` + **manual approval** (`environment: production`) |

See [section 8](#8-gitops-promotion) for details.

---

## 6. Multi-cloud image push

### GCP Artifact Registry

```
europe-west9-docker.pkg.dev/cnp-terraform/cnp-registry/<app_name>:<sha>
```

Layer cache:
```
europe-west9-docker.pkg.dev/cnp-terraform/cnp-registry/cache:<app_name>
```

Active when `target_cloud` is `gcp` or `both`.

### AWS ECR (eu-west-3)

```
562346647831.dkr.ecr.eu-west-3.amazonaws.com/<app_name>:<sha>
```

Active when `target_cloud` is `aws` or `both`.
**The ECR repository is created automatically on first push** if it doesn't already exist.

### Single build, multiple registries

When `target_cloud: both`, a single `docker buildx build` run pushes to both registries simultaneously — no rebuild, one layer transfer.

---

## 7. Keyless authentication

No static credentials are stored anywhere. Both clouds use short-lived tokens obtained at runtime via GitHub's OIDC provider.

### GCP — Workload Identity Federation

```
Workload Identity Pool : projects/199851303237/locations/global/workloadIdentityPools/github-pool/providers/github-provider
Service Account        : github-ci-sa@cnp-terraform.iam.gserviceaccount.com
Action                 : google-github-actions/auth@v2
```

### AWS — OIDC / STS

```
Role ARN : arn:aws:iam::562346647831:role/github-ecr-push-role
Region   : eu-west-3
Action   : aws-actions/configure-aws-credentials@v4
```

The role trust policy is scoped to `repo:Mooroon5-CNP/*:*` — only repos in this org can assume it.

---

## 8. GitOps promotion

After a successful image scan on `main` (dev) or `prod` (prod), the pipeline clones the GitOps config repo and updates two files:

**`apps/<app_name>/overlays/{dev,prod}/kustomization.yaml`**
```yaml
# before
newTag: abc1234

# after (7-char short SHA)
newTag: 02a7f39
```

**`apps/<app_name>/crossplane/cloudrun-claim.yaml`** *(updated only if the file exists)*
```yaml
# image reference updated to the full SHA
image: europe-west9-docker.pkg.dev/cnp-terraform/cnp-registry/<app_name>:<full-sha>
```

The commit message is `chore(<app_name>): promote <sha> to {dev,prod} [ci skip]`.

**`update-config-dev` and `update-config-prod` are both skipped when `target_cloud: aws`** — apps that push only to ECR are not deployed to GKE.

Production promotion (`update-config-prod`) requires a manual approval in the GitHub **`production` environment** before it runs.

---

## 9. What your app must provide

### Required files

```
my-app/
├── Dockerfile              ← required, must be at repo root
├── package.json            ← must have "lint" and "test" scripts
├── package-lock.json       ← required (pipeline uses npm ci)
└── .github/workflows/ci.yml
```

### `package.json` scripts

```json
{
  "scripts": {
    "lint": "eslint src --ext .js",
    "test": "jest --forceExit"
  }
}
```

### Dockerfile requirements

- Accept `APP_PORT` as a build-arg (the pipeline injects it via `--build-arg APP_PORT=<app_port>`)
- Run as a non-root user

Minimal example:

```dockerfile
FROM node:20-alpine

ARG APP_PORT=8080
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY src/ ./src/

RUN adduser -D appuser
USER appuser

EXPOSE ${APP_PORT}
CMD ["node", "src/index.js"]
```

### Healthcheck endpoints (required by CNP Kubernetes manifests)

```javascript
app.get('/healthz', (req, res) => res.sendStatus(200));
app.get('/ready',  (req, res) => res.sendStatus(200));
```

### GitOps config-repo structure (for GCP/both apps)

```
config-repo/
  apps/
    <app_name>/              ← must match app_name input exactly
      overlays/
        dev/
          kustomization.yaml  ← must contain a "newTag:" line
        prod/
          kustomization.yaml  ← must contain a "newTag:" line
```

---

## 10. FAQ

**`lint-eslint` fails: "package-lock.json not found"**

Run `npm install` locally and commit the generated `package-lock.json`. The pipeline refuses to run without it to guarantee reproducible installs.

---

**`lint-eslint` fails: "eslint not found in node_modules"**

ESLint is not in `devDependencies`. Add it:
```bash
npm install --save-dev eslint
npx eslint --init
git add package.json package-lock.json
git commit -m "chore: add eslint"
```

---

**`scan-secrets` fails: "secret detected"**

Gitleaks found a secret in the git history. Check `gitleaks-report.json` in the job artifacts to identify what and where. Rotate the credential immediately, then use `git filter-repo` or BFG to remove it from history.

---

**`scan-image` fails and the image is deleted — what do I do?**

Download `trivy-report.txt` from the job artifacts. Find the CRITICAL CVE, update the affected package or bump the base image, then push again.

---

**`update-config-dev` fails: "CONFIG_REPO_TOKEN is not set"**

Add the `CONFIG_REPO_TOKEN` secret to your app repo — see [section 3](#3-inputs-and-secrets).

---

**My app is AWS-only but `update-config-dev` still ran**

Make sure `target_cloud: aws` is set in your `with:` block. The job condition is `target_cloud != 'aws'` — it skips automatically when the input is set correctly.

---

**How do I deploy to prod?**

1. Open a Pull Request: `main` → `prod`
2. Get it approved and merged
3. The pipeline starts automatically on the `prod` branch
4. After scan passes, GitHub pauses at `update-config-prod` and waits for manual approval
5. Go to **Actions → the run → Review deployments → Approve and deploy**
6. ArgoCD picks up the new tag and syncs the prod cluster
