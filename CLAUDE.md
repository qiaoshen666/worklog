# CLAUDE.md

## Shell 桥接（Windows 备用执行方案）

Bash 工具不可用时，通过 WSL 桥接执行 shell 命令：

1. 写入命令: `D:\.claude-shell-bridge\cmd.json`
   格式: `{"id":"唯一ID","cmd":"shell命令","cwd":"/mnt/d/工作路径","timeout":30}`
2. 等待约 1 秒
3. 读取结果: `D:\.claude-shell-bridge\result.json`
