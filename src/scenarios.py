"""Pre-configured demo scenarios showcasing agent capabilities."""

from models import DemoScenario

DEMO_SCENARIOS = [
    DemoScenario(
        id="sql-injection-fix",
        name="Fix SQL Injection Vulnerability",
        description="Detect and fix a SQL injection vulnerability using parameterized queries",
        repo="Cloud-Tech-AI/vulnerable-flask-app",
        task=(
            "Find and fix the SQL injection vulnerability in the user login endpoint. "
            "Replace string concatenation with parameterized queries. Add input validation. "
            "Generate a unit test that verifies the fix prevents SQL injection attacks."
        ),
        category="security",
        estimated_duration="3-4 minutes",
        difficulty="medium"
    ),
    DemoScenario(
        id="xss-prevention",
        name="Fix XSS Vulnerability",
        description="Identify and fix Cross-Site Scripting (XSS) vulnerabilities",
        repo="Cloud-Tech-AI/vulnerable-flask-app",
        task=(
            "Find XSS vulnerabilities where user input is rendered without escaping. "
            "Add proper output encoding using Jinja2 auto-escaping or explicit escaping. "
            "Add CSP headers. Generate tests that verify XSS payloads are neutralized."
        ),
        category="security",
        estimated_duration="2-3 minutes",
        difficulty="easy"
    ),
    DemoScenario(
        id="api-rate-limiting",
        name="Add Rate Limiting to API",
        description="Implement rate limiting to prevent API abuse",
        repo="Cloud-Tech-AI/demo-api",
        task=(
            "Add rate limiting middleware to the API. Implement token bucket algorithm. "
            "Add rate limit headers (X-RateLimit-*). Configure different limits for "
            "authenticated vs anonymous users. Add tests verifying rate limits work."
        ),
        category="security",
        estimated_duration="4-5 minutes",
        difficulty="hard"
    ),
    DemoScenario(
        id="async-optimization",
        name="Convert Sync Code to Async",
        description="Refactor synchronous I/O operations to async for better performance",
        repo="Cloud-Tech-AI/demo-api",
        task=(
            "Find synchronous I/O operations (database queries, HTTP requests). "
            "Convert them to async/await using aiohttp and asyncpg. "
            "Update route handlers to async. Add benchmarks showing performance improvement."
        ),
        category="performance",
        estimated_duration="5-6 minutes",
        difficulty="hard"
    ),
    DemoScenario(
        id="test-generation",
        name="Generate Comprehensive Test Suite",
        description="Auto-generate unit and integration tests for untested code",
        repo="Cloud-Tech-AI/demo-application",
        task=(
            "Analyze the codebase and identify functions without tests. "
            "Generate pytest unit tests with fixtures, mocks, and edge cases. "
            "Add integration tests for API endpoints. Aim for 80%+ coverage. "
            "Use property-based testing with Hypothesis where appropriate."
        ),
        category="testing",
        estimated_duration="4-5 minutes",
        difficulty="medium"
    ),
    DemoScenario(
        id="error-handling",
        name="Add Robust Error Handling",
        description="Improve error handling and add proper logging",
        repo="Cloud-Tech-AI/demo-api",
        task=(
            "Add try-except blocks around error-prone operations. "
            "Replace generic exceptions with specific error types. "
            "Add structured logging with context (user_id, request_id). "
            "Add error monitoring with Sentry integration. "
            "Return proper HTTP status codes and error messages."
        ),
        category="refactoring",
        estimated_duration="3-4 minutes",
        difficulty="medium"
    ),
    DemoScenario(
        id="docker-optimization",
        name="Optimize Docker Build",
        description="Reduce Docker image size and improve build caching",
        repo="Cloud-Tech-AI/demo-application",
        task=(
            "Analyze the Dockerfile for optimization opportunities. "
            "Use multi-stage builds. Add proper layer caching. "
            "Use .dockerignore effectively. Switch to alpine base if possible. "
            "Remove unnecessary dependencies. Document the size reduction achieved."
        ),
        category="performance",
        estimated_duration="2-3 minutes",
        difficulty="easy"
    ),
    DemoScenario(
        id="api-documentation",
        name="Generate API Documentation",
        description="Auto-generate OpenAPI/Swagger documentation from code",
        repo="Cloud-Tech-AI/demo-api",
        task=(
            "Add FastAPI/OpenAPI documentation for all endpoints. "
            "Include request/response schemas with examples. "
            "Add description, tags, and proper HTTP status codes. "
            "Generate Markdown API docs from the OpenAPI spec. "
            "Add authentication documentation."
        ),
        category="refactoring",
        estimated_duration="3-4 minutes",
        difficulty="easy"
    ),
    DemoScenario(
        id="dead-code-removal",
        name="Remove Dead Code",
        description="Identify and remove unused code, imports, and dependencies",
        repo="Cloud-Tech-AI/demo-application",
        task=(
            "Use static analysis to find unused imports, functions, and classes. "
            "Remove commented-out code. "
            "Identify unused dependencies in requirements.txt. "
            "Clean up unreachable code paths. "
            "Document what was removed and why."
        ),
        category="refactoring",
        estimated_duration="2-3 minutes",
        difficulty="easy"
    ),
    DemoScenario(
        id="security-headers",
        name="Add Security Headers",
        description="Implement security best practices with HTTP headers",
        repo="Cloud-Tech-AI/demo-api",
        task=(
            "Add security headers: HSTS, X-Frame-Options, X-Content-Type-Options, "
            "CSP, Referrer-Policy, Permissions-Policy. "
            "Use secure cookie flags (Secure, HttpOnly, SameSite). "
            "Add CORS configuration. "
            "Generate tests verifying headers are present. "
            "Run security scan to verify A+ rating."
        ),
        category="security",
        estimated_duration="2-3 minutes",
        difficulty="easy"
    ),
]


def get_scenario(scenario_id: str) -> DemoScenario | None:
    """Get a scenario by ID."""
    return next((s for s in DEMO_SCENARIOS if s.id == scenario_id), None)


def get_scenarios_by_category(category: str) -> list[DemoScenario]:
    """Get all scenarios in a category."""
    return [s for s in DEMO_SCENARIOS if s.category == category]


def get_all_scenarios() -> list[DemoScenario]:
    """Get all available scenarios."""
    return DEMO_SCENARIOS
