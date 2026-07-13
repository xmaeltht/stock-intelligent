# Stock Intelligence

A local-first Kubernetes stock research application. The MVP is a modular monolith: one Next.js frontend, one FastAPI backend image, PostgreSQL, and a scheduled research pipeline using that same backend image.

## What is included

- Next.js dark-terminal research UI at `https://stock-intelligence.maelkloud.com`
  (screener, market pulse, watchlist, and side-by-side compare pages)
- Same-origin research API proxy from Next.js to FastAPI
- SEC company-universe and company-facts ingestion, including multi-year
  revenue and net-income history, equity, operating income, and gross profit
- Delayed Nasdaq market-price ingestion (full OHLC history) through a
  replaceable provider adapter
- Transparent revenue, earnings, free-cash-flow, operating-income, and
  book-value multiple valuations with margins, ratios, and fiscal-year trends
- Opportunity scoring, confidence grades, catalysts, risks, and thesis breakers
- Per-stock research pages with candlestick/Bollinger/RSI/MACD charts,
  analysis-history tracking, and primary-source links
- A persistent watchlist with one-click starring from every table
- SQLAlchemy company and stock-analysis models with Alembic migrations
- PostgreSQL 17 StatefulSet with a 20 Gi local-path PVC
- 20 Gi market-data cache PVC
- Daily weekday research pipeline CronJob
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

The local values target `istio-ingress/maelkloud-gateway`.

- Stock Intelligence: `https://stock-intelligence.maelkloud.com`
- Argo CD: `https://argocd.maelkloud.com`

Keep the Argo hostname protected
with Cloudflare Access in addition to Argo's own authentication.

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

Cloudflare terminates public TLS and forwards the two public hostnames through
the existing tunnel to the Istio Gateway. The Gateway-to-service hop remains
private HTTP; users only access the HTTPS domain names above.

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
| `GET /api/v1/opportunities/summary` | Universe, current analysis, and qualification counts |
| `GET /api/v1/opportunities/list` | Lean ranked rows with upside, price, volume, score, signal, and watchlist filters |
| `GET /api/v1/opportunities/overview` | Market pulse: breadth, score/upside distributions, movers, exchange counts |
| `GET /api/v1/opportunities/compare?tickers=A,B` | Latest full analyses for up to six tickers side by side |
| `GET /api/v1/opportunities/stocks/{ticker}` | Latest detailed research for a ticker, including stored fundamentals |
| `GET /api/v1/opportunities/stocks/{ticker}/history` | How price, fair value, and score evolved across analysis runs |
| `GET /api/v1/watchlist` | Watchlist entries joined with each security's latest analysis |
| `POST /api/v1/watchlist/{ticker}` / `DELETE …` | Add or remove a watchlist entry |
| `GET /api/docs` | Local OpenAPI interface |

The dashboard screener defaults to 95%+ modeled upside and can filter by ticker or company,
maximum share price (including below $5 and below $20), minimum daily volume, trend signal,
and watchlist membership. Results can be ranked by opportunity score, upside, name, ticker,
price, or volume in either direction. Each refreshed stock page includes a one-year OHLC
candlestick chart with volume, SMA-20/50/200, Bollinger Bands (20, 2) with %B, Wilder RSI-14,
ATR-14 volatility, quarterly support/resistance, golden/death cross detection on the 50/200
SMAs, 1/5/20-day price changes, 52-week range, MACD (12/26/9) with Elder-style impulse
coloring, and a transparent six-check technical-confirmation list. Technical indicators support
trend and timing decisions; they do not alter or prove the fundamental fair-value estimate.

Stock pages additionally surface stored fundamentals: multi-year revenue and net-income
fiscal trends, revenue CAGR, gross/operating/net/FCF margins, P/S, P/E, P/FCF, and P/B
ratios, book value per share, and market capitalization — all derived from the same SEC
company facts used for the valuation. The Market page aggregates breadth (signal and
impulse), score and upside distributions, top daily gainers/losers, most active securities,
and analyzer health across the covered universe.

The asset-type selector separates operating-company stocks from ETFs using Nasdaq Trader's
official ETF flag. Stock mode retains the fundamental-upside model. ETF mode disables the
upside threshold and ranks funds only by transparent price-trend and liquidity signals; it
does not apply revenue, EPS, or cash-flow multiples to funds.

The backend init container runs `alembic upgrade head` before the API starts. To create a future migration locally:

```bash
cd backend
.venv/bin/alembic revision --autogenerate -m "describe the change"
```

Review generated migrations before committing them.

## Daily research pipeline

The continuously running analyzer Deployment:

1. refreshes the SEC-listed company universe;
2. selects up to 500 eligible Nasdaq, NYSE, or NYSE American securities, prioritizing
   securities that have never been attempted and then the oldest successful analyses;
3. retrieves delayed prices and SEC company facts while recording per-security failures;
4. calculates deterministic fair values, scenarios, scores, catalysts, and risks;
5. persists auditable analysis history and validates the run.

It starts the next batch five seconds after the previous batch finishes. Once every eligible
security has been attempted, it remains alive and checks every five minutes for retries or
analyses older than 24 hours. The batches are resumable: one failed provider response does
not discard successful work.
Failed securities cool down for 24 hours before retry, and the dashboard separately reports
eligible, analyzed, remaining, failed, and percentage coverage. Set `ANALYSIS_SYMBOLS` only
for an intentional targeted run; leaving it empty enables eligible-universe mode.

Only the pipeline pod has general TCP egress on ports 80 and 443.

## Storage and recovery note

The local-path volumes are node-bound and not highly available. The PVC protects data across pod restarts, not disk or node failure. Before meaningful research history accumulates, add a backup CronJob targeting a second disk, NAS, or another trusted machine.

## Out of scope for this milestone

- AWS or paid cloud infrastructure
- microservices and multiple operational databases
- distributed queues and database operators
- autoscaling and real-time market streams
- brokerage integration or automatic trading
- AI-generated investment claims
