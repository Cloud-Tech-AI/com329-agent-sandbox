#!/usr/bin/env bash
# Deploys the code change agent to Kubernetes in two ways, side by side:
#   direct  - normal container (runc)          -> deployment.yaml,        Service code-change-agent
#   gvisor  - same image in a gVisor sandbox    -> deployment-gvisor.yaml, Service code-change-agent-gvisor
#
# Usage:
#   scripts/deploy.sh [command] [args]
#
# Commands:
#   all                    deploy both (default)
#   direct                 deploy only the direct deployment
#   gvisor                 deploy only the gVisor deployment
#   secret                 create/update the Secret from local env / .env, without deploying
#   setup-gvisor NODE...   label NODEs sandbox=gvisor and install gVisor on them (one-time)
#   setup-gvisor --all     same, for every node in the cluster
#   status                 show both deployments, their pods and runtimes
#   delete                 remove both deployments and Services (keeps Secret, SA, gVisor nodes)
#
# Environment:
#   NAMESPACE   namespace to deploy into (default: default)
#   IMAGE       image to run, e.g. <acct>.dkr.ecr.us-east-1.amazonaws.com/code-change-agent:v1
#               (default: the image in the manifests, code-change-agent:latest)
#   TIMEOUT     rollout wait (default: 180s)
#   ENV_FILE    file to read settings from (default: .env in the repo root)
#
# Secret: every deploy creates/updates code-change-agent-secrets from your local settings.
# Exported shell variables win over ENV_FILE. Keys used: AWS_REGION, MODEL_ID, GITHUB_TOKEN,
# GITHUB_API_URL, and optionally AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN
# (leave those unset on EKS to use the pod's IAM role). AWS_PROFILE is never copied.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
K8S="$ROOT/k8s"
NAMESPACE="${NAMESPACE:-default}"
IMAGE="${IMAGE:-}"
TIMEOUT="${TIMEOUT:-180s}"
ENV_FILE="${ENV_FILE:-$ROOT/.env}"
DEFAULT_IMAGE="code-change-agent:latest"
SECRET=code-change-agent-secrets

