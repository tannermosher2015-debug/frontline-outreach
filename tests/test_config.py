from outreach.config import load_config

def test_load_config_reads_toml(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('batch_size = 7\n[weights]\nno_website = 99\n', encoding="utf-8")
    cfg = load_config(str(p))
    assert cfg["batch_size"] == 7
    assert cfg["weights"]["no_website"] == 99

def test_load_config_missing_file_raises(tmp_path):
    import pytest
    with pytest.raises(FileNotFoundError):
        load_config(str(tmp_path / "nope.toml"))
