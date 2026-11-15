import itertools
import random
from pathlib import Path

import pytest

from sipl.interpreter import SiplRuntimeError, run
from sipl.semantics import (AS, IF, WH, Comp, Const, Deref, Id, Super, term_of)

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"

BASIC = {
    "add": lambda a, b: a + b,
    "sub": lambda a, b: a - b,
    "mult": lambda a, b: a * b,
    "or": lambda a, b: a or b,
    "neg": lambda a: not a,
    "eq": lambda a, b: a == b,
    "gr": lambda a, b: a > b,
}


class Undefined(Exception):
 pass


def apply_term(term, state, fuel=2000):
    if isinstance(term, Const):
        return term.value
    if isinstance(term, Deref):
        if term.name not in state:
            raise Undefined(term.name)
        return state[term.name]
    if isinstance(term, Super):
        return BASIC[term.func.name](*(apply_term(a, state, fuel) for a in term.args))
    if isinstance(term, AS):
        new = dict(state)
        new[term.name] = apply_term(term.func, state, fuel)
        return new
    if isinstance(term, Comp):
        return apply_term(term.right, apply_term(term.left, state, fuel), fuel)
    if isinstance(term, IF):
        branch = term.then_term if apply_term(term.cond, state, fuel) else term.else_term
        return apply_term(branch, state, fuel)
    if isinstance(term, WH):
        current = state
        for _ in range(fuel):
            if not apply_term(term.cond, current, fuel):
                return current
            current = apply_term(term.body, current, fuel)
        raise Undefined("loop did not stop")
    if isinstance(term, Id):
        return state
    raise TypeError(term)


def both(source, initial):
    try:
        by_term = apply_term(term_of(source), initial)
    except Undefined:
        by_term = None
    try:
        by_run = run(source, initial, max_steps=20000)
    except SiplRuntimeError:
        by_run = None
    return by_term, by_run

def test_practicum_power_x5_y2_gives_25():
    source = (EXAMPLES / "power.sipl").read_text(encoding="utf-8")
    final = apply_term(term_of(source), {"X": 5, "Y": 2})
    assert final == {"X": 5, "Y": 0, "R": 25}

@pytest.mark.parametrize("name,variables", [
    ("power.sipl", ("X", "Y")),
    ("gcd.sipl", ("M", "N")),
    ("division.sipl", ("X", "Y")),
])
def test_examples_agree_with_the_interpreter(name, variables):
    source = (EXAMPLES / name).read_text(encoding="utf-8")
    for values in itertools.product(range(1, 7), repeat=2):
        initial = dict(zip(variables, values))
        by_term, by_run = both(source, initial)
        assert by_term == by_run, (name, initial)

def random_aexp(rng, depth):
    if depth == 0 or rng.random() < 0.3:
        return rng.choice(["A", "B", "C", str(rng.randint(0, 5))])
    op = rng.choice(["+", "-", "*"])
    return f"({random_aexp(rng, depth - 1)} {op} {random_aexp(rng, depth - 1)})"


def random_bexp(rng, depth):
    if depth == 0 or rng.random() < 0.4:
        op = rng.choice(["=", ">"])
        return f"({random_aexp(rng, 2)} {op} {random_aexp(rng, 2)})"
    choice = rng.random()
    if choice < 0.5:
        return f"(not {random_bexp(rng, depth - 1)})"
    return f"({random_bexp(rng, depth - 1)} or {random_bexp(rng, depth - 1)})"


def test_random_arithmetic_expressions_agree():
    rng = random.Random(2026)
    for _ in range(150):
        source = f"begin R := {random_aexp(rng, 4)} end"
        initial = {"A": rng.randint(-5, 5), "B": rng.randint(-5, 5), "C": rng.randint(-5, 5)}
        by_term, by_run = both(source, initial)
        assert by_term == by_run, (source, initial)


def test_random_conditions_agree():
    rng = random.Random(7)
    for _ in range(150):
        source = f"begin if {random_bexp(rng, 3)} then R := 1 else R := 0 end"
        initial = {"A": rng.randint(-3, 3), "B": rng.randint(-3, 3), "C": rng.randint(-3, 3)}
        by_term, by_run = both(source, initial)
        assert by_term == by_run, (source, initial)

def test_undefined_variable_is_undefined_in_both():
    by_term, by_run = both("begin X := Y end", {})
    assert by_term is None and by_run is None


def test_loop_that_never_stops_is_undefined_in_both():
    by_term, by_run = both("begin while 1 > 0 do skip end", {})
    assert by_term is None and by_run is None

def test_formula_af_seq_order():
    assert apply_term(term_of("begin X := 1; X := X + 1 end"), {}) == {"X": 2}


def test_formula_af_wh_zero_iterations_returns_the_same_state():
    state = {"X": 0}
    assert apply_term(term_of("begin while X > 0 do X := X - 1 end"), state) == {"X": 0}


def test_formula_af_id():
    assert apply_term(term_of("begin skip end"), {"X": 1}) == {"X": 1}