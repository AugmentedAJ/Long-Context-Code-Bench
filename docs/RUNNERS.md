# Runner Adapters

This document describes the CLI coding agent adapters supported by Long-Context-Bench.

## Overview

Long-Context-Bench uses a pluggable adapter system to support different CLI coding agents. Each adapter implements the `RunnerAdapter` interface and handles the specifics of invoking that agent's CLI.

## Supported Runners

### Auggie

**Runner Name:** `auggie`

**Description:** Augment's CLI coding agent with advanced context understanding and code editing capabilities.

**Installation:**
- Contact Augment for access to the Auggie CLI

**Authentication:**
- **Recommended:** OAuth via `auggie login` (uses subscription)
- **Alternative:** Set `AUGMENT_API_TOKEN` environment variable

**Example (OAuth - Recommended):**
```bash
# First time: authenticate with OAuth
auggie login

# Run benchmark (no API token needed)
long-context-bench edit \
  --runner auggie \
  --model sonnet \
  output/samples/v0
```

**Example (API Token):**
```bash
export AUGMENT_API_TOKEN=your_token
long-context-bench edit \
  --runner auggie \
  --model sonnet \
  output/samples/v0
```

**Features:**
- One-shot mode with `--print` flag
- Workspace-aware indexing
- Configurable retry timeouts
- JSONL logging
- Model aliases: `sonnet`, `opus`, `haiku`

---

### Claude Code

**Runner Name:** `claude-code`

**Description:** Anthropic's command-line coding agent.

**Installation:**
- Follow Anthropic's installation instructions for Claude Code CLI

**Authentication:**
- **Recommended:** OAuth via `claude setup-token` (uses subscription)
- **Alternative:** Set `ANTHROPIC_API_KEY` environment variable

**Example (OAuth - Recommended):**
```bash
# First time: set up subscription authentication
claude setup-token

# Run benchmark (no API key needed)
long-context-bench edit \
  --runner claude-code \
  --model sonnet \
  output/samples/v0
```

**Example (API Key):**
```bash
export ANTHROPIC_API_KEY=your_key
long-context-bench edit \
  --runner claude-code \
  --model sonnet \
  output/samples/v0
```

**Features:**
- Model aliases: `sonnet`, `opus`, `haiku`


**Auth modes & visibility:**

The harness supports explicit Claude auth selection via `LCB_CLAUDE_AUTH`:
- `auto` (default): use API key if `ANTHROPIC_API_KEY` is set, else use subscription
- `subscription`: force subscription; harness strips `ANTHROPIC_*` env vars for the run
- `api-key`: force API key; requires `ANTHROPIC_API_KEY`

At runtime the edit stage prints a line such as:
`Claude auth: subscription (mode=auto, ANTHROPIC_API_KEY=absent)`

Additionally, `logs.jsonl` includes an `auth_info` record with fields `auth_mode`, `used_auth`, and `anthropic_api_key_present`.

**Features:**
- Headless mode with `-p` flag
- Structured JSON output
- Configurable allowed tools
- Auto-approval for file edits and git commits

**Implementation Details:**
- Uses `--output-format stream-json` for structured output
- Allows `Edit` and `Bash(git commit:*)` tools by default
- Passes task instructions directly via `-p` flag

---

### Codex CLI

**Runner Name:** `codex`

**Description:** OpenAI's command-line coding agent.

**Installation:**
```bash
npm install -g @openai/codex
```

**Environment Variables:**
- `OPENAI_API_KEY` (required)

**Example:**
```bash
export OPENAI_API_KEY=your_key
long-context-bench edit \
  --runner codex \
  --model gpt-5-codex \
  output/samples/v0
```

**Features:**
- Non-interactive execution with `exec` command
- Structured JSON output
- Configurable allowed tools
- Model selection via `--model` flag

**Implementation Details:**
- Uses `codex exec` for non-interactive mode
- Allows `Edit` and `Bash` tools by default
- Passes task instructions as command argument

---

### Aider

**Runner Name:** `aider`

**Description:** Open-source AI pair programming tool with support for multiple LLM providers.

**Installation:**
```bash
pip install aider-chat
```

**Environment Variables:**
- Depends on model provider (e.g., `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`)

**Example:**
```bash
export ANTHROPIC_API_KEY=your_key
long-context-bench edit \
  --runner aider \
  --model claude-sonnet-4 \
  output/samples/v0
```

**Features:**
- Non-interactive mode with `--message` flag
- Auto-commit changes
- Configurable repo map
- LLM history logging
- Support for multiple model providers

