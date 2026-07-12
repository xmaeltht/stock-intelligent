# Stock Intelligence

A local-first Kubernetes foundation for an evidence-backed stock research application. The MVP is intentionally a modular monolith: one Next.js frontend, one FastAPI backend image, PostgreSQL, and a scheduled pipeline using that same backend image.

The current milestone establishes the deployable application boundary. It does **not** yet select stocks, ingest market data, or calculate fair value.

## What is included

- Next.js dashboard at `stock-intelligence.localhost`
- Same-origin `/api/health` proxy from Next.js to FastAPI
- FastAPI liveness, database-aware readiness, versioned health, and company-list endpoints
- SQLAlchemy `companies` model and initial Alembic migration
- PostgreSQL 17 StatefulSet with a 20 Gi local-path PVC
- 20 Gi market-data PVC for future Parquet/DuckDB datasets
- Daily weekday pipeline CronJob scaffold
- Helm chart with ConfigMap and Secret placeholder support
- `HTTPRoute` attached to a configurable existing Gateway
- Default-deny NetworkPolicies and component-specific service accounts
- Argo CD `Application` scaffold
- Local in-cluster Git source for fully offline Argo CD reconciliation
- Non-root containers, dropped capabilities, seccomp, probes, and resource limits

## Repository layout

```text
.
├── argocd/application.yaml
├── backend/
│   ├── app/                 # API, model, database, and pipeline modules
│   ├── migrations/          # Alembic migration history
│   ├── tests/
│   └── Dockerfile
├── charts/stock-intelligence/
│   ├── templates/
│   ├── values.yaml
│   └── values-local.yaml
├── frontend/
│   ├── app/                 # Dashboard and health proxy
│   └── Dockerfile
├── Makefile
└── .env.example
```

## Cluster inspection result

The live `docker-desktop` cluster was bootstrapped and verified on 2026-07-12 with:

- `standard` as the default storage class, backed by `rancher.io/local-path`
- Gateway API 1.6.0 standard-channel CRDs
- Istio 1.30.2 (`istio-base` and `istiod` Helm releases)
- an Istio-managed `istio-ingress/maelkloud-gateway` serving HTTP on port 80
- Argo CD 3.4.5 non-HA controllers and CRDs in `argocd`
- `kindnet` as the cluster CNI
- Kubernetes SIG Network's policy controller enforcing standard `NetworkPolicy` resources

The Gateway is programmed at a local LoadBalancer address and only accepts routes from namespaces labelled `gateway-access=maelkloud`. The chart uses that label and points its `HTTPRoute` to the `http` listener.

Policy enforcement was verified with a paired deny/allow probe against Argo CD Redis: an unlabeled client was blocked and an explicitly allowed client connected. The reusable test is stored in `platform/network-policy-probe.yaml`.

## Local application development

Requirements:

- Python 3.12+
- Node.js 22+
- npm

Install dependencies:

```bash
cp .env.example .env
make install
```

Run the backend and frontend in separate terminals:

```bash
make dev-backend
make dev-frontend
```

Open `http://localhost:3000`. The dashboard calls the backend through the frontend's `/api/health` route. This health call works without a database; `/health/ready`, migrations, the companies endpoint, and the pipeline require PostgreSQL.

Run all verification:

```bash
make validate
```

## Kubernetes platform

The cluster-level prerequisites are installed. Their pinned versions and local access instructions are documented in `platform/README.md`; the reusable Gateway resource is stored in `platform/gateway.yaml`.

Confirm platform health:

```bash
make cluster-check
kubectl get gateway -n istio-ingress
kubectl get pods -n istio-system
kubectl get pods -n argocd
```

The local values target `istio-ingress/maelkloud-gateway`. Open
`http://stock-intelligence.localhost` for zero-configuration local access.
The application does not claim or route any `maelkloud.com` hostname.

## Build and deploy with Helm

Docker Desktop Kubernetes can use locally built images without a registry after they are loaded into its kind cluster.

```bash
make build-images
make load-images
POSTGRES_PASSWORD='choose-a-local-password' make deploy-helm
```

The multi-node Docker Desktop cluster uses the kind provisioner. Building an
image on macOS does not automatically cache it on every Kubernetes node;
`make load-images` imports both application images into the `desktop` cluster.

If your Gateway has a different name or namespace:

```bash
POSTGRES_PASSWORD='choose-a-local-password' \
GATEWAY_NAME='your-gateway' \
GATEWAY_NAMESPACE='your-gateway-namespace' \
make deploy-helm
```

Inspect the rollout:

```bash
kubectl get pods,svc,pvc,cronjob,httproute -n stock-intelligence
kubectl describe httproute stock-intelligence -n stock-intelligence
```

Docker Desktop publishes the Gateway LoadBalancer on localhost port 80, so
`http://stock-intelligence.localhost` works without editing `/etc/hosts`. The current
foundation uses HTTP. Add cert-manager and a certificate before enabling an
HTTPS listener.

### Secrets

The default chart can render a placeholder Secret for first-time local testing. A deploy through the Makefile overrides the database password from `POSTGRES_PASSWORD`.

For GitOps, do not commit a real password into a values file. Create a Secret through your chosen local secret-management workflow with these keys:

```text
POSTGRES_USER
POSTGRES_PASSWORD
POSTGRES_DB
```

Then set:

```yaml
secrets:
  existingSecret: stock-intelligence-runtime
  createPlaceholder: false
```

## Deploy with Argo CD

Argo CD is installed and actively reconciles the application from a local,
read-only Git service in the `stock-intelligence` namespace. This removes the
need for GitHub credentials while keeping Git as Argo's source of truth.

Publish the current working tree and refresh Argo CD with:

```bash
make publish-local-git
```

The command packages source files, updates the internal Git snapshot, restarts
the small Git server, and reapplies the Argo CD `Application`. Argo renders
`charts/stock-intelligence` with `values-local.yaml` and reconciles it with
pruning and self-healing enabled.

Verify it with:

```bash
kubectl get application stock-intelligence -n argocd
```

Both `SYNC STATUS` and `HEALTH STATUS` should report `Synced` and `Healthy`.

## API and database foundation

Useful endpoints:

| Endpoint | Purpose |
|---|---|
| `GET /health/live` | Process liveness; no dependency checks |
| `GET /health/ready` | PostgreSQL connectivity readiness |
| `GET /api/v1/health` | Versioned frontend health contract |
| `GET /api/v1/companies` | Active company list, paginated with `limit` and `offset` |
| `GET /api/docs` | Local OpenAPI interface |

The backend init container runs `alembic upgrade head` before the API starts. To create a future migration locally:

```bash
cd backend
.venv/bin/alembic revision --autogenerate -m "describe the change"
```

Review generated migrations before committing them.

## Daily pipeline scaffold

The weekday CronJob runs at `23:30 UTC` with `concurrencyPolicy: Forbid`. It currently:

1. verifies database access and counts companies;
2. records structured placeholder events for prices, financials, filings, catalysts, risks, valuation, scoring, and validation;
3. exits non-zero on the first unexpected failure.

Provider calls and financial calculations are deliberately left for the next milestones. Only the pipeline pod has general TCP egress on ports 80 and 443.

## Storage and recovery note

The local-path volumes are node-bound and not highly available. The PVC protects data across pod restarts, not disk or node failure. Before meaningful research history accumulates, add a backup CronJob targeting a second disk, NAS, or another trusted machine.

## Out of scope for this milestone

- AWS or paid cloud infrastructure
- microservices and multiple operational databases
- distributed queues and database operators
- autoscaling and real-time market streams
- brokerage integration or automatic trading
- AI-generated investment claims
