import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from sipl.diagnostics import SiplSyntaxError
from sipl.parser import parse
from sipl.semantics import (AS, IF, WH, Basic, Comp, Const, Deref, Id, Super,
                            explain, format_term, sem_A, sem_B, term_of,
                            term_to_dict)

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def example(name):
    return (EXAMPLES / name).read_text(encoding="utf-8")


def course(source):
    return format_term(term_of(source))


def ascii_(source):
    return format_term(term_of(source), "ascii")

def test_golden_power_matches_the_practicum():
    assert course(example("power.sipl")) == (
        "AS_R(1) · WH(S²(gr, Y⇒, 0), "
        "AS_R(S²(mult, R⇒, X⇒)) · AS_Y(S²(sub, Y⇒, 1)))"
    )


def test_golden_power_ascii():
    assert ascii_(example("power.sipl")) == (
        "AS_R(1) ; WH(S2(gr, Y=>, 0), "
        "AS_R(S2(mult, R=>, X=>)) ; AS_Y(S2(sub, Y=>, 1)))"
    )


def test_golden_gcd():
    assert course(example("gcd.sipl")) == (
        "WH(S¹(neg, S²(eq, M⇒, N⇒)), "
        "IF(S²(gr, M⇒, N⇒), AS_M(S²(sub, M⇒, N⇒)), AS_N(S²(sub, N⇒, M⇒))))"
    )


def test_golden_division():
    assert course(example("division.sipl")) == (
        "AS_R(0) · WH(S²(or, S²(gr, X⇒, Y⇒), S²(eq, X⇒, Y⇒)), "
        "AS_X(S²(sub, X⇒, Y⇒)) · AS_R(S²(add, R⇒, 1)))"
    )

def test_rule_skip():
    assert course("begin skip end") == "id"


def test_rule_assign_number():
    assert course("begin X := 5 end") == "AS_X(5)"


def test_rule_assign_variable():
    assert course("begin X := Y end") == "AS_X(Y⇒)"


def test_rule_add_sub_mult():
    assert course("begin X := A + B end") == "AS_X(S²(add, A⇒, B⇒))"
    assert course("begin X := A - B end") == "AS_X(S²(sub, A⇒, B⇒))"
    assert course("begin X := A * B end") == "AS_X(S²(mult, A⇒, B⇒))"


def test_rule_if():
    assert course("begin if X > 0 then Y := 1 else Y := 2 end") == (
        "IF(S²(gr, X⇒, 0), AS_Y(1), AS_Y(2))")


def test_rule_while():
    assert course("begin while X > 0 do X := X - 1 end") == (
        "WH(S²(gr, X⇒, 0), AS_X(S²(sub, X⇒, 1)))")


def test_rule_eq_or_neg():
    src = "begin if not A = 1 or B > 2 then skip else skip end"
    assert course(src) == (
        "IF(S²(or, S¹(neg, S²(eq, A⇒, 1)), S²(gr, B⇒, 2)), id, id)")

def test_subtraction_is_left_associative_in_the_term():
    assert course("begin X := A - B - C end") == (
        "AS_X(S²(sub, S²(sub, A⇒, B⇒), C⇒))")


def test_multiplication_binds_tighter_in_the_term():
    assert course("begin X := A + B * C end") == (
        "AS_X(S²(add, A⇒, S²(mult, B⇒, C⇒)))")


def test_parentheses_change_the_term():
    assert course("begin X := (A + B) * C end") == (
        "AS_X(S²(mult, S²(add, A⇒, B⇒), C⇒))")


def test_sequence_of_three_is_left_nested_without_parentheses():
    assert course("begin A := 1; B := 2; C := 3 end") == (
        "AS_A(1) · AS_B(2) · AS_C(3)")
    term = term_of("begin A := 1; B := 2; C := 3 end")
    assert isinstance(term, Comp) and isinstance(term.left, Comp)
    assert not isinstance(term.right, Comp)


def test_block_on_the_right_gets_parentheses():
    assert course("begin X := 1; begin Y := 2; Z := 3 end end") == (
        "AS_X(1) · (AS_Y(2) · AS_Z(3))")


def test_outer_begin_end_and_block_do_not_change_the_term():
    assert course("begin begin X := 1 end end") == course("begin X := 1 end")


