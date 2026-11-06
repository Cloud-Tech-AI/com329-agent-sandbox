# Code Change Agent

A [Strands](https://strandsagents.com/) agent that makes a code change in a GitHub repository and opens a pull request. It uses Claude on Amazon Bedrock, runs behind a small FastAPI server, and shows each step it takes on a single web page.

It is the sample workload for [COM329](../README.md): the same image runs on Amazon EKS once with the default `runc` runtime and once inside a [gVisor](https://gvisor.dev/) sandbox.

- [How it works](#how-it-works)
- [Prerequisites](#prerequisites)
- [Run locally](#run-locally)
- [Run with Docker](#run-with-docker)
- [Deploy to Amazon EKS](#deploy-to-amazon-eks)
- [Adapting to your cluster](#adapting-to-your-cluster)
- [Configuration reference](#configuration-reference)
- [HTTP API](#http-api)
- [Troubleshooting](#troubleshooting)
- [Clean up](#clean-up)

## How it works

| File | Purpose |
| --- | --- |
| [`agent.py`](agent.py) | The agent and its six tools: `clone_repo`, `read_file`, `grep_files`, `write_file`, `push_branch`, `create_pull_request`. |
| [`server.py`](server.py) | FastAPI app. `POST /runs` starts a run in a background thread; `GET /runs/{id}/events` streams its steps as server-sent events. |
| [`config.py`](config.py) | Settings from environment variables, `.env`, or files in a mounted Kubernetes Secret. |
| [`static/index.html`](static/index.html) | The page: enter `owner/repo` and the change to make, then watch the steps. |

For each run the agent:

1. Clones `https://github.com/<owner>/<repo>` into a fresh temporary directory, using `GITHUB_TOKEN`.
2. Explores with `grep_files` and `read_file`, then edits with `write_file`. Every path is checked to stay inside the clone.
3. Commits on a branch named `agent/<short-task-slug>` and pushes it to `origin`.
4. Opens a pull request into `main` through the GitHub REST API and replies with its URL.
5. Deletes the temporary directory, whether the run succeeded or not.

The token is scrubbed from any `git` output before it reaches the model or the page.

## Prerequisites

| Need | For | Notes |
| --- | --- | --- |
| Python 3.10+ and `git` | local runs | |
| Docker | Docker runs and building the image | |
| AWS credentials with `bedrock:InvokeModel` | all | On access to the model set by `MODEL_ID` (default `global.anthropic.claude-sonnet-4-6`) in `AWS_REGION`. |
| GitHub token | all | Fine-grained token with **Contents: read and write** and **Pull requests: read and write** on the target repo, or a classic token with `repo` scope. Use a test repository. |
| An EKS cluster, `kubectl`, `aws` CLI v2 | EKS | The [EKS Pod Identity Agent](https://docs.aws.amazon.com/eks/latest/userguide/pod-id-agent-setup.html) add-on must be installed. |
| Nodes you can modify | gVisor | The installer needs `bash`, `curl`, `systemd`, `bzip2` or `zstd`, and a writable `/etc/containerd/config.toml` (for example Amazon Linux 2023 managed or self-managed nodes). It does not work on Fargate, Bottlerocket or EKS Auto Mode nodes. |
| VPC CNI network policy enforcement | gVisor egress lockdown | See [Adapting to your cluster](#adapting-to-your-cluster). |

The target repository must have a `main` branch, which is the pull request base.

## Run locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env: set GITHUB_TOKEN, and AWS_PROFILE if you don't use the default profile

uvicorn server:app --reload
```

Open http://localhost:8000, enter the repository as `owner/name` and describe the change, then click **Run agent**.

## Run with Docker

Settings come from `.env` (see [`.env.example`](.env.example)). Your `~/.aws` folder is mounted read-only so profiles and SSO work inside the container.

```bash
cp .env.example .env     # set GITHUB_TOKEN (and AWS_PROFILE if needed)
docker compose up --build
```

Open http://localhost:8000. `.env` is excluded from the image by `.dockerignore`.

## Deploy to Amazon EKS

The steps below create, in your account:

- an ECR repository `code-change-agent` with the image,
- an IAM role `code-change-agent-bedrock` that can only invoke the configured Bedrock model,
- an EKS Pod Identity association from that role to the `code-change-agent` service account,
- the Secret `code-change-agent-secrets`, the service account, and two Deployments and Services: `code-change-agent` (runc) and `code-change-agent-gvisor` (gVisor).

### 1. Configure

```bash
cp .env.example .env     # set GITHUB_TOKEN; leave the AWS key lines commented out on EKS
aws eks update-kubeconfig --name <your-cluster> --region us-east-1
```

### 2. Push the image and set up IAM

```bash
CLUSTER=<your-cluster> REGION=us-east-1 scripts/setup-aws.sh
```

The script is safe to re-run. It prints the `IMAGE` value to use in the next steps. Environment variables and defaults:

| Variable | Default |
| --- | --- |
| `CLUSTER` | `sample-cluster` |
| `REGION` | `us-east-1` |
| `NAMESPACE` | `default` |
| `TAG` | `v1` |
| `MODEL_ID` | `global.anthropic.claude-sonnet-4-6` |

> Prefer IRSA over Pod Identity? Skip the association step, make the role trust your cluster's OIDC provider for `system:serviceaccount:<namespace>:code-change-agent`, and add the `eks.amazonaws.com/role-arn` annotation described in [`k8s/serviceaccount.yaml`](k8s/serviceaccount.yaml).

### 3. Install gVisor on the sandbox nodes (one-time)

```bash
scripts/deploy.sh setup-gvisor <node-name> [<node-name>...]   # or: --all
```

This labels the nodes `sandbox=gvisor` and applies [`k8s/gvisor/gvisor-installer.yaml`](k8s/gvisor/gvisor-installer.yaml), a privileged DaemonSet that downloads and checksums the latest gVisor release, installs `runsc` and `containerd-shim-runsc-v1`, registers the `runsc` runtime with containerd (1.x and 2.x configs are both handled) and restarts containerd once per node. Running pods survive the restart. The [`gvisor` RuntimeClass](k8s/gvisor/runtimeclass-gvisor.yaml) schedules pods only onto labelled nodes and accounts for the sandbox's own overhead (64Mi, 50m CPU).

To pin a gVisor version, change `RELEASE=latest` in the installer ConfigMap to a dated release.

### 4. Deploy

```bash
IMAGE=<account>.dkr.ecr.us-east-1.amazonaws.com/code-change-agent:v1 scripts/deploy.sh all
```

`deploy.sh` syncs the Secret from your shell and `.env`, applies the service account, deploys both variants, waits for the rollouts and, for the gVisor pod, checks `dmesg` to confirm it really runs under gVisor.

| Command | What it does |
| --- | --- |
| `all` (default) | Secret, service account, both deployments, status |
| `direct` | Only the runc deployment |
| `gvisor` | Only the gVisor deployment, its RuntimeClass and NetworkPolicy |
| `secret` | Only create or update the Secret |
| `setup-gvisor NODE... \| --all` | Label nodes and install gVisor |
| `status` | Deployments, pods, their runtime and node |
| `delete` | Remove both Deployments and Services (keeps Secret, service account and gVisor nodes) |

`deploy.sh` reads `NAMESPACE` (default `default`), `IMAGE`, `TIMEOUT` (default `180s`) and `ENV_FILE` (default `.env`). Run `scripts/deploy.sh --help` for the full text.

### 5. Open the UI

```bash
kubectl port-forward svc/code-change-agent 8000:80          # direct
kubectl port-forward svc/code-change-agent-gvisor 8001:80   # gVisor
```

> **Security:** the UI has no authentication and acts with your `GITHUB_TOKEN`. Keep the Services as `ClusterIP` and reach them with `port-forward`. Don't expose them through a public load balancer or Ingress.

### How secrets reach the pod

`deploy.sh` builds `code-change-agent-secrets` from exported shell variables first, then `.env` (the same precedence as `config.py`). Only these keys are copied: `AWS_REGION`, `MODEL_ID`, `GITHUB_TOKEN`, `GITHUB_API_URL` and, if set, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`. `AWS_PROFILE` is never copied, because a profile name means nothing inside a pod. Blank values are skipped.

The Secret is mounted read-only at `/etc/code-change-agent/secrets`, one file per key, and `config.py` reads them from there. Settings are read once at startup, so `deploy.sh` restarts the deployments whenever the Secret changes.

Don't create the Secret with `kubectl create secret --from-env-file=.env`: blank lines such as `AWS_PROFILE=` would become empty files. `config.py` ignores blank values, but `deploy.sh secret` is the supported path.

On a cluster without Pod Identity or IRSA, put `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` in `.env` and they will be copied into the Secret.

## Adapting to your cluster

Most values are parameters. The one file you must edit for a new cluster is [`k8s/gvisor/networkpolicy-gvisor.yaml`](k8s/gvisor/networkpolicy-gvisor.yaml), which has the CIDRs of the cluster it was written for:

| In the file | Meaning | Find yours with |
| --- | --- | --- |
| `172.31.0.0/16` | VPC CIDR (nodes, pods, API server ENIs) | `aws ec2 describe-vpcs --vpc-ids $(aws eks describe-cluster --name <cluster> --query cluster.resourcesVpcConfig.vpcId --output text) --query 'Vpcs[0].CidrBlockAssociationSet[].CidrBlock'` |
| `10.100.0.0/16` | Service CIDR | `aws eks describe-cluster --name <cluster> --query cluster.kubernetesNetworkConfig.serviceIpv4Cidr --output text` |
| `10.100.0.10/32` | kube-dns ClusterIP | `kubectl -n kube-system get svc kube-dns -o jsonpath='{.spec.clusterIP}'` |

If your VPC has more than one CIDR block, or your pods use custom networking with a secondary CIDR, add each one to the `except` list.

The policy is only enforced when the Amazon VPC CNI network policy agent is on. `deploy.sh` warns if it isn't. To turn it on:

```bash
aws eks update-addon --cluster-name <cluster> --addon-name vpc-cni \
  --configuration-values '{"enableNetworkPolicy":"true"}'
```

Other things to check:

- **Region and model.** Set `AWS_REGION` and `MODEL_ID` in `.env`, and pass the same `REGION` and `MODEL_ID` to `setup-aws.sh` so the IAM policy matches.
- **Namespace.** Pass the same `NAMESPACE` to `setup-aws.sh` and `deploy.sh`; the Pod Identity association is per namespace.
- **GitHub Enterprise Server.** `GITHUB_API_URL` controls where pull requests are opened. Cloning currently uses `github.com`.

## Configuration reference

Read by [`config.py`](config.py). Highest priority first: environment variables, `.env` in the working directory, files in `SECRETS_DIR`, then defaults. Blank values count as unset.

| Setting | Default | Description |
| --- | --- | --- |
| `AWS_REGION` | `us-east-1` | Region for Bedrock calls. |
| `MODEL_ID` | `global.anthropic.claude-sonnet-4-6` | Bedrock model or inference profile ID. |
| `GITHUB_TOKEN` | — | **Required.** Used to clone, push and open pull requests. |
| `GITHUB_API_URL` | `https://api.github.com` | GitHub REST API base URL. |
| `AWS_PROFILE` | — | Local only. Named profile for Bedrock. |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN` | — | Optional static credentials. Leave unset to use the default AWS chain (profile, `~/.aws`, Pod Identity or IRSA). |
| `SECRETS_DIR` | `/etc/code-change-agent/secrets` | Folder of one-file-per-setting secrets. Ignored if it doesn't exist. |

## HTTP API

The page uses two endpoints, which you can also call directly.

```bash
# start a run
curl -s -X POST localhost:8000/runs -H 'content-type: application/json' \
  -d '{"github_repo": "my-org/my-repo", "task": "Fix the typo in the README heading"}'
# {"id": "6f1c..."}

# stream its steps (server-sent events)
curl -N localhost:8000/runs/6f1c.../events
# data: {"type": "tool", "text": "clone_repo"}
# data: {"type": "tool", "text": "grep_files"}
# ...
# data: {"type": "done", "text": "Opened https://github.com/my-org/my-repo/pull/12"}
```

Event `type` is `tool` (the agent called a tool), `done` (final reply) or `error`. Runs are held in memory and removed once their stream has been read to the end.

## Troubleshooting

| Symptom | Likely cause and fix |
| --- | --- |
| `GITHUB_TOKEN is not set` | Set it in `.env` or the environment. On EKS, re-run `scripts/deploy.sh secret`. |
| `git clone failed` / `git push failed` with 403 | The token can't access the repo or lacks write access. Check its repository list and *Contents* permission. |
| `GitHub API error 422` | A pull request for that branch already exists, or the repo has no `main` branch. |
| `AccessDeniedException` from Bedrock | Model access not enabled in `AWS_REGION`, or the IAM role doesn't cover `MODEL_ID`. Re-run `setup-aws.sh` with the right `MODEL_ID`. |
| `Unable to locate credentials` in the pod | No Pod Identity association for this namespace and service account, or the Pod Identity Agent add-on is missing. Check `aws eks list-pod-identity-associations --cluster-name <cluster>`. |
| `ErrImagePull` / `ImagePullBackOff` | `IMAGE` wasn't set, so the pod tried `code-change-agent:latest`. Re-run with `IMAGE=...`. |
| gVisor pod stuck `Pending` | No nodes labelled `sandbox=gvisor`, or not enough room on them. Run `setup-gvisor`. |
| gVisor pod `ContainerCreating` with `no runtime for "runsc"` | The installer hasn't finished on that node. Check `kubectl -n gvisor-system logs -l app=gvisor-installer -c install`. |
| gVisor pod can't reach Bedrock or GitHub | NetworkPolicy CIDRs don't match your cluster, or DNS IP is wrong. See [Adapting to your cluster](#adapting-to-your-cluster). |
| gVisor pod can still reach the API server | Network policy enforcement is off in the VPC CNI. |
| Changed `.env` but the pod uses old values | Run `scripts/deploy.sh secret` followed by `kubectl rollout restart deploy/<name>`, or just `scripts/deploy.sh all`. |

## Clean up

Remove everything this sample created, in reverse order:

```bash
# workloads
scripts/deploy.sh delete
kubectl delete -f k8s/gvisor/networkpolicy-gvisor.yaml --ignore-not-found
kubectl delete secret code-change-agent-secrets --ignore-not-found
kubectl delete -f k8s/serviceaccount.yaml --ignore-not-found

# gVisor
kubectl delete -f k8s/gvisor/runtimeclass-gvisor.yaml --ignore-not-found
kubectl delete -f k8s/gvisor/gvisor-installer.yaml --ignore-not-found
kubectl label nodes -l sandbox=gvisor sandbox-

# AWS
ASSOC=$(aws eks list-pod-identity-associations --cluster-name <cluster> \
  --service-account code-change-agent --query 'associations[0].associationId' --output text)
aws eks delete-pod-identity-association --cluster-name <cluster> --association-id "$ASSOC"
aws iam delete-role-policy --role-name code-change-agent-bedrock --policy-name bedrock-invoke
aws iam delete-role --role-name code-change-agent-bedrock
aws ecr delete-repository --repository-name code-change-agent --force
```

Deleting the installer doesn't undo its changes on the nodes: `runsc` stays in `/usr/local/bin` and the runtime stays registered in `/etc/containerd/config.toml` (the original is saved as `config.toml.bak-gvisor`). The simplest way to get clean nodes is to replace them, for example by scaling the node group down and up or rolling it to a new launch template version.

Also delete any `agent/...` branches and pull requests the agent opened in your test repository, and revoke the GitHub token if you created it for this demo.
