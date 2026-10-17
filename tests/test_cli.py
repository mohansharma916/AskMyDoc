import pytest

from askdocs.config import Settings
from askdocs.ingest.__main__ import main
from askdocs.services import Services


@pytest.fixture
def services(embedder):
    settings = Settings(database_url="sqlite:///:memory:", qdrant_url=":memory:")
    return Services(settings, embedder=embedder)


def test_cli_indexes_folder_and_reports(services, tmp_path, capsys):
    (tmp_path / "a.md").write_text("# A\n\nAlpha text.")
    (tmp_path / "b.txt").write_text("Beta text.")
    assert main(["--path", str(tmp_path)], services) == 0
    out = capsys.readouterr().out
    assert "indexed   a.md  (1 chunks)" in out
    assert "2 files: 2 indexed, 0 updated, 0 unchanged, 0 failed; 2 chunks written." in out

    assert main(["--path", str(tmp_path)], services) == 0
    assert "2 unchanged" in capsys.readouterr().out


def test_cli_missing_path_and_failures(services, tmp_path, capsys):
    assert main(["--path", str(tmp_path / "nope")], services) == 2
    (tmp_path / "empty.md").write_text("")
    assert main(["--path", str(tmp_path)], services) == 1
    assert "failed" in capsys.readouterr().out


def test_unknown_override_rejected():
    with pytest.raises(TypeError):
        Services(Settings(), nope=1)
