import pytest

from sa_paths import format_paths, main, resolve_paths


@pytest.fixture
def repos(tmp_path):
    root = tmp_path / "repos"
    for name in ("lkp-back/.git", "partners-dashboard/.git", ".git", "notes", "system-docs/.git"):
        (root / name).mkdir(parents=True)
    (root / "system-docs/docs").mkdir(parents=True)
    (root / "system-docs/docs/bctc.md").write_text("x", encoding="utf-8")
    return root


def test_default_system_docs(repos):
    p = resolve_paths({"SA_REPOS_ROOT": str(repos)})
    assert p["repos_exists"] is True
    assert p["index_files"] == ["bctc.md"]
    assert p["services"] == ["lkp-back", "partners-dashboard"]
    assert p["not_services"] == ["notes"]
    assert p["system_docs"] == str(repos / "system-docs")
    assert p["index_dir"] == str(repos / "system-docs/docs")


def test_external_system_docs(repos, tmp_path):
    docs = tmp_path / "elsewhere/docs"
    docs.mkdir(parents=True)
    (docs / "bctc.md").write_text("x", encoding="utf-8")
    (docs / "system_tech.md").write_text("x", encoding="utf-8")
    p = resolve_paths({"SA_REPOS_ROOT": str(repos), "SA_SYSTEM_DOCS": str(docs.parent)})
    assert p["index_files"] == ["bctc.md", "system_tech.md"]
    assert "system-docs" in p["services"]


def test_missing_root(tmp_path):
    p = resolve_paths({"SA_REPOS_ROOT": str(tmp_path / "nope")})
    assert p["repos_exists"] is False
    assert p["services"] == []
    assert p["index_files"] == []


def test_home_default(tmp_path):
    p = resolve_paths({"HOME": str(tmp_path)})
    assert p["repos_root"] == str(tmp_path / "repos")


def test_tasks_dir_from_cwd(repos, tmp_path):
    p = resolve_paths({"SA_REPOS_ROOT": str(repos)}, cwd=tmp_path / "work")
    assert p["tasks_dir"] == str(tmp_path / "work" / "tasks")


def test_tilde_uses_env_home(tmp_path):
    p = resolve_paths({"HOME": str(tmp_path), "SA_REPOS_ROOT": "~/r"})
    assert p["repos_root"] == str(tmp_path / "r")


def test_relative_root_made_absolute(tmp_path):
    p = resolve_paths({"HOME": str(tmp_path), "SA_REPOS_ROOT": "rel", "SA_SYSTEM_DOCS": "docs"}, cwd=tmp_path)
    assert p["repos_root"] == str(tmp_path / "rel")
    assert p["system_docs"] == str(tmp_path / "docs")


def test_format(repos, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = format_paths(resolve_paths({"SA_REPOS_ROOT": str(repos)}))
    assert out == (
        f"tasks_dir: {tmp_path / 'tasks'}\n"
        f"repos_root: {repos} (есть)\n"
        f"index_dir: {repos / 'system-docs' / 'docs'}\n"
        "index_files: bctc.md\n"
        "services: lkp-back, partners-dashboard\n"
        "not_services (нет .git): notes"
    )
    missing = tmp_path / "nope"
    out = format_paths(resolve_paths({"SA_REPOS_ROOT": str(missing)}))
    assert out == (
        f"tasks_dir: {tmp_path / 'tasks'}\n"
        f"repos_root: {missing} (нет)\n"
        f"index_dir: {missing / 'system-docs' / 'docs'}\n"
        "index_files: нет\n"
        "services: нет\n"
        "not_services (нет .git): нет"
    )


def test_cli(repos, monkeypatch, capsys):
    monkeypatch.setenv("SA_REPOS_ROOT", str(repos))
    monkeypatch.delenv("SA_SYSTEM_DOCS", raising=False)
    assert main([]) == 0
    assert capsys.readouterr().out.splitlines()[1] == f"repos_root: {repos} (есть)"
    assert main(["x"]) == 2