**Implementation Details:**
- Uses `--message` for non-interactive execution
- Uses `--yes-always` to auto-accept prompts
- Uses `--auto-commits` to commit changes automatically
- Respects `--disable-retrieval` (sets `--map-tokens=0`)
- Respects `--disable-shell` (sets `--no-suggest-shell-commands`)
- Logs LLM interactions to `.aider.llm.history`

---

### Generic

**Runner Name:** `generic`

**Description:** Generic adapter for any CLI agent that accepts task instructions via stdin.

**Installation:**
- Depends on the specific agent

**Example:**
```bash
long-context-bench edit \
  --runner generic \
  --model your-model \
  --agent-binary /path/to/your/agent \
  output/samples/v0
```

**Features:**
- Simple stdin-based interface
- Works with any CLI tool that reads from stdin
- Minimal assumptions about agent behavior

**Implementation Details:**
- Writes task instructions to stdin
- Captures stdout/stderr
- No special flags or configuration

---

## Adapter Interface

All adapters implement the `RunnerAdapter` base class:

```python
class RunnerAdapter(ABC):
    def __init__(
        self,
        model: str,
        agent_binary: Optional[str] = None,
        timeout: int = 1800,
        disable_retrieval: bool = False,
        disable_shell: bool = False,
        enable_mcp_codebase_qa: bool = False,
        **kwargs: Any,
    ):
        ...

    @abstractmethod
    def run(
        self,
        workspace_path: Path,
        task_instructions: str,
        logs_path: Path,
        env: Optional[Dict[str, str]] = None,
    ) -> RunnerResult:
        ...
```

### RunnerResult

Each adapter returns a `RunnerResult` with:
- `status`: `"success"`, `"timeout"`, or `"error"`
- `elapsed_ms`: Execution time in milliseconds
- `errors`: Optional list of error messages

## Adding a New Runner

To add support for a new CLI coding agent:

1. **Create adapter file:** `long_context_bench/runners/your_agent.py`
2. **Implement RunnerAdapter:** Extend the base class and implement `run()`
3. **Register adapter:** Add to `get_runner_adapter()` in `__init__.py`
4. **Update documentation:** Add to this file and README.md
5. **Test:** Verify the adapter works with a minimal test run

Example skeleton:

```python
from long_context_bench.runners.base import RunnerAdapter, RunnerResult

class YourAgentAdapter(RunnerAdapter):
    def run(self, workspace_path, task_instructions, logs_path, env):
        # Build command
        cmd = [self.agent_binary or "your-agent", ...]

        # Run agent
        result = subprocess.run(cmd, ...)

        # Return result
        return RunnerResult(status="success", elapsed_ms=..., errors=None)
```

## Comparison

| Runner | Provider | Open Source | Installation | Best For |
|--------|----------|-------------|--------------|----------|
| Auggie | Augment | No | Contact Augment | Advanced context understanding |
| Claude Code | Anthropic | No | Anthropic CLI | Claude models |
| Codex CLI | OpenAI | No | npm install | OpenAI models |
| Aider | Community | Yes | pip install | Multi-provider support |
| Generic | N/A | N/A | Varies | Custom agents |

## Troubleshooting

### Agent Not Found

If you get "agent not found" errors:
1. Ensure the agent is installed and in your PATH
2. Use `--agent-binary` to specify the full path
3. Verify the binary is executable: `which <agent-name>`

### Authentication Errors

**For Claude Code:**
```bash
# Check if authenticated with OAuth
claude --version  # Should work without ANTHROPIC_API_KEY

# If not authenticated, set up OAuth
claude setup-token

# Or use API key as fallback
export ANTHROPIC_API_KEY=your_key
```

**For Auggie:**
```bash
# Check if authenticated with OAuth
auggie --version  # Should work without AUGMENT_API_TOKEN

# If not authenticated, log in with OAuth
auggie login

# Or use API token as fallback
export AUGMENT_API_TOKEN=your_token
```

### Timeout Issues

If tasks are timing out:
1. Increase timeout: `--timeout 3600` (1 hour)
2. Check agent logs in `output/edits/.../logs.jsonl`
3. Test the agent manually on a simple task

### Model Not Supported

Some agents only support specific models:
- Claude Code: Claude models only
- Codex CLI: OpenAI models only
- Aider: Multiple providers (check Aider docs)
- Auggie: Multiple providers

Refer to each agent's documentation for supported models.

