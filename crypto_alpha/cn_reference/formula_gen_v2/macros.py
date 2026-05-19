from __future__ import annotations


def field_ref(field: str) -> str:
    value = str(field).strip()
    return value if value.startswith("$") else f"${value}"


def csrank(expression: str) -> str:
    return f"CSRank({expression})"


def zscore(expression: str) -> str:
    return f"ZScore({expression})"


def safe_div(left: str, right: str) -> str:
    return f"Div({left},Add(Abs({right}),0.000001))"


def delta_persistence(x: str, n: int) -> str:
    x = field_ref(x) if not str(x).strip().startswith(("Delta(", "Mean(", "Mom(", "ZScore(", "CSRank(")) else str(x).strip()
    return f"Mean(Mul(Sign(Delta({x},1)),Sign(Delay(Delta({x},1),1))),{int(n)})"


def delta_autocorr(x: str, n: int) -> str:
    x = field_ref(x) if not str(x).strip().startswith(("Delta(", "Mean(", "Mom(", "ZScore(", "CSRank(")) else str(x).strip()
    return f"Corr(Delta({x},1),Delay(Delta({x},1),1),{int(n)})"


def second_diff(x: str) -> str:
    x = field_ref(x) if not str(x).strip().startswith(("Delta(", "Mean(", "Mom(", "ZScore(", "CSRank(")) else str(x).strip()
    return f"Sub(Delta({x},1),Delay(Delta({x},1),1))"


def signed_square(x: str) -> str:
    return f"Mul(Sign(ZScore({x})),Mul(ZScore({x}),ZScore({x})))"


def price_volume_confirm(price: str, flow: str, n: int) -> str:
    price = field_ref(price)
    flow = field_ref(flow)
    return f"Mean(Mul(Sign(Delta({price},1)),Sign(Delta({flow},1))),{int(n)})"


def price_volume_diverge(price: str, flow: str, n: int) -> str:
    # Direction is deliberately left to wrapper/replay selection in v1.
    return price_volume_confirm(price, flow, n)


def signal_confirm(base: str, confirmation: str) -> str:
    return f"Mul({zscore(base)},{confirmation})"


def signal_state(base: str, state: str) -> str:
    return f"Mul({zscore(base)},{zscore(state)})"


def signal_confirm_state(base: str, confirmation: str, state: str) -> str:
    return f"Mul({zscore(base)},Mul({confirmation},{zscore(state)}))"

