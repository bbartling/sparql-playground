from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BRICKTS_", env_file=".env", extra="ignore")

    data_dir: Path = Path("data")
    db_path: Path = Path("var/timeseries.sqlite")
    model_path: Path = Path("model/building_50.ttl")
    site_model_path: Path = Path("model/site.ttl")
    points_dir: Path = Path("model/points")
    datasets_path: Path = Path("data/datasets.json")
    snapshot_path: Path = Path("var/graph.snapshot.ttl")

    serialize_interval_s: int = 60
    serialize_on_mutation: bool = True
    bootstrap_on_startup: bool = True

    sparql_max_rows: int = 10000
    sparql_timeout_s: float = 10.0
    sparql_max_query_chars: int = 20000
    sparql_max_concurrency: int = 4

    timeseries_max_rows: int = 200000
    allow_mutations: bool = False

    log_level: str = "INFO"
    log_json: bool = True

    host: str = "127.0.0.1"
    port: int = 8000

    def resolve(self, root: Path | None = None) -> "Settings":
        if root is None:
            return self
        data = self.model_dump()

        def _p(key: str) -> None:
            val = data[key]
            if isinstance(val, Path) and not val.is_absolute():
                data[key] = root / val

        for k in (
            "data_dir",
            "db_path",
            "model_path",
            "site_model_path",
            "points_dir",
            "datasets_path",
            "snapshot_path",
        ):
            _p(k)
        return Settings(**data)


def get_settings() -> Settings:
    return Settings()
