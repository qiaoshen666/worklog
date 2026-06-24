---
name: shell-bridge
description: Execute shell commands on Windows by writing commands to a file bridge, executed by a WSL daemon. Use this instead of the Bash tool whenever you need to run a shell command.
---

# WSL Shell Bridge

Use this skill to run shell commands when the Bash tool is unavailable.

## How it works

1. Write the command to `D:\.claude-shell-bridge\cmd.json` as JSON: `{"id":"任意唯一ID","cmd":"要执行的shell命令","cwd":"/mnt/d/your/path","timeout":30}`
2. Wait briefly for the WSL daemon to execute the command
3. Read the result from `D:\.claude-shell-bridge\result.json`

## Important notes

- The `cmd` field must be a single shell command (can use `&&` to chain, or `\n` for multiline scripts)
- The `cwd` field uses WSL path format (`/mnt/d/...`, not `D:\...`)
- The `timeout` field is in seconds (default 30, max 300)
- The daemon removes `cmd.json` when it picks up the command — do NOT keep rewriting it
- After writing `cmd.json`, briefly wait (~1s) before reading `result.json`
- Generate a unique `id` for each command (e.g. `task_1`, `run_python`, etc.)

## Examples

### Simple command
Write cmd.json:
```json
{"id":"ls_dir","cmd":"ls /mnt/d/日常/日志/*.docx","cwd":"/mnt/d","timeout":10}
```

### Python script
Write cmd.json:
```json
{"id":"export_docx","cmd":"python3 -c \"\nfrom docx import Document\nimport glob\nfor f in glob.glob('/mnt/d/日常/日志/2026.6.5*.docx'):\n    doc = Document(f)\n    with open(f+'.txt','w',encoding='utf-8') as fw:\n        for p in doc.paragraphs:\n            fw.write(p.text+'\\n')\n    print(f'OK: {f}')\n\"","cwd":"/mnt/d","timeout":30}
```

### Shell pipeline
Write cmd.json:
```json
{"id":"grep_logs","cmd":"grep -r 'error' /mnt/d/logs/ | wc -l","cwd":"/mnt/d","timeout":60}
```
