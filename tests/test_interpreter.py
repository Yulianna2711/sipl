from pathlib import Path

import pytest

from sipl.interpreter import (Interpreter, SiplRuntimeError, StepLimitExceeded,
                              UndefinedVariableError, run)
from sipl.parser import parse

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"

def example(name):
    return (EXAMPLES / name).read_text(encoding="utf-8")

def test_power():
    assert run(example("power.sipl"), {"X": 2, "Y": 5})["R"] == 32

def test_power_with_zero_exponent():
    assert run(example("power.sipl"), {"X": 7, "Y": 0})["R"] == 1

def test_gcd():
    final = run(example("gcd.sipl"), {"M": 12, "N": 18})
    assert final["M"] == final["N"] == 6

def test_division():
    final = run(example("division.sipl"), {"X": 7, "Y": 2})
    assert final["R"] == 3 and final["X"] == 1

def test_skip_keeps_state():
    assert run("begin skip end", {"X": 1}) == {"X": 1}

def test_assign_and_sequence():
    assert run("begin X := 1; Y := X + 2; X := Y * 3 end") == {"X": 9, "Y": 3}

def test_if_then_branch():
    assert run("begin if X > 0 then Y := 1 else Y := 2 end", {"X": 5})["Y"] == 1

def test_if_else_branch():
    assert run("begin if X > 0 then Y := 1 else Y := 2 end", {"X": 0})["Y"] == 2

def test_while_loop_counts_down():
    assert run("begin while X > 0 do X := X - 1 end", {"X": 4}) == {"X": 0}

def test_while_with_false_condition_does_nothing():
    assert run("begin while X > 0 do X := X - 1 end", {"X": 0}) == {"X": 0}

def test_statement_after_if_runs_in_both_cases():
    src = "begin if X > 0 then A := 1 else A := 2; B := 3 end"
    assert run(src, {"X": 1}) == {"X": 1, "A": 1, "B": 3}
    assert run(src, {"X": 0}) == {"X": 0, "A": 2, "B": 3}

def test_subtraction_is_left_associative():
    assert run("begin X := 10 - 3 - 2 end")["X"] == 5

def test_multiplication_before_addition():
    assert run("begin X := 2 + 3 * 4 end")["X"] == 14

def test_parentheses():
    assert run("begin X := (2 + 3) * 4 end")["X"] == 20

def test_negative_results_are_allowed():
    assert run("begin X := 2 - 5 end")["X"] == -3

def test_conditions_or_not_eq():
    src = "begin if not X = 1 or Y > 5 then R := 1 else R := 0 end"
    assert run(src, {"X": 1, "Y": 0})["R"] == 0
    assert run(src, {"X": 2, "Y": 0})["R"] == 1
    assert run(src, {"X": 1, "Y": 9})["R"] == 1

def test_initial_state_is_not_modified():
    initial = {"X": 1}
    run("begin X := 2 end", initial)
    assert initial == {"X": 1}

def test_run_accepts_ast_and_source():
    src = "begin X := 1 end"
    assert run(parse(src)) == run(src) == {"X": 1}

def test_interpreter_object_keeps_final_state():
    interp = Interpreter({"X": 3})
    interp.run(parse("begin Y := X * 2 end"))
    assert interp.state == {"X": 3, "Y": 6}

def test_undefined_variable():
    with pytest.raises(UndefinedVariableError) as info:
        run("begin X := Y + 1 end")
    assert info.value.name == "Y"
    assert info.value.span.start_column == 12

def test_undefined_variable_is_a_runtime_error():
    with pytest.raises(SiplRuntimeError):
        run("begin X := Y end")

def test_infinite_loop_hits_step_limit():
    with pytest.raises(StepLimitExceeded) as info:
        run("begin while 1 > 0 do skip end", max_steps=50)
    assert info.value.limit == 50

def test_step_limit_not_hit_by_short_program():
    assert run("begin X := 1 end", max_steps=1) == {"X": 1}