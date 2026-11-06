"""The code-change agent.

Six plain tools: clone, read, grep, write, push, and open a pull request.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

import requests
from strands import Agent, tool
from strands.models import BedrockModel

from config import get_settings

SYSTEM_PROMPT = """You change code in a GitHub repository and open a pull request for the change.
Follow these steps in order:
1. Call clone_repo.
2. Find and read the files you need with grep_files and read_file.
3. Make the requested change with write_file. Keep the change small and focused.
   Always write the complete file content.
4. Call push_branch with a branch named agent/<short-task-slug> and a commit message.
5. Open a pull request with create_pull_request. Use the pushed branch as the head
   and main as the base. Write a clear title and description.
Reply with the pull request URL when you are done."""

MAX_GREP_LINES = 200


def build_tools(github_repo: str, token: str, api_url: str, workdir: Path) -> list:
    """All agent tools, scoped to one GitHub repo cloned into workdir."""
    repo = workdir / "repo"
    owner, _, repo_name = github_repo.partition("/")

    def git(*args: str, cwd: Path = repo) -> str:
        """Run git and return its output, with the token scrubbed. Raises on failure."""
        result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
        output = (result.stdout + result.stderr).replace(token, "***").strip()
        if result.returncode != 0:
            raise RuntimeError(f"git {args[0]} failed: {output}")
        return output

    def safe_path(path: str) -> Path:
        full = (repo / path).resolve()
        if full != repo.resolve() and repo.resolve() not in full.parents:
            raise ValueError(f"{path} is outside the repository")
        return full

    @tool
    def clone_repo() -> str:
        """Clone the GitHub repository. Call this first."""
        git("clone", f"https://{token}@github.com/{github_repo}.git", str(repo), cwd=workdir)
        return f"cloned {github_repo}"

    @tool
    def read_file(path: str) -> str:
        """Read a file in the repository. If path is a folder, list the files in it instead.

        Args:
            path: Path relative to the repository root. Use "." for the root folder.
        """
        full = safe_path(path)
        if full.is_dir():
            return "\n".join(
                sorted(
                    str(p.relative_to(repo))
                    for p in full.rglob("*")
                    if p.is_file() and ".git" not in p.relative_to(repo).parts
                )
            )
        return full.read_text()

    @tool
    def grep_files(pattern: str, path: str = ".") -> str:
        """Search file contents with a regular expression. Returns file:line:text matches.

        Args:
            pattern: Extended regular expression to search for.
            path: File or folder to search, relative to the repository root. Defaults to everything.
        """
        target = safe_path(path).relative_to(repo.resolve())
        result = subprocess.run(
            ["git", "grep", "--untracked", "-n", "-I", "-E", "-e", pattern, "--", str(target)],
            cwd=repo,
            capture_output=True,
            text=True,
        )
        if result.returncode == 1:
            return "no matches"
        if result.returncode != 0:
            return f"grep error: {result.stderr.strip()}"
        lines = result.stdout.splitlines()
        if len(lines) > MAX_GREP_LINES:
            lines = lines[:MAX_GREP_LINES] + [f"... truncated, {len(lines)} matches in total"]
        return "\n".join(lines)

    @tool
    def write_file(path: str, content: str) -> str:
        """Write the complete new content of a file in the repository. Creates the file if needed.

        Args:
            path: File path relative to the repository root.
            content: The full new content of the file.
        """
        full = safe_path(path)
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)
        return f"wrote {path}"

    @tool
    def push_branch(branch: str, message: str) -> str:
        """Create a branch, commit every change in the repository and push it to origin.

        Args:
            branch: Name of the new branch, for example agent/add-version-endpoint.
            message: Commit message.
        """
        git("checkout", "-B", branch)
        git("add", "-A")
        git(
            "-c", "user.name=code-change-agent",
            "-c", "user.email=code-change-agent@users.noreply.github.com",
            "commit", "-m", message,
        )
        git("push", "-u", "origin", branch)
        return f"pushed {branch}"

    @tool
    def create_pull_request(title: str, body: str, head: str, base: str = "main") -> str:
        """Open a pull request on GitHub.

        Args:
            title: Pull request title.
            body: Pull request description.
            head: Branch containing the change (already pushed to origin).
            base: Branch to merge into. Defaults to main.
        """
        response = requests.post(
            f"{api_url}/repos/{owner}/{repo_name}/pulls",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
            json={"title": title, "body": body, "head": head, "base": base},
            timeout=30,
        )
        if not response.ok:
            return f"GitHub API error {response.status_code}: {response.text}"
        return response.json().get("html_url", "pull request created, but no URL was returned")

    return [clone_repo, read_file, grep_files, write_file, push_branch, create_pull_request]


def run_agent(github_repo: str, task: str, emit: Callable[[dict], None]) -> str:
    """Run the agent on one task. Calls emit() with each step. Returns the agent's final reply."""
    settings = get_settings()
    if settings.github_token is None:
        raise RuntimeError("GITHUB_TOKEN is not set")
    token = settings.github_token.get_secret_value()

    seen_tools: set[str] = set()

    def on_event(**kwargs):
        tool_use = kwargs.get("current_tool_use") or {}
        tool_id = tool_use.get("toolUseId")
        if tool_id and tool_id not in seen_tools:
            seen_tools.add(tool_id)
            emit({"type": "tool", "text": tool_use.get("name", "unknown")})

    workdir = Path(tempfile.mkdtemp(prefix="code-change-agent-"))
    try:
        agent = Agent(
            model=BedrockModel(model_id=settings.model_id, boto_session=settings.boto_session()),
            system_prompt=SYSTEM_PROMPT,
            tools=build_tools(github_repo, token, settings.github_api_url, workdir),
            callback_handler=on_event,
        )
        result = agent(f"GitHub repository: {github_repo}\nTask: {task}")
        return str(result).strip()
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
