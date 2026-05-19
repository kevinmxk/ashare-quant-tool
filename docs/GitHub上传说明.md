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

## 脚本会做什么

1. 如果当前目录还不是 git 仓库，会自动初始化
2. 检查并切换到 `main` 分支
3. 检查 `origin` 远端，没有就自动添加
4. 执行 `git add .`
5. 如果有变更则自动提交
6. 执行 `git push -u origin main`

## 可能遇到的问题

### 1. 需要登录 GitHub

如果本机 git 还没有登录，推送时 GitHub 会要求你认证。

常见方式：

- 浏览器登录
- Personal Access Token
- Git Credential Manager

### 2. 远端已经有不同历史

如果远端仓库不是空仓库，可能会出现推送被拒绝。

这时先不要强推，先告诉我报错内容，我再帮你处理。

### 3. 分支不是 `main`

如果你想改成别的分支，比如 `master` 或 `dev`，可以这样：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\push_to_github.ps1 -Branch dev
```

## 建议的本次操作

你现在可以直接在项目目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\push_to_github.ps1 -CommitMessage "Upload initial A-share quant analysis tool"
```

如果你跑完后把报错或成功输出发给我，我可以继续帮你确认仓库状态，或者处理后续分支、README、发布说明这些事情。