kc() { kubectl -n "$NAMESPACE" "$@"; }
log() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33mwarning:\033[0m %s\n' "$*" >&2; }
die() { printf '\033[1;31merror:\033[0m %s\n' "$*" >&2; exit 1; }

# Print a manifest with the image swapped for $IMAGE, if set.
render() {
  if [[ -n "$IMAGE" ]]; then
    sed "s|image: ${DEFAULT_IMAGE}|image: ${IMAGE}|" "$1"
  else
    cat "$1"
  fi
}

# Settings copied from the local environment into the Secret (see .env.example).
# AWS_PROFILE is deliberately absent: a profile name means nothing inside a pod.
SECRET_KEYS="AWS_REGION MODEL_ID GITHUB_TOKEN GITHUB_API_URL AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN"
SECRET_CHANGED=0

# Value of $1 from $ENV_FILE (last assignment wins, matching surrounding quotes removed). Empty if absent.
env_file_value() {
  [[ -f "$ENV_FILE" ]] || return 0
  local line val
  line=$(grep -E "^[[:space:]]*(export[[:space:]]+)?$1=" "$ENV_FILE" | tail -n1) || return 0
  val="${line#*=}"
  val="${val%$'\r'}"
  if [[ "$val" =~ ^\"(.*)\"$ || "$val" =~ ^\'(.*)\'$ ]]; then val="${BASH_REMATCH[1]}"; fi
  printf '%s' "$val"
}

# Create/update the Secret from local settings: exported shell variables first, then .env
# (same precedence as config.py). Falls back to an existing Secret when nothing is set locally.
sync_secret() {
  local tmp key val count=0
  tmp=$(mktemp)
  # shellcheck disable=SC2064
  trap "rm -f '$tmp'" RETURN
  for key in $SECRET_KEYS; do
    val="${!key:-}"
    [[ -n "$val" ]] || val=$(env_file_value "$key")
    [[ -n "${val//[[:space:]]/}" ]] || continue
    printf '%s=%s\n' "$key" "$val" >>"$tmp"
    count=$((count + 1))
  done

  if [[ $count -eq 0 ]]; then
    kc get secret "$SECRET" >/dev/null 2>&1 \
      || die "no settings found in the environment or $ENV_FILE, and Secret $SECRET does not exist in $NAMESPACE. Copy .env.example to .env and fill it in."
    warn "no local settings found; keeping the existing Secret $SECRET"
    return
  fi
  grep -q '^GITHUB_TOKEN=' "$tmp" \
    || warn "GITHUB_TOKEN is not set in the environment or $ENV_FILE; opening pull requests will fail"

  log "syncing Secret $SECRET from local env ($(cut -d= -f1 "$tmp" | tr '\n' ' '))"
  local out
  out=$(kc create secret generic "$SECRET" --from-env-file="$tmp" --dry-run=client -o yaml | kc apply -f -)
  echo "$out"
  # The app caches settings at startup, so running pods need a restart to see new values.
  [[ "$out" == *configured* ]] && SECRET_CHANGED=1
  return 0
}

preflight_cluster() {
  command -v kubectl >/dev/null || die "kubectl not found"
  kubectl cluster-info >/dev/null 2>&1 || die "cannot reach the cluster (context: $(kubectl config current-context 2>/dev/null || echo none))"
  log "cluster: $(kubectl config current-context), namespace: $NAMESPACE"
  kubectl get namespace "$NAMESPACE" >/dev/null 2>&1 || kubectl create namespace "$NAMESPACE"
}

preflight() {
  preflight_cluster
  sync_secret
  [[ -n "$IMAGE" ]] || warn "IMAGE not set, using $DEFAULT_IMAGE. EKS nodes cannot pull a local image; set IMAGE to an ECR image."
  grep -Eq '^[[:space:]]*eks\.amazonaws\.com/role-arn:.*<ACCOUNT_ID>' "$K8S/serviceaccount.yaml" \
    && warn "serviceaccount.yaml still has <ACCOUNT_ID> in the IRSA annotation; Bedrock calls will fail unless you use Pod Identity."
  log "applying service account"
  kc apply -f "$K8S/serviceaccount.yaml"
}

wait_rollout() {
  if [[ "$SECRET_CHANGED" == 1 ]]; then
    log "Secret changed, restarting $1"
    kc rollout restart "deployment/$1"
  fi
  if ! kc rollout status "deployment/$1" --timeout="$TIMEOUT"; then
    kc get pods -l "app=$1" -o wide || true
    kc describe pods -l "app=$1" | tail -n 25 || true
    die "deployment $1 did not become ready"
  fi
}

deploy_direct() {
  log "deploying code-change-agent (direct, runc)"
  render "$K8S/deployment.yaml" | kc apply -f -
  wait_rollout code-change-agent
}

gvisor_nodes() { kubectl get nodes -l sandbox=gvisor -o name; }

# True if the VPC CNI network policy agent is enforcing NetworkPolicies.
network_policy_enabled() {
  kubectl -n kube-system get ds aws-node \
    -o jsonpath='{.spec.template.spec.containers[?(@.name=="aws-eks-nodeagent")].args}' 2>/dev/null \
    | grep -q -- '--enable-network-policy=true'
}

deploy_gvisor() {
  log "deploying code-change-agent-gvisor (gVisor sandbox, runsc)"
  [[ -n "$(gvisor_nodes)" ]] \
    || die "no nodes labelled sandbox=gvisor. Run: scripts/deploy.sh setup-gvisor <node-name> (or --all)"
  kubectl get daemonset -n gvisor-system gvisor-installer >/dev/null 2>&1 \
    || warn "gvisor-installer is not deployed; assuming gVisor was installed on the nodes some other way"
  kubectl apply -f "$K8S/gvisor/runtimeclass-gvisor.yaml"
  network_policy_enabled \
    || warn "network policy enforcement is off in the VPC CNI; the gVisor pod's egress lockdown will be ignored. Enable it with: aws eks update-addon --cluster-name <cluster> --addon-name vpc-cni --configuration-values '{\"enableNetworkPolicy\":\"true\"}'"
  kc apply -f "$K8S/gvisor/networkpolicy-gvisor.yaml"
  render "$K8S/deployment-gvisor.yaml" | kc apply -f -
  wait_rollout code-change-agent-gvisor
  verify_gvisor
}

# Confirm the pod really runs under gVisor: its kernel log comes from the Sentry, not Linux.
verify_gvisor() {
  local pod
  pod=$(kc get pods -l app=code-change-agent-gvisor -o jsonpath='{.items[0].metadata.name}')
  if kc exec "$pod" -- sh -c 'dmesg 2>/dev/null | grep -qi gvisor'; then
    log "verified: $pod is running inside gVisor"
  else
    warn "could not confirm gVisor inside $pod (check: kubectl -n $NAMESPACE exec $pod -- dmesg)"
  fi
}

setup_gvisor() {
  [[ $# -gt 0 ]] || die "name the nodes to use for gVisor, or pass --all. Nodes: $(kubectl get nodes -o name | tr '\n' ' ')"
  if [[ "$1" == "--all" ]]; then
    log "labelling all nodes sandbox=gvisor"
    kubectl label nodes --all sandbox=gvisor --overwrite
  else
    log "labelling $* sandbox=gvisor"
    kubectl label nodes "$@" sandbox=gvisor --overwrite
  fi
  log "installing gVisor on labelled nodes (privileged DaemonSet, restarts containerd once per node)"
  kubectl apply -f "$K8S/gvisor/gvisor-installer.yaml"
  kubectl apply -f "$K8S/gvisor/runtimeclass-gvisor.yaml"
  if ! kubectl -n gvisor-system rollout status daemonset/gvisor-installer --timeout="$TIMEOUT"; then
    kubectl -n gvisor-system logs -l app=gvisor-installer -c install --tail=30 || true
    die "gVisor install did not finish"
  fi
  kubectl -n gvisor-system logs -l app=gvisor-installer -c install --tail=3 --prefix || true
  log "gVisor ready on: $(gvisor_nodes | tr '\n' ' ')"
}

status() {
  kc get deploy/code-change-agent deploy/code-change-agent-gvisor svc/code-change-agent svc/code-change-agent-gvisor \
    --ignore-not-found -o wide
  echo
  kc get pods -o custom-columns='POD:.metadata.name,APP:.metadata.labels.app,RUNTIME:.spec.runtimeClassName,STATUS:.status.phase,NODE:.spec.nodeName' \
    -l 'app in (code-change-agent,code-change-agent-gvisor)'
  echo
  echo "Open them locally:"
  echo "  kubectl -n $NAMESPACE port-forward svc/code-change-agent 8000:80"
  echo "  kubectl -n $NAMESPACE port-forward svc/code-change-agent-gvisor 8001:80"
}

delete() {
  log "deleting both deployments and Services from $NAMESPACE"
  kc delete -f "$K8S/deployment.yaml" --ignore-not-found
  kc delete -f "$K8S/deployment-gvisor.yaml" --ignore-not-found
}

cmd="${1:-all}"
[[ $# -gt 0 ]] && shift
case "$cmd" in
  all)          preflight; deploy_direct; deploy_gvisor; status ;;
  direct)       preflight; deploy_direct; status ;;
  gvisor)       preflight; deploy_gvisor; status ;;
  secret)       preflight_cluster; sync_secret ;;
  setup-gvisor) setup_gvisor "$@" ;;
  status)       status ;;
  delete)       delete ;;
  -h|--help|help) sed -n '2,29p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//' ;;
  *)            die "unknown command: $cmd (try --help)" ;;
esac
