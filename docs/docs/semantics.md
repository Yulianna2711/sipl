# Semantic terms

`sipl.semantics` builds the semantic term of a SIPL program. A term
is an expression of the program algebra. It denotes the function that
the program computes on states.

```
sipl term examples/power.sipl
AS_R(1) · WH(S²(gr, Y⇒, 0), AS_R(S²(mult, R⇒, X⇒)) · AS_Y(S²(sub, Y⇒, 1)))
```

## Notation

| Term | Text | Meaning (applied to a state `st`) | Formula |
|------|------|-----------------------------------|---------|
| `Const(n)` | `n` | `st -> n` | |
| `Deref(x)` | `x⇒` | `st -> st(x)` | AF_DNM |
| `Super(f, g1..gn)` | `Sⁿ(f, g1, ..., gn)` | `f(g1(st), ..., gn(st))` | AF_S |
| `AS(x, f)` | `AS_x(f)` | `st[x ↦ f(st)]` | AF_AS |
| `Comp(f1, f2)` | `f1 · f2` | `f2(f1(st))` | AF_SEQ |
| `IF(fb, fs1, fs2)` | `IF(fb, fs1, fs2)` | `fs1(st)` if `fb(st)`, else `fs2(st)` | AF_IF |
| `WH(fb, fs)` | `WH(fb, fs)` | iterate `fs` while `fb` holds; undefined if the loop never stops | AF_WH |
| `Id` | `id` | `st` | AF_ID |

Base functions inside a superposition: `add`, `sub`, `mult`, `or`, `neg`, `eq`, `gr`.
The `ascii` style writes `=>` instead of `⇒`, `;` instead of `·` and `S2` instead of `S²`.

## Rules (sem_P, sem_S, sem_A, sem_B)

| Rule | Replacement |
|------|-------------|
| NS_Prog | `sem_P(begin S end) = sem_S(S)` |
| NS_Stm_As | `sem_S(x := a) = AS_x(sem_A(a))` |
| NS_Stm_Seq | `sem_S(S1; S2) = sem_S(S1) · sem_S(S2)` |
| NS_Stm_If | `sem_S(if b then S1 else S2) = IF(sem_B(b), sem_S(S1), sem_S(S2))` |
| NS_Stm_Wh | `sem_S(while b do S) = WH(sem_B(b), sem_S(S))` |
| NS_Stm_skip | `sem_S(skip) = id` |
| NS_A_Num | `sem_A(n) = n` |
| NS_A_Var | `sem_A(x) = x⇒` |
| NS_A_Add / Sub / Mult | `sem_A(a1 ⊕ a2) = S²(add / sub / mult, sem_A(a1), sem_A(a2))` |
| NS_B_eq / gr | `sem_B(a1 = a2) = S²(eq, ...)`, `sem_B(a1 > a2) = S²(gr, ...)` |
| NS_B_or | `sem_B(b1 ∨ b2) = S²(or, sem_B(b1), sem_B(b2))` |
| NS_B_neg | `sem_B(¬b) = S¹(neg, sem_B(b))` |

The term is built by a recursive walk over the AST: `sem_P`, `sem_S`, `sem_A`,
`sem_B` in `sipl/semantics/builder.py` have one case per rule.

## Design decisions and limits

* `begin S end` and parentheses (NS_Stm_BE, NS_A_Par, NS_B_Par) leave no trace:
  the parser removes them, so the AST has no node for them. They do not change
  the term, except that an inner block on the right of `;` is printed in
  parentheses: `AS_X(1) · (AS_Y(2) · AS_Z(3))`.
* A sequence of n statements is read left-associatively, like the grammar:
  `A; B; C` gives `AS_A · AS_B · AS_C` = `(AS_A · AS_B) · AS_C`.
* `sipl term FILE --steps` lists the rules applied while the term was built
  (top-down, with the source position of each application).
* The grammar of this implementation has no negative literals, so a negative number is written
  `0 - n`. Values of variables can be negative, as in the course
  (`Int` includes negative numbers).
* The term is a description of the semantics. It is not executed by the
  library; the tests apply it to states with the formulas AF_* and compare
  the result with the interpreter (`tests/test_semantics_equivalence.py`).