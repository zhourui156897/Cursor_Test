"""Configuration loader: reads .env + YAML config files with hot-reload support."""

from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache

import yaml
from pydantic_settings import BaseSettings
from pydantic import Field


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    # Auth
    auth_mode: str = Field(default="single", description="single or multi")
    admin_username: str = "admin"
    admin_password: str = "changeme"
    jwt_secret: str = "please-change-this-to-a-random-string"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24h

    # Paths
    obsidian_vault_path: str = "~/Documents/ObsidianVault"
    data_dir: str = "~/.dierdanao/data"

    # Ports
    backend_port: int = 8000
    frontend_port: int = 3000
    milvus_port: int = 19530

    # Vector DB
    vector_db_mode: str = "milvus-lite"

    # LLM
    llm_api_url: str = "http://localhost:11434/v1"
    llm_model: str = "qwen2.5"
    embedding_model: str = "bge-m3"
    embedding_dim: int = 1024

    # Neo4j
    neo4j_user: str = "neo4j"
    neo4j_password: str = "dierdanao123"
    neo4j_uri: str = "bolt://localhost:7687"

    model_config = {"env_file": str(_project_root() / ".env"), "env_file_encoding": "utf-8", "extra": "ignore"}

    @property
    def resolved_data_dir(self) -> Path:
        return Path(self.data_dir).expanduser().resolve()

    @property
    def resolved_vault_path(self) -> Path:
        return Path(self.obsidian_vault_path).expanduser().resolve()

    @property
    def db_path(self) -> Path:
        return self.resolved_data_dir / "dierdanao.db"


@lru_cache()
def get_settings() -> Settings:
    settings = Settings()
    _apply_user_overrides(settings)
    return settings


def _apply_user_overrides(settings: Settings):
    """Apply user_config.yaml llm/paths overrides onto Settings."""
    cfg_path = _project_root() / "backend" / "config" / "user_config.yaml"
    if not cfg_path.exists():
        return
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        return

    llm = data.get("llm", {})
    if llm.get("api_url"):
        settings.llm_api_url = llm["api_url"]
    if llm.get("model"):
        settings.llm_model = llm["model"]
    if llm.get("embedding_model"):
        settings.embedding_model = llm["embedding_model"]
    if llm.get("embedding_dim"):
        settings.embedding_dim = llm["embedding_dim"]

    paths = data.get("paths", {})
    if paths.get("obsidian_vault_path"):
        settings.obsidian_vault_path = paths["obsidian_vault_path"]
    if paths.get("data_dir"):
        settings.data_dir = paths["data_dir"]


class UserConfig:
    """Loads and manages user_config.yaml (tag system, sync rules, roles)."""

    def __init__(self, config_path: Path | None = None):
        self._config_path = config_path or (
            _project_root() / "backend" / "config" / "user_config.yaml"
        )
        self._data: dict = {}
        self.reload()

    def reload(self):
        if self._config_path.exists():
            with open(self._config_path, "r", encoding="utf-8") as f:
                self._data = yaml.safe_load(f) or {}
        else:
            self._data = {}

    def save(self):
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._config_path, "w", encoding="utf-8") as f:
            yaml.dump(self._data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    @property
    def data(self) -> dict:
        return self._data

    @data.setter
    def data(self, value: dict):
        self._data = value

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value):
        self._data[key] = value


_user_config: UserConfig | None = None


def get_user_config() -> UserConfig:
    global _user_config
    if _user_config is None:
        _user_config = UserConfig()
    return _user_config
