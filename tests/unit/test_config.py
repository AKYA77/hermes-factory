from factory.config import load


def test_default_config():
    settings = load("config/default.yaml")
    assert settings.scope == "historical-paper"
    assert settings.historical_import_enabled is False
    assert settings.heavy_workers == 1
