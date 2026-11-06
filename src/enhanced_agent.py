"""Enhanced code-change agent with planning, security analysis, and test generation."""

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

import requests
from strands import Agent, tool
from strands.models import BedrockModel

from config import get_settings
from models import AgentEvent, EventType, FileChange

SYSTEM_PROMPT = """You are an expert software engineer that analyzes, improves, and fixes code.

Your workflow:
1. **Plan**: Start by calling plan_changes to think through the approach
2. **Clone**: Call clone_repo to get the code
3. **Analyze**: Use grep_files and read_file to understand the codebase
4. **Security**: Look for vulnerabilities (SQL injection, XSS, auth issues, etc.)
5. **Implement**: Make targeted changes with write_file
6. **Test**: Generate comprehensive tests to verify your changes
7. **Review**: Check your own changes for issues
8. **Commit**: Push with a clear commit message
9. **Document**: Open a PR with detailed description of what and why

Key principles:
- Think before acting - use plan_changes to outline your approach
- Make focused, atomic changes
- Always add or update tests
- Write clear commit messages and PR descriptions
- Consider edge cases and error handling
- Follow the existing code style
- Add comments for complex logic
- Look for security vulnerabilities
- Check for performance issues

When fixing security issues:
- Identify the vulnerability type and severity
- Fix the root cause, not just the symptom
- Add input validation and sanitization
- Use parameterized queries for SQL
- Escape output for XSS prevention
- Add rate limiting where appropriate
- Generate tests that verify the fix

Always write complete file contents, never partial updates."""

MAX_GREP_LINES = 500


