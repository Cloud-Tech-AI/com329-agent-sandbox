# Security

## Reporting a vulnerability

If you find a security issue in this repository, please **do not** open a public GitHub issue. Instead, report it privately using [GitHub private vulnerability reporting](https://github.com/Cloud-Tech-AI/com329-agent-sandbox/security/advisories/new).

Include a description of the issue, steps to reproduce, and its impact. We will acknowledge your report and keep you updated on the fix.

If you believe you have found a vulnerability in an AWS service, report it to [AWS Security](https://aws.amazon.com/security/vulnerability-reporting/). For gVisor itself, follow the [gVisor security policy](https://github.com/google/gvisor/security/policy).

## Scope and known limitations

This is sample code for a conference session. It demonstrates isolation techniques and is **not** hardened for production. By design:

- The web UI and HTTP API have **no authentication**. Anyone who can reach them can make the agent act with the configured `GITHUB_TOKEN`. Expose them only through `kubectl port-forward`.
- The agent follows natural-language instructions and reads content from the repositories it clones, so it is exposed to prompt injection. The gVisor sandbox and `NetworkPolicy` limit what a misled agent can reach; they don't stop it from misusing the GitHub token it holds. Use a fine-grained token limited to a test repository.
- The direct (`runc`) deployment is deliberately *not* sandboxed, as the baseline for comparison.
- The gVisor installer is a privileged DaemonSet with host access. Only label nodes you dedicate to sandboxed workloads.

Reports about these documented limitations are still welcome if you can show a practical improvement.
