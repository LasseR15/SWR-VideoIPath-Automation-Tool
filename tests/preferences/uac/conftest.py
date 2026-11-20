from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def uac_payloads() -> dict[str, dict[str, Any]]:
    path = Path(__file__).parent / "fixtures" / "uac_payloads.json"
    with path.open() as handle:
        return json.load(handle)
