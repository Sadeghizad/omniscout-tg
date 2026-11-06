# OmniScout-TG as an MCP server

The engine ships as a [Model Context Protocol](https://modelcontextprotocol.io) server, so an
agent can price and plan Telegram Ads campaigns with the same code the CLI and the GUI use.
The server speaks stdio and runs on your machine. No hosted service, no extra API key.

## 1. Prepare the machine

```powershell
git clone <your-fork-url> 1002tgmktg
cd 1002tgmktg
pip install -r requirements.txt
Copy-Item .env.example .env      # optional: only needed for b.ai creative hooks
```

`mcp`, `fastapi` and `uvicorn` are already in `requirements.txt`.

## 2. Point a client at it

Every client needs the same three facts: the interpreter, the module, and the working directory.
Replace `/ABSOLUTE/PATH/TO/1002tgmktg` with your clone, and on Windows use forward slashes or
escaped backslashes.

> **Use the absolute interpreter path.** Desktop apps often launch with a different `PATH` than your
> shell. `python` works when it resolves; when it does not, put the full path there, for example
> `C:/Users/you/AppData/Local/Programs/Python/Python311/python.exe`.

### Claude Desktop

Edit `claude_desktop_config.json` (Settings → Developer → Edit Config), then restart the app.

```json
{
  "mcpServers": {
    "omniscout-tg": {
      "command": "python",
      "args": ["-m", "src.mcp_server"],
      "cwd": "C:/Users/you/Documents/1002tgmktg"
    }
  }
}
```

### Cursor

Project-scoped `.cursor/mcp.json`, or the global `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "omniscout-tg": {
      "command": "python",
      "args": ["-m", "src.mcp_server"],
      "cwd": "C:/Users/you/Documents/1002tgmktg"
    }
  }
}
```

### VS Code (Copilot agent mode, Cline, Roo Code)

Workspace file `.vscode/mcp.json`:

```json
{
  "servers": {
    "omniscout-tg": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "src.mcp_server"],
      "cwd": "C:/Users/you/Documents/1002tgmktg"
    }
  }
}
```

Cline and Roo Code use the same `command` / `args` / `cwd` shape as Cursor.

### DSH and other YAML-configured hosts

Add the server to your host profile's MCP list. The fields match the JSON above: `command`, `args`,
`cwd`, plus optional `env`.

```yaml
mcpServers:
  omniscout-tg:
    command: python
    args: ["-m", "src.mcp_server"]
    cwd: C:/Users/you/Documents/1002tgmktg
```

## 3. Tools

| Tool | What it returns | Network | Typical time |
| :--- | :--- | :---: | :--- |
| `estimate_economics` | CPM ceiling, target bid (USD and TON), confidence score, BUY / NEGOTIATE / TEST_CELL / REJECT verdict | no | instant |
| `validate_channels` | Per-handle pass/fail with the rejection code, subscriber count and last post date | yes | ~2-5 s per handle |
| `discover_channels` | The live candidate universe around your seeds, with provenance and depth | yes | 1-3 min |
| `run_media_plan` | Full pipeline: KPI summary, per-channel recommendations, absolute paths of the generated `.xlsx` and `.csv` | yes | 2-10 min |

### `estimate_economics`

Everything is deterministic arithmetic on the channel's numbers and your campaign assumptions.
Give it a quoted price to turn it into a negotiation verdict.

```json
{
  "subscribers": 48000,
  "reach_24h": 16000,
  "err24": 2.9,
  "target_cac_usd": 50,
  "est_cvr": 0.02,
  "quoted_cpm": 14.5
}
```

### `validate_channels`

Accepts `@name`, `name`, `https://t.me/name` and `https://t.me/s/name`. A handle passes only when the
public preview answers HTTP 200, the channel has a real title, at least 1,000 subscribers, and a post
in the last 14 days.

### `run_media_plan`

Longest call, and the only one that writes files. Ask for it when the agent should produce a
deliverable rather than an answer. The response carries `files.xlsx_path` and `files.csv_path` so the
agent can report where they landed.

## 4. What to ask the agent

- "Validate `@parvazcapital_tel`, `@finance_managers` and `@bourse_academy` for Telegram Ads, then price them for a $50 CAC campaign with a 2% conversion rate."
- "My client sells contract-signing software to Iranian businesses. Plan a $3,000 campaign seeded from `@parvazcapital_tel` and give me the Excel deliverable."
- "A channel with 120k subscribers and 34% attention is asking $22 CPM. Should I buy at a $40 CAC?"

## 5. Troubleshooting

**The client shows the server as failed or missing.** Run the exact command the client runs, from the
same directory, in a terminal: `python -m src.mcp_server`. If that prints nothing and hangs, it is
working, because stdio servers wait for their host. If it raises `ModuleNotFoundError: mcp`, install
the dependencies in the interpreter your client uses.

**Dense scoring silently degrades.** The dense half of the relevance scorer runs `google/embeddinggemma-2`
through a separate virtualenv. Set `EMBEDDING_PYTHON_PATH` to that interpreter. Without it, BM25 still
scores and dense scores use a fixed baseline, so verdicts stay usable and less precise.

**`run_media_plan` returns few or no channels.** Telegram Ads rejects a lot of what discovery finds:
private channels, channels under 1,000 members, and channels that stopped posting. Try two or three
seed channels from the same vertical.
