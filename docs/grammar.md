# SIPL grammar

Machine-readable grammar: [`grammar/sipl.lark`](../grammar/sipl.lark) (Lark, LALR).
Source: the BNF of SIPL from the course ("Programming Theory", Nikitchenko;
practicum, practical work 1).

## Syntax

```
P ::= begin S end
S ::= x := a | S1 ; S2 | if b then S1 else S2 | while b do S | begin S end | skip
a ::= n | x | a1 + a2 | a1 - a2 | a1 * a2 | (a)
b ::= a1 = a2 | a1 > a2 | b1 or b2 | not b | (b)
```

## How the ambiguity of the original BNF is resolved

The original BNF is ambiguous (for example `X + Y * Z` has two parse trees),
so this version fixes the following rules, as suggested in the textbook.

| Aspect | Decision |
|---|---|
| Associativity | All binary operators are left-associative: `a - b - c` is `(a - b) - c`. |
| Expression precedence (tightest first) | `*`, then `+` `-`, then `=` `>`, then `not`, then `or`. |
| `;` | Binds loosest of all. `if`/`while` take a single statement, so `if b then S1 else S2; S3` is `(if b then S1 else S2); S3` and `while b do S1; S2` is `(while b do S1); S2`. Use `begin ... end` to group. |
| `;` before `end` | Not allowed (`begin X := 1; end` is a syntax error). |
| Numbers | Non-negative integer literals. A negative value is written `0 - n`. |
| Variables | A letter followed by letters, digits or `_`; keywords are excluded. |
| Keywords | Lowercase and case-sensitive: `begin end if then else while do skip not or`. |
| Negation / disjunction | `not` or `¬`; `or` or `∨`. |
| Whitespace | Insignificant. There are no comments. |

## Tests

`tests/test_grammar.py` contains 12 valid and 14 invalid programs plus
structural checks for associativity and precedence.