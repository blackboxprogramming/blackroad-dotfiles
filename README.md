# blackroad-dotfiles

Personal dotfiles and shell configuration manager with symlinks, snapshots, diff, and restore.

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

`shell` 🐚 | `editor` ✏️ | `git` 🌿 | `tmux` 🖥️ | `tool` 🔧

## Storage

SQLite at `~/.blackroad-personal/dotfiles.db`.
Snapshots store full file content (base64) for reliable restore.

## License

Proprietary — BlackRoad OS, Inc.
