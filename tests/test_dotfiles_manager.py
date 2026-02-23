"""Tests for dotfiles_manager.py"""
import base64, hashlib, json, os, sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
import dotfiles_manager as dm


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(dm, "DB_PATH", str(tmp_path / "test_dots.db"))
    yield tmp_path


def _register(tmp_path, name="zshrc", category="shell", auto=False):
    src = tmp_path / f"{name}_source"
    src.write_text(f"# {name} config\nexport PATH=$HOME/bin:$PATH\n")
    dst = tmp_path / f".{name}"
    db  = dm.get_db()
    db.execute("""
        INSERT INTO dotfiles(name,source_path,target_path,category,description,auto_update)
        VALUES(?,?,?,?,?,?)
    """, (name, str(src), str(dst), category, f"{name} config", 1 if auto else 0))
    db.commit()
    return db.execute("SELECT id FROM dotfiles WHERE name=?", (name,)).fetchone()["id"], src, dst


def test_db_init(tmp_db):
    assert dm.get_db() is not None


def test_register_dotfile(tmp_db):
    src = tmp_db / "zshrc"
    src.write_text("# zsh")
    dst = tmp_db / ".zshrc"
    args = MagicMock(name="zshrc", source=str(src), target=str(dst),
                     category="shell", description="Zsh config", auto=False)
    dm.cmd_register(args)
    db  = dm.get_db()
    row = db.execute("SELECT * FROM dotfiles WHERE name='zshrc'").fetchone()
    assert row is not None
    assert row["category"] == "shell"


def test_register_duplicate_warns(tmp_db, capsys):
    src = tmp_db / "vimrc"
    src.write_text("# vim")
    dst = tmp_db / ".vimrc"
    args = MagicMock(name="vimrc", source=str(src), target=str(dst),
                     category="editor", description="", auto=False)
    dm.cmd_register(args)
    dm.cmd_register(args)   # duplicate
    out = capsys.readouterr()
    assert "already registered" in out.err


def test_link_creates_symlink(tmp_db):
    eid, src, dst = _register(tmp_db, "zshrc")
    args = MagicMock(entry_id=eid)
    dm.cmd_link(args)
    assert dst.is_symlink()
    assert os.readlink(str(dst)) == str(src)


def test_link_already_linked(tmp_db, capsys):
    eid, src, dst = _register(tmp_db, "zshrc2")
    args = MagicMock(entry_id=eid)
    dm.cmd_link(args)
    dm.cmd_link(args)   # second time
    out = capsys.readouterr().out
    assert "already linked" in out


def test_backup_creates_snapshot(tmp_db):
    eid, src, dst = _register(tmp_db)
    args = MagicMock(entry_id=eid, notes="initial")
    dm.cmd_backup(args)
    db  = dm.get_db()
    snaps = db.execute("SELECT * FROM snapshots WHERE entry_id=?", (eid,)).fetchall()
    assert len(snaps) == 1
    assert snaps[0]["notes"] == "initial"


def test_file_hash(tmp_db):
    f = tmp_db / "test.txt"
    f.write_text("hello world")
    h = dm.file_hash(str(f))
    expected = hashlib.sha256(b"hello world").hexdigest()
    assert h == expected


def test_restore_from_snapshot(tmp_db):
    eid, src, dst = _register(tmp_db)
    original = src.read_text()
    # Backup
    args = MagicMock(entry_id=eid, notes="")
    dm.cmd_backup(args)
    # Modify
    src.write_text("# modified")
    # Get snapshot id
    db = dm.get_db()
    snap_id = db.execute("SELECT id FROM snapshots WHERE entry_id=?", (eid,)).fetchone()["id"]
    # Restore
    args2 = MagicMock(entry_id=eid, snapshot_id=snap_id)
    dm.cmd_restore(args2)
    assert src.read_text() == original


def test_export_import_manifest(tmp_db, tmp_path):
    _register(tmp_db, "zshrc")
    out_file = str(tmp_path / "manifest.json")
    args = MagicMock(output=out_file)
    dm.cmd_export_manifest(args)
    assert Path(out_file).exists()
    with open(out_file) as f: data = json.load(f)
    assert len(data) >= 1
    # Clear and re-import
    db = dm.get_db(); db.execute("DELETE FROM dotfiles"); db.commit()
    args2 = MagicMock(file=out_file)
    dm.cmd_import_manifest(args2)
    rows = dm.get_db().execute("SELECT * FROM dotfiles").fetchall()
    assert len(rows) >= 1


def test_categories():
    assert "shell"  in dm.CATEGORIES
    assert "editor" in dm.CATEGORIES
    assert "git"    in dm.CATEGORIES
    assert "tmux"   in dm.CATEGORIES
    assert "tool"   in dm.CATEGORIES
