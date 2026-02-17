---
description: Git and GitHub workflow commands for this repository
---

# Git & GitHub Workflows

## /commit - Stage and Commit Changes
1. Check status: `git status`
2. Stage all changes: `git add .`
3. Commit with message: `git commit -m "your message here"`

## /push - Push to Remote
1. Push to current branch: `git push origin HEAD`
2. If branch doesn't exist remotely: `git push -u origin HEAD`

## /sync - Sync with Main Branch
1. Fetch latest: `git fetch origin`
2. Checkout main: `git checkout main`
3. Pull latest: `git pull origin main`
4. Return to your branch: `git checkout -`
5. Rebase: `git rebase main`

## /branch - Create Feature Branch
1. Ensure on main: `git checkout main`
2. Pull latest: `git pull origin main`
3. Create and switch: `git checkout -b feature/your-feature-name`

## /pr - Create Pull Request
1. Push current branch: `git push -u origin HEAD`
2. Use GitHub MCP to create PR with title and description

## /status - Check Repository Status
1. Show current branch: `git branch --show-current`
2. Show status: `git status`
3. Show recent commits: `git log --oneline -5`

## /undo - Undo Last Commit (Keep Changes)
1. Soft reset: `git reset --soft HEAD~1`

## /stash - Stash Current Changes
1. Stash: `git stash push -m "description"`
2. List stashes: `git stash list`
3. Apply latest: `git stash pop`

## /clean - Discard Uncommitted Changes
// turbo
1. Discard all: `git checkout -- .`
2. Remove untracked: `git clean -fd`
