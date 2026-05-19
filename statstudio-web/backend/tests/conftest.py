"""Shared pytest fixtures: load sample CSVs as DatasetPayload."""
from __future__ import annotations
import os
import pandas as pd
import pytest

from app.utils.dataframe import df_to_payload

SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "samples")


def _load(name: str):
    df = pd.read_csv(os.path.join(SAMPLES_DIR, name))
    return df_to_payload(df, name=name.replace(".csv", ""))


@pytest.fixture(scope="session")
def iris():
    return _load("iris.csv")


@pytest.fixture(scope="session")
def mtcars():
    return _load("mtcars.csv")


@pytest.fixture(scope="session")
def tooth_growth():
    return _load("ToothGrowth.csv")


@pytest.fixture(scope="session")
def air_passengers():
    return _load("AirPassengers.csv")


@pytest.fixture(scope="session")
def usarrests():
    return _load("USArrests.csv")


@pytest.fixture(scope="session")
def spc():
    return _load("spc_bottling.csv")


@pytest.fixture(scope="session")
def doe():
    return _load("doe_factorial_2k.csv")
