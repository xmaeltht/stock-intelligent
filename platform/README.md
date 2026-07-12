# Local cluster bootstrap

Pinned versions used for this development cluster:

| Component | Version | Installation |
|---|---:|---|
| Gateway API | 1.6.0 | Official standard-channel manifest |
| Istio | 1.30.2 | Official `base` and `istiod` Helm charts |
| Argo CD | 3.4.5 | Official non-HA installation manifest |
| NetworkPolicy controller | 1.1.0 manifest | Kubernetes SIG Network reference implementation |

The application uses an Istio-managed Kubernetes Gateway API `Gateway`. Istio automatically creates the corresponding proxy Deployment and LoadBalancer Service after `platform/gateway.yaml` is applied.

The listener is HTTP-only for the local foundation. Add cert-manager and a TLS certificate before changing it to HTTPS.

## Recreate the platform

```bash
kubectl apply --server-side -f \
  https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.6.0/standard-install.yaml

helm repo add istio https://istio-release.storage.googleapis.com/charts
helm repo update istio
helm upgrade --install istio-base istio/base --version 1.30.2 \
  --namespace istio-system --create-namespace --set defaultRevision=default --wait
helm upgrade --install istiod istio/istiod --version 1.30.2 \
  --namespace istio-system --wait

kubectl create namespace argocd
kubectl apply -n argocd --server-side --force-conflicts -f \
  https://raw.githubusercontent.com/argoproj/argo-cd/v3.4.5/manifests/install.yaml

kubectl apply --server-side -f \
  https://raw.githubusercontent.com/kubernetes-sigs/kube-network-policies/v1.1.0/install.yaml

kubectl apply -f platform/gateway.yaml
```

The Argo CD command uses the official non-HA same-cluster installation. Do not
rerun `kubectl create namespace argocd` when the namespace already exists.

## NetworkPolicy enforcement

Docker Desktop's current `kindnet` uses containerd NRI rather than a normal CNI
configuration file. The Kubernetes SIG Network reference controller also uses
NRI, so it enforces standard Kubernetes `NetworkPolicy` resources without
replacing `kindnet`, pod IPAM, routing, or kube-proxy.

Verify the four node agents:

```bash
kubectl get daemonset kube-network-policies -n kube-system
```

Run the reusable deny/allow test against Argo CD Redis:

```bash
kubectl apply --server-side -f platform/network-policy-probe.yaml
kubectl get jobs -n argocd netpol-denied-probe netpol-allowed-probe
```

Both Jobs must complete. The denied probe succeeds only if its connection is
blocked; the allowed probe succeeds only if its connection works. Kubernetes
automatically removes both Jobs 120 seconds after completion.

## Gateway

```bash
kubectl apply -f platform/gateway.yaml
kubectl wait --namespace istio-ingress \
  --for=condition=Programmed gateway/maelkloud-gateway \
  --timeout=180s
```

Only namespaces labelled `gateway-access=maelkloud` may attach routes.

Docker Desktop publishes this LoadBalancer on `127.0.0.1:80`, even though the
Gateway status reports an internal cluster address. Use the zero-configuration
local hostname:

```text
http://stock-intelligence.localhost
```

The stock application does not claim any `maelkloud.com` hostname.

Before the stock application is deployed, a request to that host should reach
`istio-envoy` and return HTTP 404 because no matching `HTTPRoute` exists yet.

## Local Git source for Argo CD

`platform/local-git.yaml` runs a small read-only Git daemon inside the cluster.
It exists only to give Argo CD a real Git source without requiring GitHub or a
paid hosted service. Publish source changes with:

```bash
make publish-local-git
```

The Git service is reachable only inside the cluster, and its NetworkPolicy
permits repository reads only from the `argocd` namespace.

## Argo CD access

Argo CD is intentionally not exposed publicly. Access it locally when needed:

```bash
kubectl port-forward service/argocd-server -n argocd 8080:443
```

Then open `https://localhost:8080`. Retrieve the initial admin password with:

```bash
kubectl get secret argocd-initial-admin-secret -n argocd \
  -o jsonpath='{.data.password}' | base64 --decode
```