def test_unicode_operators_give_the_same_term():
    assert course("begin if ¬ A = 1 ∨ B > 2 then skip else skip end") == course(
        "begin if not A = 1 or B > 2 then skip else skip end")

def test_term_node_types():
    term = term_of("begin while X > 0 do X := X - 1 end")
    assert isinstance(term, WH)
    assert isinstance(term.cond, Super) and term.cond.n == 2
    assert term.cond.func == Basic("gr")
    assert term.cond.args == (Deref("X"), Const(0))
    assert isinstance(term.body, AS) and term.body.name == "X"


def test_if_and_id_types():
    term = term_of("begin if X = 1 then skip else skip end")
    assert isinstance(term, IF)
    assert term.then_term == Id() and term.else_term == Id()


def test_terms_are_equal_when_structure_is_equal():
    assert term_of("begin X := 1 end") == term_of("begin   X   :=   1   end")
    assert term_of("begin X := 1 end") != term_of("begin X := 2 end")


def test_terms_are_frozen():
    with pytest.raises(FrozenInstanceError):
        Const(1).value = 2


def test_unknown_base_function_is_rejected():
    with pytest.raises(ValueError):
        Basic("div")


def test_sem_a_and_sem_b_work_on_parts_of_the_ast():
    program = parse("begin if A > 1 then X := B * 2 else skip end")
    branch = program.body
    assert format_term(sem_B(branch.cond)) == "S²(gr, A⇒, 1)"
    assert format_term(sem_A(branch.then_branch.expr)) == "S²(mult, B⇒, 2)"


def test_term_of_accepts_ast_and_source():
    src = "begin X := 1 end"
    assert term_of(parse(src)) == term_of(src)


def test_syntax_error_is_propagated():
    with pytest.raises(SiplSyntaxError):
        term_of("begin X := end")


def test_non_ast_input_is_rejected():
    with pytest.raises(TypeError):
        sem_A("not an ast")

def test_ascii_style_is_pure_ascii():
    for name in ("power.sipl", "gcd.sipl", "division.sipl"):
        text = ascii_(example(name))
        assert text.isascii(), text


def test_unknown_style_is_rejected():
    with pytest.raises(ValueError):
        format_term(Id(), "latex")


def test_names_with_several_letters():
    assert course("begin total := total + step end") == (
        "AS_total(S²(add, total⇒, step⇒))")

def test_term_to_dict_is_json_serializable():
    data = term_to_dict(term_of(example("power.sipl")))
    json.dumps(data)
    assert data["type"] == "Comp"
    assert data["left"] == {"type": "AS", "name": "R",
                            "func": {"type": "Const", "value": 1}}
    assert data["right"]["type"] == "WH"
    assert data["right"]["cond"]["func"] == {"type": "Basic", "name": "gr"}

def test_explain_power_applies_the_rules_in_practicum_order():
    rules = [step.rule for step in explain(example("power.sipl"))]
    assert rules == [
        "NS_Prog",
        "NS_Stm_Seq",
        "NS_Stm_As", "NS_A_Num",
        "NS_Stm_Wh",
        "NS_B_gr", "NS_A_Var", "NS_A_Num",
        "NS_Stm_Seq",
        "NS_Stm_As", "NS_A_Mult", "NS_A_Var", "NS_A_Var",
        "NS_Stm_As", "NS_A_Sub", "NS_A_Var", "NS_A_Num",
    ]


def test_explain_first_step_is_the_whole_term():
    steps = explain(example("power.sipl"))
    assert steps[0].term == term_of(example("power.sipl"))
    assert steps[0].span.start_line == 1


def test_explain_every_step_has_a_span_and_a_term():
    for step in explain(example("gcd.sipl")):
        assert step.span.start_line >= 1
        assert format_term(step.term)


def test_explain_covers_every_rule_of_the_course():
    src = ("begin A := 1 + 2 - 3 * 4; skip; "
           "if not A = 1 or A > 2 then A := 0 else skip; "
           "while A > 0 do A := A - 1 end")
    rules = {step.rule for step in explain(src)}
    assert rules == {
        "NS_Prog", "NS_Stm_As", "NS_Stm_Seq", "NS_Stm_If", "NS_Stm_Wh", "NS_Stm_skip",
        "NS_A_Num", "NS_A_Var", "NS_A_Add", "NS_A_Sub", "NS_A_Mult",
        "NS_B_eq", "NS_B_gr", "NS_B_or", "NS_B_neg",
    }