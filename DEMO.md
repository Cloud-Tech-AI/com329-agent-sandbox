# Demo: an AI agent pod on runc vs gVisor

The same code-change agent runs twice on EKS. First as a normal pod (runc), then in a gVisor sandbox. Inside each pod you run the commands an agent's shell tool could run, and compare what each pod can reach. Both agents fix a bug in [Cloud-Tech-AI/demo-application](https://github.com/Cloud-Tech-AI/demo-application) and open a PR.

Run everything from `~/workspace/com329-agent-sandbox`. Use two terminals: **T1** for the main flow, **T2** for port-forward / proxy.

---

## Before you start

1. The cluster is clean (see [Reset](#reset)). This should print `No resources found`:

   ```bash
   kubectl get deploy,runtimeclass
   ```

2. The GitHub token is in `.env` and in the cluster Secret:

   ```bash
   scripts/deploy.sh secret
   ```

3. Set these variables in **T1**:

   ```bash
   export REGISTRY=595786915976.dkr.ecr.us-east-1.amazonaws.com
   export IMAGE=$REGISTRY/code-change-agent:demo
   export GVISOR_NODE=ip-172-31-81-202.ec2.internal
   ```

---

## 1. Show the cluster

```bash
kubectl get nodes -L node.kubernetes.io/instance-type,topology.kubernetes.io/zone
kubectl get runtimeclass
```

Expected: 3 `t3.small` nodes in 3 AZs, and `No resources found` for runtimeclass. Every pod shares the host kernel.

---

## 2. Build the container locally and push to ECR

```bash
docker build -t $IMAGE .
```

```bash
CFG=$(mktemp -d) && echo '{}' > $CFG/config.json
aws ecr get-login-password --region us-east-1 | docker --config $CFG login -u AWS --password-stdin $REGISTRY
DOCKER_HOST="$(docker context inspect --format '{{.Endpoints.docker.Host}}')" docker --config $CFG push $IMAGE
rm -rf $CFG
```

The temporary `--config` avoids Docker's credential-store prompt.

---

## 3. Deploy the agent (runc)

```bash
sed "s|image: code-change-agent:latest|image: $IMAGE|" k8s/deployment.yaml | kubectl apply -f -
kubectl rollout status deploy/code-change-agent
```

---

## 4. Exec in and see what an agent can reach

```bash
kubectl exec -it deploy/code-change-agent -c code-change-agent -- bash
```

Inside the pod:

```bash
uname -r
ls /var/run/secrets/kubernetes.io/serviceaccount/
TOKEN=$(cat /var/run/secrets/kubernetes.io/serviceaccount/token)
curl -sk -H "Authorization: Bearer $TOKEN" https://kubernetes.default.svc/version
curl -sk -H "Authorization: Bearer $TOKEN" https://kubernetes.default.svc/apis | grep '"name"'
curl -sk -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  https://kubernetes.default.svc/apis/authentication.k8s.io/v1/selfsubjectreviews \
  -d '{"apiVersion":"authentication.k8s.io/v1","kind":"SelfSubjectReview"}' | grep -A1 -E 'username|node-name'
exit
```

Expected:
- the host kernel, `6.18.56-...amzn2023`
- `ca.crt namespace token`: a live Kubernetes credential on disk
- the cluster version (`v1.37.1-eks-...`) and the list of API groups
- the pod's identity, `system:serviceaccount:default:code-change-agent`, and the node it runs on

> Talking point: RBAC still blocks secrets and nodes (403). But the agent has a token, a network path to the control plane and the host kernel. That's one RBAC mistake or one kernel CVE away from much more.

---

## 5. Port-forward and run the agent (runc)

**T2:**

```bash
kubectl port-forward svc/code-change-agent 8000:80
```

**T1:**

```bash
ID=$(curl -s -X POST localhost:8000/runs -H 'Content-Type: application/json' \
  -d '{"github_repo":"Cloud-Tech-AI/demo-application","task":"The Order Now button on the homepage is invisible until hovered. Fix it and open a PR."}' \
  | grep -o '"id":"[^"]*"' | cut -d'"' -f4)
curl -sN localhost:8000/runs/$ID/events
```

Expected: tool calls stream in (`clone_repo`, `read_file`, `write_file`, `push_branch`, `create_pull_request`), then the PR URL. It takes about 1–2 minutes. You can also use the UI at http://localhost:8000.

Stop the port-forward in T2 with Ctrl-C.

---

## 6. Install gVisor

```bash
kubectl label node $GVISOR_NODE sandbox=gvisor --overwrite
kubectl apply -f k8s/gvisor/gvisor-installer.yaml -f k8s/gvisor/runtimeclass-gvisor.yaml
kubectl -n gvisor-system rollout status ds/gvisor-installer
kubectl -n gvisor-system logs -l app=gvisor-installer -c install
kubectl get runtimeclass
```

The installer is a privileged DaemonSet. It installs `runsc` on the labelled node and registers it with containerd. Because `runsc` is already on this node, the log says `runsc already registered`. That is expected.

---

## 7. Deploy the gVisor pod

Same image, with three differences: `runtimeClassName: gvisor`, `automountServiceAccountToken: false`, and a NetworkPolicy.

```bash
kubectl apply -f k8s/gvisor/networkpolicy-gvisor.yaml
sed "s|image: code-change-agent:latest|image: $IMAGE|" k8s/deployment-gvisor.yaml | kubectl apply -f -
kubectl rollout status deploy/code-change-agent-gvisor
kubectl get pods -o custom-columns='POD:.metadata.name,RUNTIME:.spec.runtimeClassName,NODE:.spec.nodeName'
```

---

## 8. Exec in and run the same commands (gVisor)

```bash
kubectl exec -it deploy/code-change-agent-gvisor -c code-change-agent -- bash
```

Inside the pod:

```bash
uname -r
dmesg | head -3
ls /var/run/secrets/kubernetes.io/serviceaccount/
curl -sSk -m 5 https://kubernetes.default.svc/version
curl -sS -m 5 -o /dev/null -w "%{http_code}\n" http://code-change-agent.default.svc/
curl -s -m 5 -o /dev/null -w "%{http_code}\n" https://api.github.com
exit
```

Expected:
- `4.19.0-gvisor` and `Starting gVisor...`: the pod talks to gVisor's kernel, not the host's
- `No such file or directory`: no token
- `curl: (28) Connection timed out` for the API server and for the other pod
- `200` for GitHub: the agent can still do its job

> Talking point: gVisor gives the kernel isolation. The missing token and the blocked network come from `automountServiceAccountToken: false` and the NetworkPolicy. Together they give three boundaries: kernel, identity and network.

---

## 9. Reach the gVisor pod and run the agent

`kubectl port-forward` does not work with gVisor (`lost connection to pod`), because gVisor has its own network stack. Use `kubectl proxy` instead.

**T2:**

```bash
kubectl proxy --port=8001
```

**T1:**

```bash
GV=localhost:8001/api/v1/namespaces/default/services/code-change-agent-gvisor:80/proxy
ID=$(curl -s -X POST $GV/runs -H 'Content-Type: application/json' \
  -d '{"github_repo":"Cloud-Tech-AI/demo-application","task":"Prices do not show on the menu cards. Fix it and open a PR."}' \
  | grep -o '"id":"[^"]*"' | cut -d'"' -f4)
curl -sN $GV/runs/$ID/events
```

Expected: the same tool calls, then a second PR URL. The sandboxed agent still works.
UI: http://localhost:8001/api/v1/namespaces/default/services/code-change-agent-gvisor:80/proxy/ (keep the trailing slash).

---

## 10. Side by side

```bash
for d in code-change-agent code-change-agent-gvisor; do
  echo "== $d"; kubectl exec deploy/$d -c code-change-agent -- sh -c \
    'uname -r; T=$(cat /var/run/secrets/kubernetes.io/serviceaccount/token 2>/dev/null) && echo "token: found" || echo "token: none"; curl -sk -m 3 -o /dev/null -w "api-server: %{http_code}\n" -H "Authorization: Bearer $T" https://kubernetes.default.svc/version'
done
```

Expected: the runc pod shows the host kernel, `token: found` and `api-server: 200`. The gVisor pod shows `4.19.0-gvisor`, `token: none` and `api-server: 000`.

---

## Reset

Run this before each rehearsal and before going live.

**Cluster.** This keeps the Secret and the ServiceAccount:

```bash
kubectl delete -f k8s/deployment.yaml -f k8s/deployment-gvisor.yaml -f k8s/gvisor/networkpolicy-gvisor.yaml --ignore-not-found
kubectl delete -f k8s/gvisor/gvisor-installer.yaml -f k8s/gvisor/runtimeclass-gvisor.yaml --ignore-not-found
kubectl label nodes --all sandbox-
```

**PRs.** Close the agent's PRs and delete their branches. Otherwise the next run can fail to push to a branch name that already exists:

```bash
T=$(grep '^GITHUB_TOKEN=' .env | cut -d= -f2-); API=https://api.github.com/repos/Cloud-Tech-AI/demo-application
for n in $(curl -s "$API/pulls?state=open" | grep -oE '"number": *[0-9]+' | grep -oE '[0-9]+'); do
  BR=$(curl -s $API/pulls/$n | grep -oE '"ref": *"agent/[^"]*"' | head -1 | cut -d'"' -f4)
  [ -n "$BR" ] && curl -s -o /dev/null -X PATCH -H "Authorization: Bearer $T" $API/pulls/$n -d '{"state":"closed"}' \
    && curl -s -o /dev/null -X DELETE -H "Authorization: Bearer $T" $API/git/refs/heads/$BR && echo "closed #$n, deleted $BR"
done
```

**Rotating the GitHub token.** Edit `GITHUB_TOKEN` in `.env`. New terminals pick it up through `~/.bashrc`. Then update the cluster, and clear git's old credential:

```bash
scripts/deploy.sh secret
printf 'protocol=https\nhost=github.com\n\n' | git credential reject
```

The next `git push` asks for your login. Use `ishan-modi` as the username and the token as the password.

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| Pod `Pending`: `Too many pods` | The t3.small nodes are full (11 pods each). Delete an old pod. |
| gVisor pod `Pending`: `didn't match node selector` | Run `kubectl label node $GVISOR_NODE sandbox=gvisor` |
| `ImagePullBackOff` | `$IMAGE` isn't set in this terminal, or the push didn't finish |
| The agent says it can't push or open the PR | The token in the Secret can't write to the repo. Update `.env`, then run `scripts/deploy.sh secret` and `kubectl rollout restart deploy/code-change-agent deploy/code-change-agent-gvisor` |
| `docker push` asks for `pass` | Use the `--config $CFG` lines from step 2 exactly as written |
