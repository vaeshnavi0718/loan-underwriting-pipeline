"""Keeps the eval case file in sync with the synthetic fixtures."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from evals.cases import load_cases
from evals.harness import list_cases


def test_case_file_loads_and_validates():
    assert load_cases()


def test_every_fixture_has_exactly_one_case():
    assert sorted(load_cases()) == list_cases()
