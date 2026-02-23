#!/usr/bin/env python3
"""BlackRoad Dotfiles Manager – symlink, backup, diff, and restore dotfiles."""

import argparse, hashlib, json, os, shutil, sqlite3, sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

GREEN  = "\033[0;32m"; RED    = "\033[0;31m"; YELLOW = "\033[1;33m"
CYAN   = "\033[0;36m"; BOLD   = "\033[1m";    NC     = "\033[0m"
def ok(m):   print(f"{GREEN}✓{NC} {m}")
def err(m):  print(f"{RED}✗{NC} {m}", file=sys.stderr)
def info(m): print(f"{CYAN}ℹ{NC} {m}")
def warn(m): print(f"{YELLOW}⚠{NC} {m}")

DB_PATH    = os.path.expanduser("~/.blackroad-personal/dotfiles.db")
CATEGORIES = ("shell", "editor", "git", "tmux", "tool")

@dataclass
class DotfileEntry:
    id: int
    name: str
    source_path: str
    target_path: str
    category: str
    description: str
    auto_update: bool

@dataclass
class Snapshot:
    id: int
    entry_id: int
    content_hash: str
    saved_at: str
    notes: str

def get_db() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS dotfiles (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL UNIQUE,
            source_path TEXT NOT NULL,
            target_path TEXT NOT NULL,
            category    TEXT NOT NULL DEFAULT 'tool',
            description TEXT NOT NULL DEFAULT '',
            auto_update INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS snapshots (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_id     INTEGER NOT NULL REFERENCES dotfiles(id),
            content_hash TEXT NOT NULL,
            content_b64  TEXT NOT NULL DEFAULT '',
            saved_at     TEXT NOT NULL,
            notes        TEXT NOT NULL DEFAULT ''
        );
    """)
    conn.commit()
    return conn

def file_hash(path: str) -> str:
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception:
        return ""

def row_to_entry(row) -> DotfileEntry:
    d = dict(row)
    return DotfileEntry(id=d["id"], name=d["name"], source_path=d["source_path"],
                        target_path=d["target_path"], category=d["category"],
                        description=d["description"], auto_update=bool(d["auto_update"]))

def row_to_snapshot(row) -> Snapshot:
    d = dict(row)
    return Snapshot(id=d["id"], entry_id=d["entry_id"], content_hash=d["content_hash"],
                    saved_at=d["saved_at"], notes=d["notes"])

CATEGORY_ICON = {"shell":"🐚","editor":"✏️","git":"🌿","tmux":"🖥️","tool":"🔧"}

def print_entry(e: DotfileEntry, status=""):
    icon = CATEGORY_ICON.get(e.category, "?")
    auto = " [auto]" if e.auto_update else ""
    print(f"  {icon} [{e.id:>3}] {CYAN}{e.name}{NC}{auto}  ({e.category})")
    print(f"        {e.source_path}  →  {e.target_path}")
    if e.description: print(f"        {e.description}")
    if status:        print(f"        {status}")

# ── Commands ──────────────────────────────────────────────────────────────────
def cmd_register(args):
    if args.category not in CATEGORIES:
        err(f"Category must be one of: {', '.join(CATEGORIES)}"); sys.exit(1)
    db = get_db()
    source = str(Path(args.source).expanduser().resolve())
    target = str(Path(args.target).expanduser())
    try:
        db.execute("""
            INSERT INTO dotfiles(name,source_path,target_path,category,description,auto_update)
            VALUES(?,?,?,?,?,?)
        """, (args.name, source, target, args.category, args.description or "", 1 if args.auto else 0))
        db.commit()
        ok(f"Registered: {args.name}  ({source} → {target})")
    except sqlite3.IntegrityError:
        err(f"A dotfile named '{args.name}' is already registered")

def cmd_link(args):
    db  = get_db()
    row = db.execute("SELECT * FROM dotfiles WHERE id=?", (args.entry_id,)).fetchone()
    if not row:
        err(f"Entry #{args.entry_id} not found"); return
    e = row_to_entry(row)
    target = Path(e.target_path)
    source = Path(e.source_path)

    if not source.exists():
        err(f"Source does not exist: {source}"); return

    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists() or target.is_symlink():
        if target.is_symlink() and os.readlink(str(target)) == str(source):
            ok(f"Already linked: {target}"); return
        backup = str(target) + ".bak"
        shutil.move(str(target), backup)
        warn(f"Existing file backed up to {backup}")

    os.symlink(str(source), str(target))
    ok(f"Linked: {target} → {source}")

def cmd_sync_all(args):
    db   = get_db()
    rows = db.execute("SELECT * FROM dotfiles WHERE auto_update=1").fetchall()
    if not rows:
        warn("No dotfiles with auto_update enabled")
        info("Use --auto flag when registering"); return
    info(f"Syncing {len(rows)} dotfile(s)…")
    for row in rows:
        e = row_to_entry(row)
        _do_link(e)

def _do_link(e: DotfileEntry):
    target = Path(e.target_path)
    source = Path(e.source_path)
    if not source.exists():
        warn(f"  {e.name}: source missing ({source})"); return
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        if target.is_symlink() and os.readlink(str(target)) == str(source):
            ok(f"  {e.name}: already linked"); return
        backup = str(target) + ".bak"
        shutil.move(str(target), backup)
    os.symlink(str(source), str(target))
    ok(f"  {e.name}: linked")

def cmd_backup(args):
    db  = get_db()
    row = db.execute("SELECT * FROM dotfiles WHERE id=?", (args.entry_id,)).fetchone()
    if not row:
        err(f"Entry #{args.entry_id} not found"); return
    e = row_to_entry(row)
    path = Path(e.source_path)
    if not path.exists():
        err(f"Source file not found: {path}"); return
    content = path.read_bytes()
    h       = hashlib.sha256(content).hexdigest()
    b64     = __import__("base64").b64encode(content).decode()
    now     = datetime.now().isoformat()
    db.execute("INSERT INTO snapshots(entry_id,content_hash,content_b64,saved_at,notes) VALUES(?,?,?,?,?)",
               (args.entry_id, h, b64, now, args.notes or ""))
    db.commit()
    ok(f"Snapshot saved for {e.name}  hash={h[:12]}…")

def cmd_diff(args):
    db  = get_db()
    row = db.execute("SELECT * FROM dotfiles WHERE id=?", (args.entry_id,)).fetchone()
    if not row:
        err(f"Entry #{args.entry_id} not found"); return
    e = row_to_entry(row)
    snap = db.execute(
        "SELECT * FROM snapshots WHERE entry_id=? ORDER BY saved_at DESC LIMIT 1", (args.entry_id,)
    ).fetchone()
    if not snap:
        warn(f"No snapshots for {e.name}. Run `backup` first."); return
    current_hash = file_hash(e.source_path)
    if current_hash == snap["content_hash"]:
        ok(f"{e.name}: no changes since last snapshot")
    else:
        warn(f"{e.name}: file has changed since snapshot {snap['saved_at'][:19]}")
        # Attempt unified diff
        import tempfile, subprocess
        with tempfile.NamedTemporaryFile(suffix=".old", delete=False, mode="wb") as f:
            f.write(__import__("base64").b64decode(snap["content_b64"]))
            old_file = f.name
        result = subprocess.run(["diff", "-u", old_file, e.source_path],
                                capture_output=True, text=True)
        os.unlink(old_file)
        if result.stdout:
            print(result.stdout[:2000])

def cmd_restore(args):
    db  = get_db()
    row = db.execute("SELECT * FROM dotfiles WHERE id=?", (args.entry_id,)).fetchone()
    if not row:
        err(f"Entry #{args.entry_id} not found"); return
    e    = row_to_entry(row)
    snap = db.execute("SELECT * FROM snapshots WHERE id=?", (args.snapshot_id,)).fetchone()
    if not snap:
        err(f"Snapshot #{args.snapshot_id} not found"); return
    content = __import__("base64").b64decode(snap["content_b64"])
    path    = Path(e.source_path)
    # Back up current
    if path.exists():
        shutil.copy2(str(path), str(path) + ".pre-restore")
        warn(f"Current version backed up to {path}.pre-restore")
    path.write_bytes(content)
    ok(f"Restored {e.name} from snapshot #{snap['id']} ({snap['saved_at'][:19]})")

def cmd_export_manifest(args):
    db   = get_db()
    rows = db.execute("SELECT * FROM dotfiles ORDER BY category, name").fetchall()
    data = [dict(r) for r in rows]
    fname = args.output or "dotfiles_manifest.json"
    with open(fname, "w") as f: json.dump(data, f, indent=2)
    ok(f"Manifest exported to {fname}  ({len(data)} entries)")

def cmd_import_manifest(args):
    with open(args.file) as f: data = json.load(f)
    db = get_db()
    imported = 0
    for item in data:
        try:
            db.execute("""
                INSERT OR IGNORE INTO dotfiles(name,source_path,target_path,category,description,auto_update)
                VALUES(?,?,?,?,?,?)
            """, (item["name"], item["source_path"], item["target_path"],
                  item.get("category","tool"), item.get("description",""), item.get("auto_update",0)))
            imported += 1
        except Exception: pass
    db.commit()
    ok(f"Imported {imported}/{len(data)} entries")

def cmd_check_broken(args):
    db   = get_db()
    rows = db.execute("SELECT * FROM dotfiles").fetchall()
    broken = 0
    for row in rows:
        e = row_to_entry(row)
        t = Path(e.target_path)
        if t.is_symlink():
            if not t.exists():
                err(f"  BROKEN  {e.name}: {t} → (missing)")
                broken += 1
            else:
                ok(f"  OK      {e.name}")
        elif t.exists():
            warn(f"  UNLINKED  {e.name}: {t} exists but is not a symlink")
        else:
            info(f"  NOT LINKED  {e.name}")
    if broken == 0:
        ok("No broken symlinks")

def cmd_list(args):
    db   = get_db()
    rows = db.execute("SELECT * FROM dotfiles ORDER BY category, name").fetchall()
    if not rows:
        warn("No dotfiles registered"); return
    cur_cat = None
    for row in rows:
        e = row_to_entry(row)
        if e.category != cur_cat:
            cur_cat = e.category
            print(f"\n{BOLD}{CATEGORY_ICON.get(e.category,'?')} {e.category.upper()}{NC}")
        t = Path(e.target_path)
        if t.is_symlink() and t.exists():
            status = f"{GREEN}linked{NC}"
        elif t.exists():
            status = f"{YELLOW}exists (unlinked){NC}"
        else:
            status = f"{RED}not linked{NC}"
        print_entry(e, status)

def cmd_snapshots(args):
    db   = get_db()
    rows = db.execute(
        "SELECT s.*, d.name FROM snapshots s JOIN dotfiles d ON s.entry_id=d.id "
        "WHERE s.entry_id=? ORDER BY s.saved_at DESC", (args.entry_id,)
    ).fetchall()
    if not rows:
        warn(f"No snapshots for entry #{args.entry_id}"); return
    print(f"\n{BOLD}Snapshots for entry #{args.entry_id}:{NC}")
    for r in rows:
        print(f"  [{r['id']:>3}] {r['saved_at'][:19]}  hash={r['content_hash'][:12]}…  {r['notes']}")

def main():
    parser = argparse.ArgumentParser(prog="br-dots", description="BlackRoad Dotfiles Manager")
    sub    = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("register"); p.add_argument("name"); p.add_argument("source"); p.add_argument("target")
    p.add_argument("--category",default="tool",choices=CATEGORIES); p.add_argument("--description",default="")
    p.add_argument("--auto",action="store_true"); p.set_defaults(func=cmd_register)

    p = sub.add_parser("link");   p.add_argument("entry_id",type=int); p.set_defaults(func=cmd_link)
    sub.add_parser("sync-all").set_defaults(func=cmd_sync_all)

    p = sub.add_parser("backup"); p.add_argument("entry_id",type=int); p.add_argument("--notes",default="")
    p.set_defaults(func=cmd_backup)

    p = sub.add_parser("diff"); p.add_argument("entry_id",type=int); p.set_defaults(func=cmd_diff)

    p = sub.add_parser("restore"); p.add_argument("entry_id",type=int); p.add_argument("snapshot_id",type=int)
    p.set_defaults(func=cmd_restore)

    p = sub.add_parser("export"); p.add_argument("--output",default=None); p.set_defaults(func=cmd_export_manifest)
    p = sub.add_parser("import"); p.add_argument("file"); p.set_defaults(func=cmd_import_manifest)

    sub.add_parser("check").set_defaults(func=cmd_check_broken)
    sub.add_parser("list").set_defaults(func=cmd_list)

    p = sub.add_parser("snapshots"); p.add_argument("entry_id",type=int); p.set_defaults(func=cmd_snapshots)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
