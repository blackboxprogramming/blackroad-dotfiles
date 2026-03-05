# blackroad-dotfiles

[![CI](https://github.com/blackboxprogramming/blackroad-dotfiles/actions/workflows/ci.yml/badge.svg)](https://github.com/blackboxprogramming/blackroad-dotfiles/actions/workflows/ci.yml)
[![Security Scan](https://github.com/blackboxprogramming/blackroad-dotfiles/actions/workflows/security.yml/badge.svg)](https://github.com/blackboxprogramming/blackroad-dotfiles/actions/workflows/security.yml)

Dotfiles and shell configuration manager with symlinks, snapshots, diff, and restore.
Includes Cloudflare Workers for long-running sync tasks, Vercel pages, and Railway services.

## Quick Start

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Register a dotfile
python dotfiles_manager.py register zshrc ~/.zshrc ~/.zshrc \
  --category shell --description "Zsh configuration" --auto

python dotfiles_manager.py register vimrc ~/dotfiles/.vimrc ~/.vimrc \
  --category editor

python dotfiles_manager.py register gitconfig ~/dotfiles/.gitconfig ~/.gitconfig \
  --category git --auto

# Create symlink
python dotfiles_manager.py link 1

# Sync all auto-update dotfiles
python dotfiles_manager.py sync-all

# Take a snapshot (backup current content)
python dotfiles_manager.py backup 1 --notes "Before big refactor"

# See what changed since last snapshot
python dotfiles_manager.py diff 1

# Restore from a snapshot
python dotfiles_manager.py snapshots 1       # list snapshots
python dotfiles_manager.py restore 1 3       # restore entry 1 from snapshot 3

# Check for broken symlinks
python dotfiles_manager.py check

# Export manifest (for new machine setup)
python dotfiles_manager.py export --output dotfiles_manifest.json

# Import manifest on new machine
python dotfiles_manager.py import dotfiles_manifest.json

# List all registered dotfiles
python dotfiles_manager.py list
```

## Categories

`shell` | `editor` | `git` | `tmux` | `tool`

## Storage

SQLite at `~/.blackroad-personal/dotfiles.db`.
Snapshots store full file content (base64) for reliable restore.

## Testing

```bash
pytest tests/ -v
```

## Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| CI | Push/PR to `main` | Tests (Python 3.11/3.12) + lint |
| Security Scan | Push/PR + weekly | CodeQL analysis + dependency review |
| Automerge | PR labeled `automerge` | Auto-squash-merge passing PRs |
| Deploy Cloudflare | Push to `workers/` | Deploy Cloudflare Worker |
| Deploy Vercel | Push to `pages/` | Deploy Vercel pages |
| Deploy Railway | Push to `services/` | Deploy Railway services |

All GitHub Actions are pinned to specific commit SHAs for supply-chain security.
Dependabot is configured to keep all dependencies up to date.

## Cloudflare Worker API

The worker at `workers/` handles long-running tasks:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/validate-manifest` | POST | Validate dotfiles manifest JSON |
| `/api/sync-status` | GET | Get last sync status |
| `/api/trigger-sync` | POST | Trigger background sync |

## Infrastructure

- **Cloudflare Workers** — Long-running sync, manifest validation, scheduled health checks
- **Vercel** — Static pages and dashboard (`pages/`)
- **Railway** — Backend services (`services/`)
- **Stripe** — Product and subscription management (configured via secrets)

## Security

- All Actions pinned to commit SHA (not mutable tags)
- CodeQL + dependency review on every PR
- Dependabot auto-updates with automerge for Actions
- CODEOWNERS enforced review policy
- See [SECURITY.md](SECURITY.md) for vulnerability reporting

## License

Proprietary — BlackRoad OS, Inc. All Rights Reserved.
This software is NOT open source. See [LICENSE](LICENSE) for terms.
