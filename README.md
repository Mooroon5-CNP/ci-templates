# ci-templates

Reusable GitLab CI/CD pipeline template for the internal developer platform.
Applications include this template once and get a full secure pipeline with no
copy-paste.

## Pipeline overview

```
scan-secrets ──► build ──► scan-image ──► update-config-dev   (main branch, auto)
                              │                └─► update-config-prod  (prod branch, manual)
                              └──► cleanup-on-scan-failure     (on_failure)
```

| Stage | Job | What it does |
|---|---|---|
| `scan-secrets` | `scan-secrets` | Gitleaks scans source code for leaked credentials |
| `build` | `build` | BuildKit rootless builds and pushes image to GitLab Container Registry |
| `scan-image` | `scan-image` | Trivy pulls the image from the registry and checks for CVEs |
| `scan-image` | `cleanup-on-scan-failure` | Deletes the pushed image tag if Trivy finds a blocking vulnerability |
| `update-config` | `update-config-dev` | Updates `newTag` in `overlays/dev/kustomization.yaml` (auto, main) |
| `update-config` | `update-config-prod` | Updates `newTag` in `overlays/prod/kustomization.yaml` (manual gate, prod) |

## Usage

In your application repository's `.gitlab-ci.yml`:

```yaml
include:
  - project: 'platform/ci-templates'
    ref: main
    file: 'pipeline.yml'

workflow:
  rules:
    - if: '$CI_COMMIT_BRANCH == "main"'
    - if: '$CI_COMMIT_BRANCH == "prod"'
```

### Inputs

| Input | Type | Default | Description |
|---|---|---|---|
| `app_name` | string | **required** | Application name; used as the image repository name and Kustomize overlay path |
| `app_port` | string | `"8080"` | Port the container exposes |
| `config_repo_url` | string | **required** | HTTPS URL of the ArgoCD config repo |
| `trivy_severity` | string | `"CRITICAL"` | Comma-separated Trivy severity levels that block the pipeline |

### Example with all inputs

```yaml
include:
  - project: 'platform/ci-templates'
    ref: main
    file: 'pipeline.yml'
    inputs:
      app_name: my-service
      app_port: "3000"
      config_repo_url: https://gitlab.example.com/platform/k8s-config.git
      trivy_severity: "HIGH,CRITICAL"
```

## Required CI/CD variables

Set these in **Settings → CI/CD → Variables** on each consuming project (or at
the group level to share them across projects).

| Variable | Scope | Masked | Description |
|---|---|---|---|
| `CI_REGISTRY_USER` | All | No | GitLab Container Registry username (usually `$CI_REGISTRY_USER` is auto-injected) |
| `CI_REGISTRY_PASSWORD` | All | Yes | Registry password / deploy token |
| `CONFIG_REPO_TOKEN` | All | Yes | Project/Personal Access Token with `write_repository` scope on the config repo |

`CI_REGISTRY`, `CI_REGISTRY_IMAGE`, `CI_PROJECT_ID`, `CI_JOB_TOKEN`, and
`CI_COMMIT_SHORT_SHA` are predefined GitLab variables injected automatically.

## Runner requirements

The `build` job carries a `tags: [dind]` label. The runner behind that tag must:

- Run in **shell** or **docker** executor mode (not privileged)
- Have **user namespaces** enabled (`/proc/sys/kernel/unprivileged_userns_clone = 1` on older kernels)
- Have **overlayfs** available for the OCI worker

If your runners do not support user namespaces, set
`BUILDKITD_FLAGS: --oci-worker-no-process-sandbox --oci-worker-snapshotter=native`
in the job variables.

## Config repo layout expected by update-config jobs

```
k8s-config/
  apps/
    <app_name>/
      overlays/
        dev/
          kustomization.yaml    # must contain a `newTag:` line
        prod/
          kustomization.yaml    # must contain a `newTag:` line
```

Minimal `kustomization.yaml`:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ../../base
images:
  - name: registry.gitlab.example.com/platform/my-service
    newTag: placeholder
```

## Security design decisions

- **No DinD / no privileged runners** — BuildKit rootless runs in an unprivileged container.
- **Image is pushed before scanning** — BuildKit has no tar-export mode without a daemon; Trivy pulls from the registry instead. The `cleanup-on-scan-failure` job removes the image if the scan blocks.
- **Secrets scanned before build** — Gitleaks runs in `scan-secrets` stage so a leaked credential never reaches the registry.
- **Short SHA tagging only** — `latest` is never pushed; every image is pinned to a commit.
- **CONFIG_REPO_TOKEN is masked** — it is injected into the clone URL at runtime and never stored on disk.

## Repository structure

```
ci-templates/
  pipeline.yml                  # Entry point; include this in application repos
  templates/
    .build.yml                  # BuildKit rootless build job template
    .scan-secrets.yml           # Gitleaks secret scan job template
    .scan-image.yml             # Trivy image scan job template
    .cleanup.yml                # Registry cleanup on scan failure
    .update-config.yml          # Kustomize GitOps promotion jobs
  README.md
```
