# Development Branch: Next-Level Demo

This branch contains significant enhancements to transform the basic code-change agent into a production-quality demonstration with modern UI and advanced capabilities.

## 🚀 What's New

### 1. **Modern React Frontend** (`frontend/`)
- **Tech Stack**: React 18 + TypeScript + Vite + Tailwind CSS
- **Features**:
  - Real-time event streaming with Server-Sent Events
  - Side-by-side runtime comparison (runc vs gVisor)
  - Syntax-highlighted code diffs
  - Pre-loaded demo scenarios with filtering
  - Responsive design with dark mode support
  - Live metrics dashboard
  - Event log with color-coded event types

### 2. **Enhanced Agent Capabilities** (`src/enhanced_agent.py`)
New tools and features:
- **`plan_changes`**: Strategic planning before execution
- **`analyze_security`**: Automatic vulnerability scanning for:
  - SQL Injection
  - XSS (Cross-Site Scripting)
  - Path Traversal
  - Hardcoded Secrets
  - Command Injection
- **`run_tests`**: Execute test suites to verify changes
- **`generate_diff`**: Show git diffs before committing
- **Enhanced file tracking**: Line-by-line change metrics
- **Better observability**: Structured events with metadata

### 3. **Production-Ready Server** (`src/enhanced_server.py`)
- **RESTful API** with proper error handling
- **Metrics tracking**: Duration, files changed, tools used, errors
- **Scenario library**: 10 pre-configured demo scenarios
- **Health check endpoint**: `/health`
- **CORS support**: For development
- **Static file serving**: Serves built frontend

### 4. **Demo Scenario Library** (`src/scenarios.py`)
10 ready-to-run scenarios across categories:

#### Security (4 scenarios)
- **SQL Injection Fix**: Parameterized queries + input validation
- **XSS Prevention**: Output encoding + CSP headers
- **API Rate Limiting**: Token bucket algorithm
- **Security Headers**: HSTS, CSP, frame options, etc.

#### Testing (1 scenario)
- **Test Generation**: Auto-generate pytest suite with fixtures

#### Performance (3 scenarios)
- **Async Optimization**: Convert sync I/O to async
- **Docker Optimization**: Multi-stage builds, alpine base
- **Dead Code Removal**: Static analysis cleanup

#### Refactoring (2 scenarios)
- **API Documentation**: OpenAPI/Swagger generation
- **Error Handling**: Structured logging + monitoring

### 5. **Type Safety** (`src/models.py`)
- Pydantic models for all data structures
- Event types enumeration
- Runtime selection support
- Metrics tracking models

## 📁 New Project Structure

```
.
├── frontend/                      # React + TypeScript frontend
│   ├── src/
│   │   ├── components/           # React components
│   │   │   ├── EventLog.tsx     # Real-time event display
│   │   │   ├── ScenarioCard.tsx # Scenario selector
│   │   │   └── MetricsPanel.tsx # Metrics dashboard
│   │   ├── hooks/
│   │   │   └── useAgentRun.ts   # Custom hook for agent runs
│   │   ├── lib/
│   │   │   ├── api.ts           # API client
│   │   │   └── utils.ts         # Utility functions
│   │   ├── types/               # TypeScript types
│   │   ├── App.tsx              # Main application
│   │   └── main.tsx             # Entry point
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── tsconfig.json
├── src/
│   ├── enhanced_agent.py         # Enhanced agent with 10 tools
│   ├── enhanced_server.py        # Production server
│   ├── models.py                 # Pydantic data models
│   ├── scenarios.py              # Demo scenario library
│   ├── agent.py                  # Original agent (kept for comparison)
│   ├── server.py                 # Original server (kept for comparison)
│   └── config.py                 # Unchanged
├── Dockerfile                     # Multi-stage build (Node + Python)
├── DEV_README.md                 # This file
└── README.md                     # Original README (updated)
```

## 🏃 Quick Start

### Local Development

