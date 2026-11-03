from assistd.rules import Rules
from assistd.tools import (INTERACTIVE_TOOLS, READ_TOOLS, WRITE_TOOLS, Sandbox, effective_tools,
                           unknown_tool_names)
from conftest import make_dir_link, write

ALL = list(READ_TOOLS + WRITE_TOOLS)


def sandbox(root, enabled=None, **kw) -> Sandbox:
    return Sandbox(root, Rules.load(root), enabled or ALL, **kw)


def test_rules_hidden_and_readonly(checkout):
    rules = Rules.load(checkout)
    assert rules.is_hidden("Scripts", True)
    assert rules.is_hidden("Scripts/run.ps1")
    assert rules.is_hidden(".git/config")
    assert not rules.is_hidden("Mathe/notes.md")
    assert rules.is_readonly("Mathe/Lehrplan-Gymnasium/Klasse-8.md")
    assert rules.is_readonly("AGENTS.md") and rules.is_readonly("Mathe/AGENTS.md")
    assert rules.is_readonly(".family_assist.yaml")


def test_negation_cannot_lift_builtin_protection(checkout):
    write(checkout, ".family_assist.yaml", "readonly:\n  - '!AGENTS.md'\n  - '!.family_assist.yaml'\n")
    rules = Rules.load(checkout)
    assert rules.is_readonly("AGENTS.md") and rules.is_readonly(".family_assist.yaml")


def test_invalid_config_is_ignored_with_warning(checkout):
    write(checkout, ".family_assist.yaml", "hidden: [unclosed\n")
    rules = Rules.load(checkout)
    assert not rules.is_hidden("Scripts") and rules.warnings
    write(checkout, ".family_assist.yaml", "tools: read_file\n")
    rules = Rules.load(checkout)
    assert rules.tools is None and rules.warnings


def test_hiding_root_agents_md_is_ignored_with_warning(checkout):
    write(checkout, ".family_assist.yaml", "hidden:\n  - AGENTS.md\n")
    rules = Rules.load(checkout)
    assert not rules.is_hidden("AGENTS.md")
    assert rules.warnings


def test_list_dir_hides_hidden_paths(checkout):
    out = sandbox(checkout).execute("list_dir", {"path": ""}).text.splitlines()
    assert "Scripts/" not in out and ".git/" not in out
    assert "Mathe/" in out and "notes.md" in out


def test_hidden_looks_nonexistent(checkout):
    sb = sandbox(checkout)
    for name, args in [("read_file", {"path": "Scripts/run.ps1"}), ("list_dir", {"path": "Scripts"}),
                       ("read_file", {"path": ".git/config"}),
                       ("create_file", {"path": "Scripts/new.md", "content": "x"})]:
        res = sb.execute(name, args)
        assert not res.ok and res.text.startswith("Error: not found")
    assert not (checkout / "Scripts" / "new.md").exists()


def test_find_and_grep_skip_hidden(checkout):
    sb = sandbox(checkout)
    assert "Scripts" not in sb.execute("find", {"pattern": "*.ps1"}).text
    grep = sb.execute("grep", {"pattern": "secret"}).text
    assert grep == "(no matches)"
    grep = sb.execute("grep", {"pattern": "BRUCH", "glob": "*.md"}).text
    assert "Mathe/Klasse-8/Marten/a.md:1" in grep and "Lehrplan-Gymnasium" in grep
    assert "Mathe/Klasse-8/" in sb.execute("find", {"pattern": "Klasse-8/"}).text


def test_path_escape_attempts(checkout, tmp_path):
    (tmp_path / "outside.txt").write_text("top secret")
    sb = sandbox(checkout)
    for path in ["../outside.txt", "Mathe/../../outside.txt", "/etc/passwd", "..\\outside.txt"]:
        assert not sb.execute("read_file", {"path": path}).ok


def test_linked_folder_cannot_escape(checkout, tmp_path):
    outside = tmp_path / "outside"
    write(outside, "secret.txt", "top secret")
    make_dir_link(checkout / "escape", outside)
    sb = sandbox(checkout)
    for name, args in [("read_file", {"path": "escape/secret.txt"}), ("list_dir", {"path": "escape"}),
                       ("write_file", {"path": "escape/new.txt", "content": "x"})]:
        res = sb.execute(name, args)
        assert not res.ok and "top secret" not in res.text
    assert not (outside / "new.txt").exists()
    assert "top secret" not in sb.execute("grep", {"pattern": "secret"}).text


def test_link_to_hidden_folder_is_blocked(checkout):
    make_dir_link(checkout / "alias", checkout / "Scripts")
    assert not sandbox(checkout).execute("read_file", {"path": "alias/run.ps1"}).ok