def build_enhanced_tools(
    github_repo: str,
    token: str,
    api_url: str,
    workdir: Path,
    emit: Callable[[AgentEvent], None]
) -> list:
    """Build enhanced agent tools with better observability and capabilities."""
    repo = workdir / "repo"
    owner, _, repo_name = github_repo.partition("/")
    file_changes: list[FileChange] = []

    def git(*args: str, cwd: Path = repo) -> str:
        """Run git and return its output, with the token scrubbed."""
        result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
        output = (result.stdout + result.stderr).replace(token, "***").strip()
        if result.returncode != 0:
            raise RuntimeError(f"git {args[0]} failed: {output}")
        return output

    def safe_path(path: str) -> Path:
        """Validate path is inside repo."""
        full = (repo / path).resolve()
        if full != repo.resolve() and repo.resolve() not in full.parents:
            raise ValueError(f"{path} is outside the repository")
        return full

    def emit_event(event_type: EventType, text: str, metadata: dict | None = None):
        """Helper to emit events."""
        emit(AgentEvent(type=event_type, text=text, metadata=metadata or {}))

    @tool
    def plan_changes(analysis: str, approach: str, files_to_modify: list[str]) -> str:
        """Create a plan before making changes. Think through the approach.

        Args:
            analysis: Your understanding of the current code and what needs to change
            approach: Step-by-step plan for implementing the changes
            files_to_modify: List of files you expect to create or modify
        """
        plan = f"""## Analysis
{analysis}

## Approach
{approach}

## Files to Modify
{', '.join(files_to_modify)}"""

        emit_event(EventType.THINKING, plan)
        return "Plan recorded. Proceed with implementation."

    @tool
    def clone_repo() -> str:
        """Clone the GitHub repository. Call this after planning."""
        git("clone", f"https://{token}@github.com/{github_repo}.git", str(repo), cwd=workdir)
        emit_event(EventType.INFO, f"Cloned {github_repo}")
        return f"Cloned {github_repo}. Repository is ready at {repo}"

    @tool
    def read_file(path: str) -> str:
        """Read a file in the repository. If path is a folder, list files recursively.

        Args:
            path: Path relative to repository root. Use "." for root directory.
        """
        full = safe_path(path)
        if full.is_dir():
            files = []
            for p in sorted(full.rglob("*")):
                if p.is_file() and ".git" not in p.relative_to(repo).parts:
                    rel_path = str(p.relative_to(repo))
                    size = p.stat().st_size
                    files.append(f"{rel_path} ({size} bytes)")
            return "\n".join(files)

        content = full.read_text()
        emit_event(EventType.INFO, f"Read {path} ({len(content)} bytes)")
        return content

    @tool
    def grep_files(pattern: str, path: str = ".", file_pattern: str = "*") -> str:
        """Search file contents with regex. Returns file:line:text matches.

        Args:
            pattern: Extended regular expression to search for
            path: Directory to search (default: ".")
            file_pattern: Glob pattern for file names (default: "*", e.g., "*.py")
        """
        target = safe_path(path).relative_to(repo.resolve())
        cmd = ["git", "grep", "--untracked", "-n", "-I", "-E", "-e", pattern]

        if file_pattern != "*":
            cmd.extend(["--", str(target / file_pattern)])
        else:
            cmd.extend(["--", str(target)])

        result = subprocess.run(cmd, cwd=repo, capture_output=True, text=True)

        if result.returncode == 1:
            return "No matches found"
        if result.returncode != 0:
            return f"grep error: {result.stderr.strip()}"

        lines = result.stdout.splitlines()
        matches = len(lines)

        if matches > MAX_GREP_LINES:
            lines = lines[:MAX_GREP_LINES] + [
                f"... {matches - MAX_GREP_LINES} more matches (total: {matches})"
            ]

        emit_event(EventType.INFO, f"Found {matches} matches for '{pattern}'")
        return "\n".join(lines)

    @tool
    def analyze_security(path: str = ".") -> str:
        """Scan code for common security vulnerabilities.

        Args:
            path: Directory to scan (default: ".")
        """
        target = safe_path(path)
        issues = []

        # Common vulnerability patterns
        patterns = {
            "SQL Injection": [
                r'execute\([^,)]*%[^,)]*\)',  # String formatting in SQL
                r'executemany\([^,)]*%[^,)]*\)',
                r'\.format\([^)]*\).*execute',
                r'f".*SELECT.*\{.*\}"',  # f-strings in SQL
            ],
            "XSS": [
                r'innerHTML\s*=',
                r'document\.write\(',
                r'eval\(',
                r'<script>.*\{.*\}',  # Template injection
                r'render_template_string\(',  # Flask template injection
            ],
            "Path Traversal": [
                r'open\([^)]*\+[^)]*\)',  # Concatenation in file paths
                r'Path\([^)]*\+[^)]*\)',
                r'\.\./',  # Relative path traversal
            ],
            "Hardcoded Secrets": [
                r'password\s*=\s*["\'][^"\']+["\']',
                r'api[_-]?key\s*=\s*["\'][^"\']+["\']',
                r'secret\s*=\s*["\'][^"\']+["\']',
                r'token\s*=\s*["\'][^"\']+["\']',
            ],
            "Command Injection": [
                r'os\.system\(',
                r'subprocess\.call\([^)]*shell\s*=\s*True',
                r'eval\(',
                r'exec\(',
            ],
        }

        for vuln_type, vuln_patterns in patterns.items():
            for pattern in vuln_patterns:
                result = subprocess.run(
                    ["git", "grep", "-n", "-I", "-E", "-e", pattern, "--", str(target.relative_to(repo))],
                    cwd=repo,
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    matches = result.stdout.splitlines()
                    for match in matches[:10]:  # Limit to 10 per pattern
                        issues.append(f"⚠️  {vuln_type}: {match}")

        if not issues:
            return "✅ No obvious security vulnerabilities detected in common patterns"

        report = f"Found {len(issues)} potential security issues:\n\n" + "\n".join(issues)
        emit_event(EventType.INFO, f"Security scan: {len(issues)} potential issues found")
        return report

    @tool
    def write_file(path: str, content: str, reason: str = "") -> str:
        """Write complete file content. Creates file and directories if needed.

        Args:
            path: File path relative to repository root
            content: Complete new file content
            reason: Brief description of what changed and why
        """
        full = safe_path(path)
        existed = full.exists()
        old_content = full.read_text() if existed else ""

        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)

        # Compute diff
        if existed:
            action = "modified"
            # Simple line-based diff
            old_lines = old_content.splitlines()
            new_lines = content.splitlines()
            added = len([l for l in new_lines if l not in old_lines])
            removed = len([l for l in old_lines if l not in new_lines])
        else:
            action = "created"
            added = len(content.splitlines())
            removed = 0

        change = FileChange(
            path=path,
            action=action,
            lines_added=added,
            lines_removed=removed
        )
        file_changes.append(change)

        msg = f"{action.capitalize()} {path}"
        if reason:
            msg += f": {reason}"

        emit_event(EventType.FILE_CHANGE, msg, metadata={
            "path": path,
            "action": action,
            "lines_added": added,
            "lines_removed": removed
        })

        return f"✅ {msg}"

    @tool
    def run_tests(test_command: str = "pytest") -> str:
        """Run tests to verify changes work correctly.

        Args:
            test_command: Command to run tests (default: "pytest")
        """
        emit_event(EventType.INFO, f"Running tests: {test_command}")

        result = subprocess.run(
            test_command.split(),
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=60
        )

        output = result.stdout + result.stderr
        success = result.returncode == 0

        status = "✅ Tests passed" if success else "❌ Tests failed"
        emit_event(EventType.INFO, status)

        return f"{status}\n\n{output}"

    @tool
    def generate_diff() -> str:
        """Generate a git diff of all changes made so far."""
        result = subprocess.run(
            ["git", "diff", "--cached"],
            cwd=repo,
            capture_output=True,
            text=True
        )

        if not result.stdout.strip():
            # Nothing staged, show unstaged changes
            result = subprocess.run(
                ["git", "diff"],
                cwd=repo,
                capture_output=True,
                text=True
            )

        diff = result.stdout
        if diff:
            emit_event(EventType.DIFF, diff)
        return diff or "No changes to show"

    @tool
    def push_branch(branch: str, message: str) -> str:
        """Create branch, commit all changes, and push to origin.

        Args:
            branch: Branch name (e.g., "agent/fix-sql-injection")
            message: Commit message. Should explain what and why.
        """
        git("checkout", "-B", branch)
        git("add", "-A")

        # Generate commit message with file summary
        summary = f"{message}\n\nFiles changed:\n"
        for change in file_changes:
            summary += f"- {change.action}: {change.path}"
            if change.lines_added or change.lines_removed:
                summary += f" (+{change.lines_added}/-{change.lines_removed})"
            summary += "\n"

        git(
            "-c", "user.name=code-change-agent",
            "-c", "user.email=code-change-agent@users.noreply.github.com",
            "commit", "-m", summary
        )
        git("push", "-u", "origin", branch)

        emit_event(EventType.INFO, f"✅ Pushed branch: {branch}")
        return f"✅ Pushed {branch} with {len(file_changes)} file changes"

    @tool
    def create_pull_request(title: str, body: str, head: str, base: str = "main") -> str:
        """Open a pull request on GitHub.

        Args:
            title: PR title - clear and concise
            body: PR description - explain what, why, and how to test
            head: Branch with changes (already pushed)
            base: Target branch (default: "main")
        """
        # Enhance PR body with file changes summary
        enhanced_body = f"""{body}

## Changes Made

"""
        for change in file_changes:
            icon = "✨" if change.action == "created" else "✏️"
            enhanced_body += f"- {icon} **{change.path}** ({change.action})"
            if change.lines_added or change.lines_removed:
                enhanced_body += f" `+{change.lines_added}/-{change.lines_removed}`"
            enhanced_body += "\n"

        enhanced_body += "\n## Testing\n\nPlease review the changes and run the test suite to verify functionality."

        response = requests.post(
            f"{api_url}/repos/{owner}/{repo_name}/pulls",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
            json={"title": title, "body": enhanced_body, "head": head, "base": base},
            timeout=30,
        )

        if not response.ok:
            return f"❌ GitHub API error {response.status_code}: {response.text}"

        pr_url = response.json().get("html_url", "")
        emit_event(EventType.INFO, f"✅ Opened PR: {pr_url}")
        return pr_url

    return [
        plan_changes,
        clone_repo,
        read_file,
        grep_files,
        analyze_security,
        write_file,
        run_tests,
        generate_diff,
        push_branch,
        create_pull_request,
    ]


