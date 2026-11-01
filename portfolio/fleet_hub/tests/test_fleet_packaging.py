"""Regression checks for the embedded Fleet distribution and its SQLite seed."""

from importlib.metadata import distribution
from importlib.resources import files
from pathlib import Path

import fleet_hub
from fleet_hub.services import vor_store


def test_fleet_is_installed_as_a_local_distribution() -> None:
    package = distribution("alextym-fleet-hub")
    assert package.version == "0.1.0"
    assert Path(fleet_hub.__file__).is_file()


def test_immutable_sqlite_seed_is_in_the_distributed_package() -> None:
    seed = files("fleet_hub.services").joinpath("vor_seed.sqlite3")
    assert seed.is_file()
    assert Path(str(seed)).resolve() == vor_store.SEED_FILE.resolve()
