#!/bin/sh
# Load locally built images into every cluster node's containerd.
#
# Docker Desktop's kind-provisioned cluster is not visible to the `kind` CLI,
# so `kind load docker-image` cannot reach it. This script reimplements the
# same mechanism with kubectl only: for each node it starts a short-lived
# privileged pod that mounts the node's root filesystem, copies a
# `docker save` tarball onto the node, and imports it by chroot-ing into the
# node and running its own `ctr` against the k8s.io containerd namespace.
set -eu

IMAGES="stock-intelligence-backend:dev stock-intelligence-frontend:dev"
LOADER_NAMESPACE="default"

TAR=$(mktemp -d)/si-images.tar
trap 'rm -rf "$(dirname "$TAR")"' EXIT INT TERM

echo "Saving images: $IMAGES"
# shellcheck disable=SC2086
docker save $IMAGES -o "$TAR"
echo "Tarball: $(du -h "$TAR" | cut -f1)"

NODES=$(kubectl get nodes -o name | cut -d/ -f2)
for NODE in $NODES; do
  POD="image-loader-$NODE"
  echo "--- $NODE"
  kubectl -n "$LOADER_NAMESPACE" delete pod "$POD" --ignore-not-found --wait=true >/dev/null 2>&1 || true
  cat <<EOF | kubectl -n "$LOADER_NAMESPACE" apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: $POD
  labels:
    app: stock-intelligence-image-loader
spec:
  nodeName: $NODE
  restartPolicy: Never
  tolerations:
    - key: node-role.kubernetes.io/control-plane
      operator: Exists
      effect: NoSchedule
  containers:
    - name: loader
      image: busybox:1.36
      command: ["sleep", "1800"]
      securityContext:
        privileged: true
      volumeMounts:
        - name: host-root
          mountPath: /host
  volumes:
    - name: host-root
      hostPath:
        path: /
EOF
  kubectl -n "$LOADER_NAMESPACE" wait --for=condition=Ready "pod/$POD" --timeout=180s
  echo "Copying tarball to $NODE ..."
  kubectl -n "$LOADER_NAMESPACE" cp "$TAR" "$POD:/host/tmp/si-images.tar"
  kubectl -n "$LOADER_NAMESPACE" exec "$POD" -- sh -c '
    set -e
    CTR=""
    for candidate in /usr/local/bin/ctr /usr/bin/ctr /bin/ctr; do
      if [ -x "/host$candidate" ]; then CTR="$candidate"; break; fi
    done
    if [ -z "$CTR" ]; then echo "ctr binary not found on node" >&2; exit 1; fi
    chroot /host "$CTR" -n k8s.io images import /tmp/si-images.tar
    chroot /host "$CTR" -n k8s.io images ls | grep stock-intelligence || true
    rm -f /host/tmp/si-images.tar
  '
  kubectl -n "$LOADER_NAMESPACE" delete pod "$POD" --wait=false >/dev/null
done

echo "Images imported into all nodes. Roll the pods (bump image revision + publish, or kubectl rollout restart) to pick them up."
