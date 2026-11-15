import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "conformance"))
import run_conformance as rc

CMD = rc.DEFAULT_CMD
CASES = rc.load_cases()


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_conformance(case):
    problems = rc.check(case, rc.execute(CMD, case))
    assert not problems, "\n".join(problems)