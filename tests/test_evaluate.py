from pathlib import Path

import pytest

from sipl.interpreter import SiplRuntimeError, run
from sipl.parser import parse
from sipl.semantics import (Evaluation, evaluate, format_state, format_trace, term_of)

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def prog(body):
    return f"begin {body} end"


def final(src, state=None, **kw):
    ev = evaluate(prog(src), state, **kw)
    assert ev.defined, ev.reason
    return ev.final_state


def test_assignment_constant():
    assert final("X := 5") == {"X": 5}


def test_assignment_uses_state():
    assert final("Y := X + 1", {"X": 2}) == {"X": 2, "Y": 3}


def test_sequence_left_to_right():
    assert final("X := 1; X := X + 1; X := X * 3") == {"X": 6}


def test_if_both_branches():
    src = "if X > 0 then Y := 1 else Y := 2"
    assert final(src, {"X": 1})["Y"] == 1
    assert final(src, {"X": 0})["Y"] == 2


def test_while_power():
    src = (EXAMPLES / "power.sipl").read_text(encoding="utf-8")
    assert final(src, {"X": 5, "Y": 2}) == {"X": 5, "Y": 0, "R": 25}


def test_skip_is_identity():
    assert final("skip", {"X": 3}) == {"X": 3}


def test_input_state_is_not_modified():
    state = {"X": 1}
    evaluate(prog("X := 2"), state)
    assert state == {"X": 1}


def test_accepts_ast_term_and_text():
    text = prog("X := 1")
    program = parse(text)
    term = term_of(program)
    assert evaluate(program).value == evaluate(term).value == evaluate(text).value


def test_term_of_condition_gives_bool():
    from sipl.semantics import Const, Deref, Super, Basic
    term = Super(Basic("gr"), (Deref("X"), Const(0)))
    assert evaluate(term, {"X": 2}).value is True
    assert evaluate(term, {"X": 0}).value is False


def test_missing_variable_is_undefined():
    ev = evaluate(prog("Y := X + 1"))
    assert ev.status == "undefined" and not ev.defined
    assert ev.final_state is None
    assert "'X'" in ev.reason


def test_infinite_loop_is_undefined():
    ev = evaluate(prog("while 1 > 0 do X := 1"), {}, max_steps=200)
    assert ev.status == "undefined"
    assert "step limit" in ev.reason


def test_undefined_step_is_unfinished():
    ev = evaluate(prog("Y := X"))
    assert any(not s.finished for s in ev.steps)


def test_or_is_strict():
    ev = evaluate(prog("if 1 > 0 or Z > 0 then X := 1 else skip"), {})
    assert ev.status == "undefined"

def test_trace_first_step_is_the_whole_term():
    ev = evaluate(prog("X := 1; Y := 2"))
    assert ev.steps[0].formula == "AF_SEQ" and ev.steps[0].depth == 0


def test_trace_uses_course_formulas():
    src = (EXAMPLES / "power.sipl").read_text(encoding="utf-8")
    names = {s.formula for s in evaluate(src, {"X": 5, "Y": 2}).steps}
    assert {"AF_SEQ", "AF_AS", "AF_WH", "AF_S", "AF_DNM", "const"} <= names


def test_trace_if_formula():
    ev = evaluate(prog("if X > 0 then Y := 1 else Y := 2"), {"X": 1})
    assert ev.steps[0].formula == "AF_IF"
    assert "first branch" in ev.steps[0].note


def test_trace_skip_formula():
    assert evaluate(prog("skip")).steps[0].formula == "AF_ID"


def test_trace_without_recording():
    ev = evaluate(prog("X := 1"), record=False)
    assert ev.defined and ev.steps == ()


def test_trace_text_course_and_ascii():
    ev = evaluate(prog("X := 1"))
    assert "↦" in format_trace(ev, "course") and "AF_AS" in format_trace(ev)
    ascii_text = format_trace(ev, "ascii")
    assert "->" in ascii_text and "↦" not in ascii_text


def test_trace_text_unknown_style():
    with pytest.raises(ValueError):
        format_trace(evaluate(prog("X := 1")), "bad")


def test_trace_truncates_long_terms():
    ev = evaluate((EXAMPLES / "power.sipl").read_text(encoding="utf-8"), {"X": 2, "Y": 1})
    first = format_trace(ev).splitlines()[0]
    assert "…" in first


def test_format_state():
    assert format_state({"X": 5, "Y": 2}) == "[X ↦ 5, Y ↦ 2]"
    assert format_state({"X": 5}, "ascii") == "[X -> 5]"
    assert format_state({}) == "[]"


def test_to_dict_is_json_ready():
    import json
    data = evaluate(prog("X := 1")).to_dict()
    assert data["status"] == "defined" and data["final_state"] == {"X": 1}
    assert data["steps"][0]["formula"] == "AF_AS"
    json.dumps(data)


def test_evaluation_type():
    assert isinstance(evaluate(prog("skip")), Evaluation)


CASES = [
    ("power.sipl", {"X": 3, "Y": 4}),
    ("gcd.sipl", {"M": 12, "N": 18}),
    ("division.sipl", {"X": 17, "Y": 5}),
]


@pytest.mark.parametrize("name,state", CASES)
def test_same_result_as_interpreter(name, state):
    src = (EXAMPLES / name).read_text(encoding="utf-8")
    try:
        expected = run(src, state)
    except SiplRuntimeError:
        assert not evaluate(src, state).defined
        return
    assert evaluate(src, state).final_state == expected