def run_enhanced_agent(
    github_repo: str,
    task: str,
    emit: Callable[[AgentEvent], None]
) -> str:
    """Run enhanced agent with better capabilities and observability."""
    settings = get_settings()
    if settings.github_token is None:
        raise RuntimeError("GITHUB_TOKEN is not set")
    token = settings.github_token.get_secret_value()

    seen_tools: set[str] = set()

    def on_event(**kwargs):
        """Track tool calls."""
        tool_use = kwargs.get("current_tool_use") or {}
        tool_id = tool_use.get("toolUseId")
        tool_name = tool_use.get("name", "unknown")

        if tool_id and tool_id not in seen_tools:
            seen_tools.add(tool_id)
            emit(AgentEvent(
                type=EventType.TOOL,
                text=tool_name,
                metadata={"tool": tool_name}
            ))

    workdir = Path(tempfile.mkdtemp(prefix="code-change-agent-"))
    try:
        agent = Agent(
            model=BedrockModel(
                model_id=settings.model_id,
                boto_session=settings.boto_session()
            ),
            system_prompt=SYSTEM_PROMPT,
            tools=build_enhanced_tools(github_repo, token, settings.github_api_url, workdir, emit),
            callback_handler=on_event,
        )

        result = agent(f"""GitHub repository: {github_repo}

Task: {task}

Remember to:
1. Plan your approach first
2. Analyze for security issues
3. Make focused changes
4. Add/update tests
5. Review your changes
6. Write clear PR description""")

        return str(result).strip()
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