#### 1. Backend only (with original simple UI):
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn enhanced_server:app --app-dir src --reload
# Visit http://localhost:8000
```

#### 2. Full stack (with React frontend):
```bash
# Terminal 1: Backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn enhanced_server:app --app-dir src --reload

# Terminal 2: Frontend
cd frontend
npm install
npm run dev
# Visit http://localhost:5173
```

### Docker (Production Build)

```bash
docker build -t code-change-agent:dev .
docker run -p 8000:8000 \
  -e GITHUB_TOKEN=your_token \
  -e AWS_PROFILE=your_profile \
  -v ~/.aws:/root/.aws:ro \
  code-change-agent:dev
```

### Deploy to EKS

Same as main branch - the enhanced server is backward compatible:

```bash
# Use the enhanced server in k8s/deployment*.yaml
# Change CMD to: ["uvicorn", "enhanced_server:app", "--app-dir", "src", ...]

CLUSTER=your-cluster REGION=us-east-1 scripts/setup-aws.sh
scripts/deploy.sh setup-gvisor <node-name>
IMAGE=<your-ecr-image> scripts/deploy.sh all
```

## 🎯 Demo Walkthrough

### Option 1: Pre-loaded Scenarios

1. Open the UI (http://localhost:8000 or http://localhost:5173)
2. Browse scenarios by category: **Security**, **Testing**, **Performance**, **Refactoring**
3. Click any scenario card to run it
4. Watch the real-time event log show:
   - Agent planning its approach
   - Security vulnerability detection
   - File changes with line counts
   - Git diffs
   - Test execution
   - PR creation
5. Check metrics: duration, files changed, tools used

### Option 2: Custom Task

1. Enter repository: `Cloud-Tech-AI/your-repo`
2. Enter task: `"Find and fix the SQL injection in the login endpoint"`
3. Select runtime: **Both** (runs on runc and gVisor), **runc**, or **gVisor**
4. Click "Run Custom Task"

### Option 3: API Testing

```bash
# List all scenarios
curl http://localhost:8000/scenarios

# Get a specific scenario
curl http://localhost:8000/scenarios/sql-injection-fix

# Start a run
curl -X POST http://localhost:8000/runs \
  -H 'Content-Type: application/json' \
  -d '{
    "github_repo": "Cloud-Tech-AI/vulnerable-flask-app",
    "task": "Fix SQL injection in login",
    "runtime": "gvisor"
  }'

# Stream events (returns run ID)
curl -N http://localhost:8000/runs/{run_id}/events

# Get metrics
curl http://localhost:8000/runs/{run_id}/metrics
```

## 📊 Key Improvements Over Main Branch

| Feature | Main Branch | Dev Branch |
|---------|------------|------------|
| **UI** | Basic HTML form | Modern React with TypeScript |
| **Agent Tools** | 6 basic tools | 10 advanced tools with planning |
| **Security Analysis** | None | Automatic vulnerability scanning |
| **Scenarios** | Manual entry only | 10 pre-configured demos |
| **Metrics** | None | Full execution metrics |
| **Event Types** | 3 (tool, done, error) | 8 (planning, security, diffs, etc.) |
| **Error Handling** | Basic | Production-ready with retries |
| **API** | Minimal | Full RESTful with docs |
| **Type Safety** | None | Full Pydantic models |
| **Runtime Selection** | Fixed | Choose runc, gVisor, or both |
| **File Tracking** | Basic | Line-by-line change metrics |
| **Test Integration** | None | Can run test suites |
| **Planning** | Immediate execution | Strategic planning first |

## 🔧 Configuration

Same as main branch - all settings work via `.env`:

```bash
# Required
GITHUB_TOKEN=ghp_xxxxx

# AWS (uses default profile if not set)
AWS_PROFILE=my-profile
AWS_REGION=us-east-1
MODEL_ID=global.anthropic.claude-sonnet-4-6

