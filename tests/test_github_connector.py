import os
import sys
import pytest

pytest.importorskip("git")
from git import Repo

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import tools.github_connector as gh


def test_clone_and_update(tmp_path):
    remote_path = tmp_path / "remote"
    Repo.init(remote_path, bare=True)

    work = Repo.init(tmp_path / "work")
    fpath = tmp_path / "work" / "file.txt"
    fpath.write_text("hello")
    work.index.add([str(fpath)])
    work.index.commit("init")
    work.create_remote("origin", str(remote_path))
    work.git.push("origin", "master:main")

    clone_dir = tmp_path / "clone"
    repo = gh.clone_or_update(str(remote_path), str(clone_dir), branch="main")
    assert (clone_dir / "file.txt").read_text() == "hello"
    assert gh.get_history(repo, 1)[0] == "init"

    # update and push
    fpath.write_text("updated")
    work.index.add([str(fpath)])
    work.index.commit("update")
    work.git.push("origin", "master:main")

    repo = gh.clone_or_update(str(remote_path), str(clone_dir), branch="main")
    assert (clone_dir / "file.txt").read_text() == "updated"
    assert gh.get_history(repo, 2)[0] == "update"
    diff = gh.show_diff(repo)
    assert "updated" in diff

