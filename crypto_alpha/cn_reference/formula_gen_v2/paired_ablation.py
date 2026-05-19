from __future__ import annotations

from collections.abc import Mapping


def paired_ablations(slots: Mapping[str, str]) -> list[tuple[str, str]]:
    b = slots.get("B")
    c = slots.get("C")
    s = slots.get("S")
    out: list[tuple[str, str]] = []
    if b:
        out.append(("B", b))
    if c:
        out.append(("C", c))
    if s:
        out.append(("S", s))
    if b and c:
        out.append(("B*C", f"Mul({b},{c})"))
    if b and s:
        out.append(("B*S", f"Mul({b},{s})"))
    if c and s:
        out.append(("C*S", f"Mul({c},{s})"))
    if b and c and s:
        out.append(("B*C*S", f"Mul({b},Mul({c},{s}))"))
    return out


def low_order_role_count(role_expression: str) -> int:
    if not role_expression:
        return 0
    return len([part for part in role_expression.split("*") if part])

