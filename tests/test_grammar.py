from pathlib import Path

import pytest
from lark import Lark
from lark.exceptions import LarkError

GRAMMAR_PATH = Path(__file__).resolve().parent.parent / "grammar" / "sipl.lark"
PARSER = Lark(GRAMMAR_PATH.read_text(encoding="utf-8"), start="program", parser="lalr")


def accepts(source: str) -> bool:
    try:
        PARSER.parse(source)
    except LarkError:
        return False
    return True


VALID = {
    "minimal_skip": "begin skip end",
    "assign": "begin X := 1 end",
    "sequence": "begin X := 1; Y := 2; Z := X + Y end",
    "if_else": "begin if X > 0 then Y := 1 else Y := 2 end",
    "while": "begin while X > 0 do X := X - 1 end",
    "nested_block": "begin begin X := 1 end end",
    "precedence_mix": "begin X := A + B * C - (D - E) end",
    "compound_condition": "begin if not X = Y or X > 3 then skip else skip end",
    "unicode_operators": "begin if ¬(X = Y) ∨ X > 3 then skip else skip end",
    "power_program": (
        "begin R := 1; while Y > 0 do begin R := R * X; Y := Y - 1 end end"
    ),
    "gcd_program": (
        "begin while not M = N do "
        "if M > N then M := M - N else N := N - M end"
    ),
    "multiline_with_tabs": "begin\n\tX := 1;\n\tY := 2\nend",
}

INVALID = {
    "empty_source": "",
    "no_begin_end": "X := 1",
    "missing_end": "begin X := 1",
    "empty_body": "begin end",
    "semicolon_before_end": "begin X := 1; end",
    "missing_assign_expression": "begin X := end",
    "if_without_else": "begin if X > 0 then Y := 1 end",
    "while_without_do": "begin while X > 0 X := 1 end",
    "unbalanced_parenthesis": "begin X := (1 + 2 end",
    "keyword_as_variable": "begin while := 1 end",
    "bare_expression_as_condition": "begin if X then skip else skip end",
    "double_operator": "begin X := 1 + + 2 end",
    "wrong_assignment_symbol": "begin X = 1 end",
    "trailing_garbage": "begin skip end end",
}


@pytest.mark.parametrize("source", VALID.values(), ids=VALID.keys())
def test_valid_programs_are_accepted(source):
    assert accepts(source)


@pytest.mark.parametrize("source", INVALID.values(), ids=INVALID.keys())
def test_invalid_programs_are_rejected(source):
    assert not accepts(source)


def test_subtraction_is_left_associative():
    tree = PARSER.parse("begin X := A - B - C end")
    expr = tree.children[0].children[1]
    assert expr.data == "sub"
    assert expr.children[0].data == "sub"


def test_multiplication_binds_tighter_than_addition():
    tree = PARSER.parse("begin X := A + B * C end")
    expr = tree.children[0].children[1]
    assert expr.data == "add"
    assert expr.children[1].data == "mul"


def test_semicolon_after_if_ends_the_if_statement():
    tree = PARSER.parse("begin if X > 0 then A := 1 else A := 2; B := 3 end")
    stmt = tree.children[0]
    assert stmt.data == "seq"
    assert stmt.children[0].data == "if_stmt"
    assert stmt.children[1].data == "assign"


def test_while_body_is_a_single_statement():
    tree = PARSER.parse("begin while X > 0 do X := X - 1; Y := 0 end")
    stmt = tree.children[0]
    assert stmt.data == "seq"
    assert stmt.children[0].data == "while_stmt"