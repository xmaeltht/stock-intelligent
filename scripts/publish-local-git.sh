#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT INT TERM

COPYFILE_DISABLE=1 tar -czf "$TMP_DIR/repository.tgz" \
  --exclude='./.git' \
  --exclude='./work' \
  --exclude='./outputs' \
  --exclude='node_modules' \
  --exclude='.next' \
  --exclude='.venv' \
  --exclude='__pycache__' \
  --exclude='.pytest_cache' \
  --exclude='.ruff_cache' \
  --exclude='*.pyc' \
  --exclude='*.tsbuildinfo' \
  --exclude='._*' \
  --exclude='.DS_Store' \
  -C "$ROOT_DIR" .

kubectl create configmap stock-git-source \
  --namespace stock-intelligence \
  --from-file="repository.tgz=$TMP_DIR/repository.tgz" \
  --dry-run=client \
  -o yaml > "$TMP_DIR/stock-git-source.yaml"

kubectl apply --server-side -f "$TMP_DIR/stock-git-source.yaml"
kubectl apply --server-side -f "$ROOT_DIR/platform/local-git.yaml"
kubectl rollout restart deployment/stock-git --namespace stock-intelligence
kubectl rollout status deployment/stock-git --namespace stock-intelligence --timeout=180s
kubectl apply --server-side --namespace argocd -f "$ROOT_DIR/argocd/application.yaml"

echo "Local Git source published. Argo CD will reconcile the new main revision."
