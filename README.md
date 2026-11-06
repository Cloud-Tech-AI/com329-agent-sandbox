# com329-agent-sandbox

A Strands agent that changes code in a local git repo and opens a GitLab merge request. A single page shows each step the agent takes.

- `src/agent.py`: the agent. Six tools: `clone_repo`, `read_file`, `grep_files`, `write_file`, `push_branch` and `create_pull_request`.
- `src/server.py`: FastAPI app. Starts a run and streams its steps over server-sent events.
- `src/config.py`: settings, from `.env`, the environment or the mounted Kubernetes Secret.
- `static/index.html`: the page.
- `k8s/`, `scripts/`: Kubernetes manifests and the deploy scripts (see below).

## Setup

Needs `uv`, `npx` (Node.js), AWS credentials with Bedrock access, and a GitLab personal access token with `api` scope. The target repo must have an `origin` remote.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export AWS_PROFILE=your-profile      # or the AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY pair
export AWS_REGION=us-east-1
export GITLAB_TOKEN=glpat-xxxx
export GITLAB_API_URL=https://gitlab.com/api/v4   # change for self-hosted GitLab

uvicorn server:app --app-dir src --reload   # run from the repo root, so .env is found
```

Open http://localhost:8000, enter the local repo path, the GitLab project (`group/name`) and the change to make, then click **Run agent**.

## Notes

- The agent only writes inside the repo path it receives.
- It creates a branch named `agent/...`, commits, pushes and opens an MR into `main`.
- Runs are held in memory, so a restart clears them.

## Docker

Settings come from `.env` (see `.env.example`). The agent edits git repos, so mount them into the container. Each repo must already be cloned, with a git identity set (`git config user.name` and `user.email`) in the image or the repo.

```bash
REPOS_DIR=~/workspace docker compose up --build
```

Inside the page, use paths such as `/repos/demo-application`.

## Kubernetes

Copy `.env.example` to `.env`, fill it in, then deploy with `scripts/deploy.sh` (see below). The script creates the `code-change-agent-secrets` Secret from your shell variables and `.env` (shell variables win), applies `k8s/serviceaccount.yaml` and applies the deployments. To only create or update the Secret:

```bash
scripts/deploy.sh secret
```

The Secret holds `AWS_REGION`, `MODEL_ID`, `GITHUB_TOKEN`, `GITHUB_API_URL` and, optionally, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` and `AWS_SESSION_TOKEN`. `AWS_PROFILE` is never copied. The Secret is mounted read-only at `/etc/code-change-agent/secrets`, and each key becomes a file that `src/config.py` reads. Don't create it with `--from-env-file=.env` on EKS: the blank `AWS_PROFILE` and key lines would become empty files and can override the IAM role.

### AWS credentials on EKS (no static keys)

The pod runs as the `code-change-agent` service account, and `boto3` picks up the IAM role from it.

1. Get an IAM role from your AWS account admins that can invoke the Bedrock model set by `MODEL_ID`. The role and its permissions are managed on the AWS side, not in this repo.
2. Link the role to the service account, using one of:
   - **IRSA:** the role trusts the cluster's OIDC provider, limited to `system:serviceaccount:<namespace>:code-change-agent`. Set the role ARN in the annotation in [k8s/serviceaccount.yaml](k8s/serviceaccount.yaml).
   - **EKS Pod Identity:** the role trusts `pods.eks.amazonaws.com`. Remove the annotation and run `aws eks create-pod-identity-association` (command in `serviceaccount.yaml`).
3. Make sure Bedrock model access for Claude Sonnet is enabled in the account and region set by `AWS_REGION`.

On a non-EKS cluster, put `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` in the Secret instead.

The deployment has no repo volume yet, so the agent cannot edit repos inside the cluster until you add one.

### Two deployments: direct and gVisor

[scripts/deploy.sh](scripts/deploy.sh) runs the same image twice, side by side:

| Deployment / Service | Runtime | Manifest |
| --- | --- | --- |
| `code-change-agent` | runc (direct) | [k8s/deployment.yaml](k8s/deployment.yaml) |
| `code-change-agent-gvisor` | gVisor (`runtimeClassName: gvisor`) | [k8s/deployment-gvisor.yaml](k8s/deployment-gvisor.yaml) |

```bash
# one-time: install gVisor on the nodes that will run sandboxed pods
scripts/deploy.sh setup-gvisor <node-name> [<node-name>...]   # or --all

# deploy both (or: direct | gvisor | status | delete)
IMAGE=<acct>.dkr.ecr.us-east-1.amazonaws.com/code-change-agent:v1 scripts/deploy.sh all
```

`setup-gvisor` labels the nodes `sandbox=gvisor` and runs [k8s/gvisor/gvisor-installer.yaml](k8s/gvisor/gvisor-installer.yaml), a privileged DaemonSet that installs `runsc`, registers it with containerd and restarts containerd once per node. The `gvisor` RuntimeClass ([k8s/gvisor/runtimeclass-gvisor.yaml](k8s/gvisor/runtimeclass-gvisor.yaml)) only schedules pods onto those nodes. After the rollout, the script checks `dmesg` in the pod to confirm it runs under gVisor.
