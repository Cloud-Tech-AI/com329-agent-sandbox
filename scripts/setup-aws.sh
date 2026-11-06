#!/usr/bin/env bash
# One-time AWS setup for the code change agent on EKS:
#   1. push the image to ECR (repo code-change-agent, created already if missing)
#   2. create IAM role code-change-agent-bedrock (Bedrock invoke only)
#   3. link it to the code-change-agent service account with EKS Pod Identity
# Safe to re-run. Prints the IMAGE value to pass to scripts/deploy.sh.
#
# Environment: CLUSTER (sample-cluster), REGION (us-east-1), NAMESPACE (default),
#              TAG (v1), MODEL_ID (global.anthropic.claude-sonnet-4-6)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLUSTER="${CLUSTER:-sample-cluster}"
REGION="${REGION:-us-east-1}"
NAMESPACE="${NAMESPACE:-default}"
TAG="${TAG:-v1}"
MODEL_ID="${MODEL_ID:-global.anthropic.claude-sonnet-4-6}"
ROLE=code-change-agent-bedrock
SA=code-change-agent

ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
REGISTRY="$ACCOUNT.dkr.ecr.$REGION.amazonaws.com"
IMAGE="$REGISTRY/code-change-agent:$TAG"
log() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }

log "ECR: $IMAGE"
aws ecr describe-repositories --region "$REGION" --repository-names code-change-agent >/dev/null 2>&1 \
  || aws ecr create-repository --region "$REGION" --repository-name code-change-agent \
       --image-scanning-configuration scanOnPush=true >/dev/null
docker build -t "$IMAGE" "$ROOT"
# Push with a throwaway Docker config that has no credsStore: Docker Desktop's
# store needs `pass`, which may not be set up. The ECR token (valid 12h) is
# written only to this temp dir and removed when the script exits. DOCKER_HOST
# keeps the push on the same engine (Docker Desktop context) the image was built in.
DOCKER_HOST="$(docker context inspect --format '{{.Endpoints.docker.Host}}')"
export DOCKER_HOST
PUSH_CONFIG=$(mktemp -d)
trap 'rm -rf "$PUSH_CONFIG"' EXIT
echo '{}' > "$PUSH_CONFIG/config.json"
aws ecr get-login-password --region "$REGION" \
  | docker --config "$PUSH_CONFIG" login --username AWS --password-stdin "$REGISTRY"
docker --config "$PUSH_CONFIG" push "$IMAGE"
unset DOCKER_HOST

log "IAM role $ROLE"
TRUST=$(cat <<EOF
{"Version":"2012-10-17","Statement":[{"Effect":"Allow",
 "Principal":{"Service":"pods.eks.amazonaws.com"},
 "Action":["sts:AssumeRole","sts:TagSession"],
 "Condition":{"StringEquals":{"aws:SourceAccount":"$ACCOUNT"},
              "ArnEquals":{"aws:SourceArn":"arn:aws:eks:$REGION:$ACCOUNT:cluster/$CLUSTER"}}}]}
EOF
)
# A global.* inference profile can route to any region, so the model ARN uses a region wildcard.
BASE_MODEL="${MODEL_ID#global.}"; BASE_MODEL="${BASE_MODEL#us.}"
POLICY=$(cat <<EOF
{"Version":"2012-10-17","Statement":[{"Effect":"Allow",
 "Action":["bedrock:InvokeModel","bedrock:InvokeModelWithResponseStream"],
 "Resource":["arn:aws:bedrock:$REGION:$ACCOUNT:inference-profile/$MODEL_ID",
             "arn:aws:bedrock:*::foundation-model/${BASE_MODEL}*"]}]}
EOF
)
if aws iam get-role --role-name "$ROLE" >/dev/null 2>&1; then
  aws iam update-assume-role-policy --role-name "$ROLE" --policy-document "$TRUST"
else
  aws iam create-role --role-name "$ROLE" --assume-role-policy-document "$TRUST" \
    --description "Bedrock access for code-change-agent pods on $CLUSTER" >/dev/null
fi
aws iam put-role-policy --role-name "$ROLE" --policy-name bedrock-invoke --policy-document "$POLICY"
ROLE_ARN=$(aws iam get-role --role-name "$ROLE" --query Role.Arn --output text)

log "Pod Identity: $NAMESPACE/$SA -> $ROLE_ARN"
EXISTING=$(aws eks list-pod-identity-associations --region "$REGION" --cluster-name "$CLUSTER" \
  --namespace "$NAMESPACE" --service-account "$SA" --query 'associations[0].associationId' --output text)
if [[ "$EXISTING" == "None" || -z "$EXISTING" ]]; then
  aws eks create-pod-identity-association --region "$REGION" --cluster-name "$CLUSTER" \
    --namespace "$NAMESPACE" --service-account "$SA" --role-arn "$ROLE_ARN" >/dev/null
else
  aws eks update-pod-identity-association --region "$REGION" --cluster-name "$CLUSTER" \
    --association-id "$EXISTING" --role-arn "$ROLE_ARN" >/dev/null
fi

log "done. Deploy with:"
echo "  IMAGE=$IMAGE scripts/deploy.sh all"
