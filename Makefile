SHELL := /bin/sh

PYTHON ?= python3
VENV := backend/.venv
BACKEND_PYTHON := $(VENV)/bin/python
BACKEND_PIP := $(VENV)/bin/pip
RELEASE ?= stock-intelligence
NAMESPACE ?= stock-intelligence
CHART := charts/stock-intelligence
VALUES := $(CHART)/values-local.yaml
GATEWAY_NAME ?= maelkloud-gateway
GATEWAY_NAMESPACE ?= istio-ingress

.PHONY: help install backend-install frontend-install test backend-test backend-lint frontend-check \
	helm-lint helm-template validate dev-backend dev-frontend build-images load-images cluster-check \
	deploy-helm publish-local-git uninstall

help:
	@awk 'BEGIN {FS = ":.*## "; print "Available targets:"} /^[a-zA-Z_-]+:.*## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: backend-install frontend-install ## Install local development dependencies

backend-install: ## Create a Python virtual environment and install backend dependencies
	$(PYTHON) -m venv $(VENV)
	$(BACKEND_PIP) install --upgrade pip
	$(BACKEND_PIP) install -e 'backend[dev]'

frontend-install: ## Install frontend dependencies
	cd frontend && npm install

backend-test: ## Run backend unit tests
	cd backend && .venv/bin/pytest

backend-lint: ## Lint backend Python
	cd backend && .venv/bin/ruff check .

frontend-check: ## Type-check, lint, and build the frontend
	cd frontend && npm run typecheck && npm run lint && npm run build

test: backend-test backend-lint frontend-check helm-lint helm-template ## Run all local verification

helm-lint: ## Lint the Helm chart
	helm lint $(CHART) -f $(VALUES)

helm-template: ## Render Kubernetes manifests into work/rendered.yaml
	mkdir -p work
	helm template $(RELEASE) $(CHART) -f $(VALUES) > work/rendered.yaml

validate: backend-test backend-lint frontend-check helm-lint helm-template ## Validate application and deployment assets

dev-backend: ## Run FastAPI on localhost:8000
	cd backend && .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

dev-frontend: ## Run Next.js on localhost:3000
	cd frontend && BACKEND_URL=http://localhost:8000 npm run dev

build-images: ## Build images directly into Docker Desktop's local image store
	docker build -t stock-intelligence-backend:dev backend
	docker build -t stock-intelligence-frontend:dev frontend

load-images: ## Load already-built images into the Docker Desktop kind cluster
	kind load docker-image stock-intelligence-backend:dev stock-intelligence-frontend:dev --name desktop

cluster-check: ## Show required cluster APIs and configured Gateway objects
	kubectl config current-context
	kubectl get storageclass
	kubectl api-resources --api-group=gateway.networking.k8s.io
	kubectl get gateway -A
	kubectl api-resources --api-group=argoproj.io

deploy-helm: ## Deploy locally; requires POSTGRES_PASSWORD and installed Gateway API/controller
	@test -n "$(POSTGRES_PASSWORD)" || (echo "POSTGRES_PASSWORD is required" && exit 1)
	helm upgrade --install $(RELEASE) $(CHART) --namespace $(NAMESPACE) --create-namespace \
		-f $(VALUES) \
		--set-string secrets.postgresPassword='$(POSTGRES_PASSWORD)' \
		--set-string gateway.parentRef.name='$(GATEWAY_NAME)' \
		--set-string gateway.parentRef.namespace='$(GATEWAY_NAMESPACE)' \
		--set-string networkPolicy.gatewayNamespace='$(GATEWAY_NAMESPACE)'

publish-local-git: ## Publish the current source snapshot to the in-cluster Git server for Argo CD
	./scripts/publish-local-git.sh

uninstall: ## Remove the Helm release but retain bound PVC data per cluster behavior
	helm uninstall $(RELEASE) --namespace $(NAMESPACE)
