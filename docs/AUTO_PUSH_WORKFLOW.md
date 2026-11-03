
---

### `docs/AUTO_PUSH_WORKFLOW.md`

```markdown
# Per-File Auto Push and Progress Tracking

## 1. Why this exists

Antigravity is a preview-stage coding agent. Long autonomous runs can end
early, and context can drift. If a run is interrupted after five files are
written but none are committed, all five are lost. The fix is architectural:
**make Git the durable memory, not the agent's context.**

The rule is: one file per turn, commit and push that file, append to
`PROGRESS.md`, stop. Resume cost after any interruption is:
`git pull` → read `PROGRESS.md` → write the next file.

## 2. Primary path: Antigravity MCP git tool

Antigravity's MCP Store provides an `auto_git_commit` tool that can stage,
commit, and optionally push changes automatically. Its parameters include
`repo_path`, `push`, and `stage_all`. Configure it in the MCP settings and
instruct the agent (via Prompt 1) to call it after each verified file:

```json
{
  "mcpServers": {
    "git-auto-commit": {
      "command": "npx",
      "args": ["-y", "antigravity-mcp-server"],
      "env": {
        "GITHUB_TOKEN": "<your-PAT>",
        "DEFAULT_BRANCH": "main"
      }
    }
  }
}