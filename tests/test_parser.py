from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from sipl.ast import Num, Program, Seq, If
from sipl.diagnostics import SiplSyntaxError
from sipl.parser import parse

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def strip_spans(node):
    if isinstance(node, tuple):
        return tuple(strip_spans(n) for n in node)
    if hasattr(node, "__dataclass_fields__"):
        return (type(node).__name__,) + tuple(
            strip_spans(getattr(node, f)) for f in node.__dataclass_fields__ if f != "span"
        )
    return node


def body(source):
    return strip_spans(parse(source).body)

def test_power_program_ast():
    prog = parse((EXAMPLES / "power.sipl").read_text(encoding="utf-8"))
    assert isinstance(prog, Program)
    assert strip_spans(prog.body) == (
        "Seq",
        (
            ("Assign", "R", ("Num", 1)),
            (
                "While",
                ("Gt", ("Var", "Y"), ("Num", 0)),
                (
                    "Seq",
                    (
                        ("Assign", "R", ("Mul", ("Var", "R"), ("Var", "X"))),
                        ("Assign", "Y", ("Sub", ("Var", "Y"), ("Num", 1))),
                    ),
                ),
            ),
        ),
    )


def test_gcd_program_ast():
    prog = parse((EXAMPLES / "gcd.sipl").read_text(encoding="utf-8"))
    assert strip_spans(prog.body) == (
        "While",
        ("Not", ("Eq", ("Var", "M"), ("Var", "N"))),
        (
            "If",
            ("Gt", ("Var", "M"), ("Var", "N")),
            ("Assign", "M", ("Sub", ("Var", "M"), ("Var", "N"))),
            ("Assign", "N", ("Sub", ("Var", "N"), ("Var", "M"))),
        ),
    )


def test_division_example_parses():
    parse((EXAMPLES / "division.sipl").read_text(encoding="utf-8"))

def test_skip():
    assert body("begin skip end") == ("Skip",)


def test_subtraction_is_left_associative():
    assert body("begin X := A - B - C end") == (
        "Assign", "X", ("Sub", ("Sub", ("Var", "A"), ("Var", "B")), ("Var", "C")))


def test_mul_binds_tighter_than_add():
    assert body("begin X := A + B * C end") == (
        "Assign", "X", ("Add", ("Var", "A"), ("Mul", ("Var", "B"), ("Var", "C"))))


def test_parentheses_change_grouping():
    assert body("begin X := (A + B) * C end") == (
        "Assign", "X", ("Mul", ("Add", ("Var", "A"), ("Var", "B")), ("Var", "C")))


def test_not_binds_tighter_than_or():
    assert body("begin while not A = 1 or B > 2 do skip end") == (
        "While",
        ("Or", ("Not", ("Eq", ("Var", "A"), ("Num", 1))), ("Gt", ("Var", "B"), ("Num", 2))),
        ("Skip",),
    )


def test_unicode_operators_same_as_words():
    assert body("begin while ¬ A = 1 ∨ B > 2 do skip end") == body(
        "begin while not A = 1 or B > 2 do skip end")


def test_semicolon_after_if_leaves_the_if():
    tree = parse("begin if A > 0 then A := 1 else A := 2; B := 3 end").body
    assert isinstance(tree, Seq) and isinstance(tree.stmts[0], If)


def test_nested_block_is_transparent():
    assert body("begin begin X := 1 end end") == body("begin X := 1 end")


def test_numbers_are_ints():
    expr = parse("begin X := 007 end").body.expr
    assert isinstance(expr, Num) and expr.value == 7

def test_spans_are_correct():
    prog = parse("begin\n  X := A + 12\nend")
    assign = prog.body
    assert (assign.span.start_line, assign.span.start_column) == (2, 3)
    assert (assign.span.end_line, assign.span.end_column) == (2, 14)
    num = assign.expr.right
    assert (num.span.start_column, num.span.end_column) == (12, 14)
    assert (prog.span.start_line, prog.span.end_line, prog.span.end_column) == (1, 3, 4)


def test_nodes_are_frozen():
    node = parse("begin skip end").body
    with pytest.raises(FrozenInstanceError):
        node.span = None

def err(source):
    with pytest.raises(SiplSyntaxError) as info:
        parse(source)
    return info.value.diagnostic


def test_diagnostic_unexpected_token_has_position_and_expected():
    d = err("begin X := end")
    assert (d.line, d.column) == (1, 12)
    assert "end" in d.message
    assert "number" in d.expected and "variable name" in d.expected


def test_diagnostic_unexpected_character():
    d = err("begin X := 1 $ end")
    assert (d.line, d.column) == (1, 14)
    assert "'$'" in d.message


def test_diagnostic_unexpected_end_of_input():
    d = err("begin X := 1")
    assert "end of input" in d.message
    assert "'end'" in d.expected


def test_diagnostic_empty_source():
    assert err("").expected == ("'begin'",)


def test_diagnostic_multiline_position():
    d = err("begin\n  X := 1;\n  Y := \nend")
    assert d.line == 4


def test_diagnostic_format_has_caret():
    text = err("begin X := end").format()
    lines = text.splitlines()
    assert lines[-1].strip() == "^"
    assert lines[-1].index("^") == 11
    assert "Expected:" in text


def test_diagnostic_to_dict():
    d = err("begin X := end").to_dict()
    assert set(d) == {"line", "column", "message", "expected"}