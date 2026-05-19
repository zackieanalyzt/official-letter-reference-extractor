from pathlib import Path


def test_traversal_modules_do_not_import_network_clients():
    traversal_files = Path("app/traversal").glob("*.py")

    combined = "\n".join(path.read_text(encoding="utf-8") for path in traversal_files)

    assert "httpx" not in combined
    assert "requests" not in combined
    assert "urlopen" not in combined