# Optional
GITHUB_API_URL=https://api.github.com
```

## 🧪 Example Scenario Output

Running **"Fix SQL Injection Vulnerability"**:

1. **Planning Phase**:
   ```
   Analysis: Found SQL string concatenation in auth/login.py
   Approach: Replace with parameterized queries, add validation
   Files to Modify: auth/login.py, tests/test_auth.py
   ```

2. **Security Scan**:
   ```
   ⚠️ SQL Injection: auth/login.py:45: cursor.execute(f"SELECT * FROM users WHERE username='{username}'")
   ```

3. **File Changes**:
   ```
   ✅ Modified auth/login.py: Replace string concat with parameterized query (+3/-1)
   ✅ Created tests/test_auth_injection.py: Add SQL injection test (+42/-0)
   ```

4. **Testing**:
   ```
   ✅ Tests passed
   test_sql_injection_prevention PASSED
   test_login_with_valid_creds PASSED
   ```

5. **Metrics**:
   - Duration: **2.4 minutes**
   - Files Changed: **2**
   - Tools Used: **9**
   - Errors: **0**

## 🚢 Production Checklist

Before running in production:

- [ ] Restrict CORS origins in `enhanced_server.py`
- [ ] Add authentication to API endpoints
- [ ] Enable HTTPS only
- [ ] Use fine-grained GitHub token scoped to specific repos
- [ ] Set up proper secrets management (not `.env` files)
- [ ] Configure logging and monitoring
- [ ] Set up rate limiting
- [ ] Review network policies for your cluster
- [ ] Test disaster recovery procedures

## 🐛 Known Limitations

1. **Dual-runtime mode** currently runs serially, not in parallel (would need Kubernetes API integration)
2. **Test execution** has 60s timeout (configurable)
3. **Security scanner** uses regex patterns (not a full SAST tool)
4. **Frontend build** adds ~2 minutes to Docker build time
5. **Metrics** are in-memory only (lost on restart)

## 🎨 Customization

### Add a New Scenario

Edit `src/scenarios.py`:

```python
DemoScenario(
    id="my-scenario",
    name="My Awesome Scenario",
    description="What it does",
    repo="owner/repo",
    task="Detailed task description...",
    category="security",  # or testing, performance, refactoring
    estimated_duration="3-4 minutes",
    difficulty="medium"  # easy, medium, hard
)
```

### Add a New Tool

Edit `src/enhanced_agent.py`:

```python
@tool
def my_new_tool(param: str) -> str:
    """Tool description for the agent.
    
    Args:
        param: Parameter description
    """
    # Implementation
    emit_event(EventType.INFO, f"Using my_new_tool with {param}")
    return "Result"
```

### Customize UI Theme

Edit `frontend/tailwind.config.js`:

```js
colors: {
  primary: { ... },  // Your brand colors
  gvisor: { ... },   // gVisor accent colors
}
```

## 📚 API Documentation

### Endpoints

- `GET /` - Serve frontend
- `GET /health` - Health check
- `GET /scenarios` - List all scenarios
- `GET /scenarios/{id}` - Get scenario by ID
- `POST /runs` - Start agent run
- `GET /runs/{id}/events` - Stream events (SSE)
- `GET /runs/{id}/metrics` - Get run metrics
- `DELETE /runs/{id}` - Cancel run

### Event Types

- **`tool`**: Agent called a tool
- **`thinking`**: Agent planning/analysis
- **`file_change`**: File created/modified
- **`diff`**: Git diff output
- **`done`**: Successful completion
- **`error`**: Error occurred
- **`info`**: Informational message
- **`metrics`**: Final metrics

## 🤝 Contributing

This is a dev branch for demonstration. Changes here don't affect `main`.

To propose changes:
1. Make changes in this branch
2. Test locally with both frontends
3. Update this README if adding features
4. Push to `dev/next-level-demo`
5. Don't merge to `main` without review

## 📝 License

Same as main branch - MIT. See [LICENSE](LICENSE).

---

**Questions?** Open an issue or check [DEMO.md](DEMO.md) for the original demo script.