def test_read_file_range_and_truncation(checkout):
    sb = sandbox(checkout)
    assert sb.execute("read_file", {"path": "notes.md", "start_line": 2, "end_line": 2}).text == "beta\n[lines 2-2 of 3]"
    big = sandbox(checkout, max_result_bytes=10)
    assert "truncated" in big.execute("read_file", {"path": "notes.md"}).text


def test_write_tools(checkout):
    sb = sandbox(checkout)
    res = sb.execute("create_file", {"path": "Mathe/Klasse-8/Marten/b.md", "content": "hi"})
    assert res.ok and res.changed == ("Mathe/Klasse-8/Marten/b.md",)
    assert not sb.execute("create_file", {"path": "Mathe/Klasse-8/Marten/b.md", "content": "x"}).ok
    assert sb.execute("append_file", {"path": "Mathe/Klasse-8/Marten/b.md", "content": "!"}).ok
    assert (checkout / "Mathe/Klasse-8/Marten/b.md").read_text() == "hi!"
    assert sb.execute("write_file", {"path": "Mathe/Klasse-8/Marten/b.md", "content": "new"}).ok
    assert (checkout / "Mathe/Klasse-8/Marten/b.md").read_text() == "new"


def test_readonly_and_builtin_protection(checkout):
    sb = sandbox(checkout)
    for path in ["Mathe/Lehrplan-Gymnasium/Klasse-8.md", "Mathe/Lehrplan-Gymnasium/new.md", "AGENTS.md",
                 "Mathe/AGENTS.md", ".family_assist.yaml"]:
        res = sb.execute("write_file", {"path": path, "content": "x"})
        assert not res.ok and "read-only" in res.text, path
    assert (checkout / "AGENTS.md").read_text().startswith("---")
    assert "bruch" in sb.execute("read_file", {"path": "Mathe/Lehrplan-Gymnasium/Klasse-8.md"}).text


def test_replace_in_file_multiple_is_atomic(checkout):
    sb = sandbox(checkout)
    ok = sb.execute("replace_in_file", {"path": "notes.md", "edits": [
        {"old_string": "alpha", "new_string": "A"}, {"old_string": "gamma", "new_string": "G"}]})
    assert ok.ok and (checkout / "notes.md").read_text() == "A\nbeta\nG\n"
    bad = sb.execute("replace_in_file", {"path": "notes.md", "edits": [
        {"old_string": "A", "new_string": "x"}, {"old_string": "missing", "new_string": "y"}]})
    assert not bad.ok and (checkout / "notes.md").read_text() == "A\nbeta\nG\n"
    single = sb.execute("replace_in_file", {"path": "notes.md", "old_string": "beta", "new_string": "B"})
    assert single.ok
    write(checkout, "dup.md", "x x")
    assert not sb.execute("replace_in_file", {"path": "dup.md", "old_string": "x", "new_string": "y"}).ok


def test_size_limit_and_bad_arguments(checkout):
    sb = sandbox(checkout)
    assert not sb.execute("write_file", {"path": "big.md", "content": "x" * (256 * 1024 + 1)}).ok
    assert not sb.execute("read_file", {"wrong": 1}).ok
    assert not sb.execute("read_file", "not json").ok


def test_tool_allowlist(checkout):
    sb = sandbox(checkout, enabled=["read_file"])
    assert sb.execute("grep", {"pattern": "a"}).text == "Error: unknown tool 'grep'"
    assert sb.execute("bash", {"cmd": "ls"}).text == "Error: unknown tool 'bash'"
    assert sb.execute("read_file", {"path": "notes.md"}).ok


def test_effective_tools_follow_commit_permission_and_agenttools(checkout):
    rules = Rules.load(checkout)
    assert effective_tools(rules, False) == list(READ_TOOLS + INTERACTIVE_TOOLS)
    assert effective_tools(rules, True) == list(READ_TOOLS + INTERACTIVE_TOOLS + WRITE_TOOLS)
    write(checkout, ".family_assist.yaml", "tools:\n  - list_dir\n  - read_file\n  - write_file\n  - bash\n")
    rules = Rules.load(checkout)
    assert effective_tools(rules, False) == ["list_dir", "read_file"]
    assert effective_tools(rules, True) == ["list_dir", "read_file", "write_file"]
    assert unknown_tool_names(rules) == ["bash"]


def test_read_instructions_respects_hidden(checkout):
    sb = sandbox(checkout)
    assert sb.read_instructions("Mathe") == "Mathe rules"
    assert sb.read_instructions("Scripts") is None
