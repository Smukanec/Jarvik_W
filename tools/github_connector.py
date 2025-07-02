import os
from typing import List, Optional

from git import Repo
import requests


def clone_or_update(repo_url: str, dest: str, branch: str = "main", token: Optional[str] = None) -> Repo:
    """Clone *repo_url* into *dest* or update if it already exists."""
    if token and repo_url.startswith("https://") and "@" not in repo_url:
        prefix = repo_url.replace("https://", f"https://{token}@")
        repo_url = prefix

    if os.path.exists(dest):
        repo = Repo(dest)
        origin = repo.remotes.origin
        origin.fetch()
        repo.git.checkout(branch)
        origin.pull()
    else:
        repo = Repo.clone_from(repo_url, dest, branch=branch)
    return repo


def show_diff(repo: Repo, commit_range: str = "HEAD~1..HEAD") -> str:
    """Return diff for *commit_range* in *repo*."""
    return repo.git.diff(commit_range)


def get_history(repo: Repo, max_count: int = 10) -> List[str]:
    """Return last *max_count* commit messages."""
    return [c.message.strip() for c in repo.iter_commits(max_count=max_count)]


def push_branch(repo: Repo, branch: str, token: str) -> None:
    """Push *branch* using authentication *token*."""
    url = repo.remotes.origin.url
    if token and url.startswith("https://") and "@" not in url:
        url = url.replace("https://", f"https://{token}@")
    repo.git.push(url, f"HEAD:{branch}")


def open_pull_request(repo_url: str, title: str, body: str, head: str, base: str, token: str) -> dict:
    """Create a pull request on GitHub."""
    api_url = repo_url.rstrip("/").replace("https://github.com", "https://api.github.com/repos") + "/pulls"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}
    data = {"title": title, "body": body, "head": head, "base": base}
    resp = requests.post(api_url, json=data, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()
