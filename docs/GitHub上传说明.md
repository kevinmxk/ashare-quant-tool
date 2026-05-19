# GitHub 上传说明

这份说明对应本地上传脚本：

- [push_to_github.ps1](C:/Users/Kevin/Documents/Codex/2026-05-19/a-a/scripts/push_to_github.ps1)

## 上传前已经整理好的内容

项目根目录已经补了 `.gitignore`，默认不会上传这些内容：

- `__pycache__/`
- `*.pyc`
- `.pytest_cache/`
- `.venv/`
- `.env`
- `data/cache/*.sqlite3`

这意味着：

- 本地缓存数据库不会被提交
- Python 编译缓存不会被提交
- 你的私密环境变量不会被提交

## 最简单的上传方式

在项目根目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\push_to_github.ps1
```

默认参数：

- 仓库地址：`https://github.com/kevinmxk/ashare-quant-tool.git`
- 分支：`main`
- 提交信息：`Initial project upload`

## 自定义提交信息

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\push_to_github.ps1 -CommitMessage "Upload A-share quant tool"
```

## 如果你只想推送，不想自动提交

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\push_to_github.ps1 -SkipCommit
```

这个适合你已经手动提交过，只想推送的时候用。

## 如果你想看更详细的 git 执行过程

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\push_to_github.ps1 -VerboseGit
```

## 如果远端仓库已经有初始 README 或其他提交

如果你看到这种报错：

- `main -> main (fetch first)`
- `Updates were rejected because the remote contains work that you do not have locally`

说明远端不是空仓库，通常是你在 GitHub 上创建仓库时自动带了一个 `README.md`。

这时不要强推，直接运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\push_to_github.ps1 -CommitMessage "Upload initial A-share quant analysis tool" -SyncRemoteHistory
```

这个参数会先把远端 `main` 的历史合并到本地，再继续推送。

如果合并时提示冲突，最常见的是 `README.md`。这时先解决冲突，再重新执行推送即可。

## 脚本会做什么

1. 如果当前目录还不是 git 仓库，会自动初始化
2. 检查并切换到 `main` 分支
3. 检查 `origin` 远端，没有就自动添加
4. 执行 `git add .`
5. 如果有变更则自动提交
6. 如果你传了 `-SyncRemoteHistory`，会先同步远端历史
7. 执行 `git push -u origin main`

## 可能遇到的问题

### 1. 需要登录 GitHub

如果本机 git 还没有登录，推送时 GitHub 会要求你认证。

常见方式：

- 浏览器登录
- Personal Access Token
- Git Credential Manager

### 2. 远端已经有不同历史

如果远端仓库不是空仓库，可能会出现推送被拒绝。

优先使用上面的 `-SyncRemoteHistory` 参数处理，不要直接强推。

### 3. 分支不是 `main`

如果你想改成别的分支，比如 `master` 或 `dev`，可以这样：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\push_to_github.ps1 -Branch dev
```

## 建议的本次操作

你刚刚已经遇到 `fetch first` 报错，这次请直接执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\push_to_github.ps1 -CommitMessage "Upload initial A-share quant analysis tool" -SyncRemoteHistory
```

如果你跑完后把输出发给我，我可以继续帮你确认仓库状态，或者处理冲突、README、分支这些后续事情。
