import json
from pathlib import Path

import pytest

from sipl.interpreter import run, trace
from sipl.diagnostics import SiplSyntaxError

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def types(t):
    return [e.type for e in t.events]


def test_assign_event_order():
    t = trace("begin X := 1 end")
    assert types(t) == [
        "program_started",
        "before_statement",
        "variable_changed",
        "after_statement",
        "program_finished",
    ]


def test_variable_changed_has_old_and_new():
    t = trace("begin X := X + 1 end", {"X": 4})
    change = t.of_type("variable_changed")[0]
    assert (change.name, change.old, change.new) == ("X", 4, 5)


def test_new_variable_has_old_none():
    change = trace("begin X := 1 end").of_type("variable_changed")[0]
    assert change.old is None and change.new == 1


def test_before_and_after_snapshots_differ():
    t = trace("begin X := 1 end")
    before = t.of_type("before_statement")[0]
    after = t.of_type("after_statement")[0]
    assert before.state == {} and after.state == {"X": 1}
    assert before.kind == after.kind == "assign"


def test_snapshots_are_independent_copies():
    t = trace("begin X := 1; X := 2 end")
    states = [e.state for e in t.of_type("after_statement")]
    assert states == [{"X": 1}, {"X": 2}]


def test_sequence_has_no_events_of_its_own():
    t = trace("begin X := 1; Y := 2 end")
    kinds = [e.kind for e in t.of_type("before_statement")]
    assert kinds == ["assign", "assign"]


def test_if_condition_event_true_and_false():
    src = "begin if X > 0 then Y := 1 else Y := 2 end"
    yes = trace(src, {"X": 1}).of_type("condition_evaluated")
    no = trace(src, {"X": 0}).of_type("condition_evaluated")
    assert [(e.kind, e.result) for e in yes] == [("if", True)]
    assert [(e.kind, e.result) for e in no] == [("if", False)]


def test_while_condition_checked_n_plus_one_times():
    t = trace("begin while X > 0 do X := X - 1 end", {"X": 3})
    results = [e.result for e in t.of_type("condition_evaluated")]
    assert results == [True, True, True, False]


def test_while_statement_wraps_its_body():
    t = trace("begin while X > 0 do X := X - 1 end", {"X": 1})
    kinds = [(e.type, getattr(e, "kind", None)) for e in t.events]
    assert kinds[1] == ("before_statement", "while")
    assert kinds[-2] == ("after_statement", "while")


def test_finished_ok_with_final_state():
    t = trace("begin X := 2 * 3 end")
    assert t.status == "ok"
    assert t.final_state == {"X": 6}
    assert types(t)[-1] == "program_finished"


def test_trace_matches_run_on_examples():
    for name, initial in [("power.sipl", {"X": 2, "Y": 5}),
                          ("gcd.sipl", {"M": 12, "N": 18}),
                          ("division.sipl", {"X": 7, "Y": 2})]:
        src = (EXAMPLES / name).read_text(encoding="utf-8")
        assert trace(src, initial).final_state == run(src, initial)


def test_undefined_variable_ends_trace_with_error():
    t = trace("begin X := Y end")
    assert t.status == "error"
    assert "Y" in t.finished.error
    assert t.finished.error_span.start_column == 12
    assert t.of_type("variable_changed") == []


def test_step_limit_ends_trace_with_step_limit_status():
    t = trace("begin while 1 > 0 do skip end", max_steps=10)
    assert t.status == "step_limit"
    assert t.finished.step >= 10


def test_syntax_error_still_raises():
    with pytest.raises(SiplSyntaxError):
        trace("begin X := end")


def test_trace_is_json_serializable():
    t = trace("begin X := 1; while X > 0 do X := X - 1 end")
    data = json.loads(json.dumps(t.to_dict()))
    assert data["status"] == "ok"
    assert data["final_state"] == {"X": 0}
    assert data["events"][0]["type"] == "program_started"
    first_before = next(e for e in data["events"] if e["type"] == "before_statement")
    assert first_before["span"]["start_line"] == 1


def test_error_trace_is_json_serializable():
    data = json.loads(json.dumps(trace("begin X := Y end").to_dict()))
    assert data["status"] == "error"
    assert data["events"][-1]["error_span"]["start_column"] == 12


def test_listener_receives_events_from_run():
    seen = []
    run("begin X := 1 end", listener=seen.append)
    assert seen[0].type == "program_started" and seen[-1].type == "program_finished"


def test_steps_are_non_decreasing():
    t = trace("begin X := 3; while X > 0 do X := X - 1 end")
    steps = [e.step for e in t.events]
    assert steps == sorted(steps)