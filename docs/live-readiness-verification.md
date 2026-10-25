# Live readiness verification — 25 October 2026

These observations are read-only checks of the existing `app4-pixelcam` service
in project `cnp-terraform-512313`, region `europe-west9`. They validate the live
baseline and the portal readiness reader; they are not an end-to-end deployment
of the new dev/prod feature. No production candidate was created or approved.

## Cloud Run and HTTP

`gcloud run services describe app4-pixelcam` reports:

- `Ready`, `ConfigurationsReady`, and `RoutesReady`: `True`.
- Image:
  `europe-west9-docker.pkg.dev/cnp-terraform-512313/cnp-registry/app4-pixelcam:5f5e23b91b837585f477c7faaa998c5e260ddd84`.
- Ready revision: `app4-pixelcam-00002-99s`, receiving 100% of traffic.
- Public URI: `https://app4-pixelcam-aikxfqelhq-od.a.run.app`.
- Ingress: `INGRESS_TRAFFIC_ALL`; `defaultUriDisabled` is unset.
- IAM includes `allUsers` with `roles/run.invoker`.

Public GET requests returned:

| Path | Result |
|---|---|
| `/` | HTTP 200, HTML title `Pixel Calm` |
| `/ready` | HTTP 200, `{"status":"ready"}` |
| `/healthz` | HTTP 404 with Google's generic not-found page, reproduced twice |

The alternate API-advertised URI
`https://app4-pixelcam-648441306255.europe-west9.run.app/healthz` also returned
HTTP 404. The application is reachable at its root and readiness endpoint. The
`/healthz` response is an unresolved path-specific observation; this check does
not identify its cause or claim that all application endpoints are healthy.

## Crossplane observation shape

The existing `V2Service` resource has managed `Ready=True`, `Synced=True`, and
`LastAsyncOperation=True` conditions. Its observed GCP state uses this shape:

```json
{
  "terminalCondition": [
    {"type": "Ready", "state": "CONDITION_SUCCEEDED"}
  ],
  "conditions": [
    {"type": "RoutesReady", "state": "CONDITION_SUCCEEDED"},
    {"type": "ConfigurationsReady", "state": "CONDITION_SUCCEEDED"}
  ],
  "generation": "2",
  "observedGeneration": "2",
  "reconciling": false,
  "template": {
    "containers": [{"image": "registry/app4-pixelcam:5f5e23b91b837585f477c7faaa998c5e260ddd84"}]
  }
}
```

The image above is abbreviated only in this schema example. The full observed
image matches the Cloud Run image recorded earlier. `latestCreatedRevision`
equals `latestReadyRevision`. `terminalCondition` is an array in this provider;
there is no `Ready` entry in the separate observed `conditions` array. Generation
values are strings and must be compared numerically.

The new portal implementation's `getV2ServiceStatus('app4-pixelcam')` was then
called against this live resource and returned `ready: true`, the expected image
and URI, and `failure: null`. No access token or secret is included here.

## Application ownership and rollout prerequisites

A subsequent read-only Argo CD API inspection found:

| Object | Active configuration |
|---|---|
| ApplicationSet `cloudrun-autodiscovery` | The only active ApplicationSet; scans `apps/*/crossplane`, generates `{{path[1]}}-cloudrun`, uses project `default` |
| AppProjects | Only `default` and `platform` are present |
| Legacy generated Applications | `app4-pixelcam-cloudrun`, `cnp-test-node-cloudrun`, `cnp-test-python-cloudrun`, `cnp-test-fullstack-cloudrun`, `exemple-app-cnp-cloudrun` |

The repository already contains canonical definitions for
`crossplane-autodiscovery-dev` / `crossplane-autodiscovery-prod` and
`team-cnp-dev` / `team-cnp-prod`, but they were not active in the inspected
cluster. The canonical sets generate `<app>-dev` and `<app>-prod` respectively.
These projects are platform rollout prerequisites. A portal preflight should
report their absence; it must not silently use the unrestricted `default`
project for production.

The legacy directory scanner also sees an environment-only parent directory
such as `apps/new-app/crossplane` when only its `dev/` child has manifests.
Creating a second environment scanner with different Application names would
therefore require explicit ownership handling. New code should reuse the
canonical environment sets and preserve all existing legacy resources.

An offline check of replacing legacy directory discovery with root
`kustomization.yaml` file discovery found that this would remove
`exemple-app-cnp-cloudrun` from generated membership: its current Git parent has
only `README-aws.md` plus nested dev/prod files. That migration is not safe to
apply blindly because deleting the generated Application may cascade to cloud
resources. No discovery configuration was changed during verification.

The [Argo CD Git generator documentation](https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/Generators-Git/)
supports file-based discovery, but membership and resource deletion behavior
must be assessed against the actual repository before adopting it.

## Companion workflow checks

- Six workflow contract tests pass, including the default legacy promotion
  matrix, failed-scan behavior, and rejection of all GitOps writes in portal or
  invalid modes.
- `yamllint` passes, with one pre-existing long-line warning.
- `actionlint` passes.
- The feature branch is based on `c1eb7c3`, retaining the newer AWS account fix.
