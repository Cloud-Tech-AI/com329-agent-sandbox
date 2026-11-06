# Contributing

Thanks for your interest in improving this sample. Bug reports, fixes, documentation improvements and ideas are all welcome.

## Reporting bugs and asking for features

Open a [GitHub issue](https://github.com/Cloud-Tech-AI/com329-agent-sandbox/issues) using one of the templates. For bugs, include:

- what you ran (commands, and which deployment: local, Docker, direct or gVisor),
- what you expected and what happened, with logs (`kubectl logs`, `kubectl describe pod`),
- your environment: EKS version, node OS and AMI, containerd version, gVisor release, AWS region and `MODEL_ID`.

Please search existing issues first. **Do not** open a public issue for a security problem; see [SECURITY.md](SECURITY.md).

## Pull requests

1. Fork the repository and create a branch from `main`.
2. Keep each pull request focused on one change.
3. Test what you changed:
   - Python: run the agent locally (`uvicorn server:app --reload`) and complete one run end to end against a test repository.
   - Kubernetes manifests and scripts: deploy with `scripts/deploy.sh` to a test cluster and check `scripts/deploy.sh status`. Run `shellcheck` on any script you touch.
   - Documentation: check that commands and links work.
4. Never commit secrets. `.env` is git-ignored; keep it that way, and use placeholders such as `<ACCOUNT_ID>` and `ghp-xxxx` in examples.
5. Describe what changed and why, and how you tested it, in the pull request.

## Style

- Python: follow the existing style; small, typed functions with docstrings that the model can read as tool descriptions.
- YAML: comment *why* a setting is there, as the existing manifests do.
- Docs: short sentences, commands that can be copied and run.

## License

By contributing, you agree that your contributions are licensed under the [MIT License](LICENSE) of this repository.
