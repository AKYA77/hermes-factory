"""Validated local configuration; no secrets in YAML or untyped overrides."""

from pathlib import Path
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
import yaml
from factory.contracts import SYMBOLS


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["config/v1"] = "config/v1"
    scope: Literal["historical-paper"] = "historical-paper"
    initial_equity: Literal["20"] = "20"
    risk_fraction: Literal["0.10"] = "0.10"
    target_rr: Literal["3"] = "3"
    max_hold_seconds: Literal[86400] = 86400
    instruments: tuple[str, ...] = SYMBOLS
    heavy_workers: Literal[1] = 1
    research_enabled: Literal[False] = False
    historical_import_enabled: Literal[False] = False
    host: Literal["127.0.0.1"] = "127.0.0.1"
    port: int = Field(default=8088, ge=1024, le=65535)


def load(path):
    return Settings.model_validate(yaml.safe_load(Path(path).read_text()))
