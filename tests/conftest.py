import json
import pathlib

import pytest

from gladiatus_sim import Fighter

ROOT = pathlib.Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def report():
    data = json.load(open(ROOT / "examples" / "turma_report_114889279.json"))
    data["att"] = [Fighter.from_dict(d) for d in data["attackers"]]
    data["dfn"] = [Fighter.from_dict(d) for d in data["defenders"]]
    return data
