"""Shared statistical primitives. All probabilities are fractions in [0, 1].

Every module speaks the same mathematical language: log-odds contributions,
Wilson intervals, empirical-Bayes shrinkage. No arbitrary 0-10 scores here.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

EPS = 1e-6


def clamp01(p: float) -> float:
    return min(1.0 - EPS, max(EPS, p))


def logit(p: float) -> float:
    p = clamp01(p)
    return math.log(p / (1.0 - p))


def sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    ex = math.exp(x)
    return ex / (1.0 + ex)


@dataclass
class Interval:
    lower: float
    upper: float
    standard_error: float

    def to_dict(self) -> dict:
        return {"lower_bound": self.lower, "upper_bound": self.upper,
                "standard_error": self.standard_error}


def wilson_interval(successes: float, n: float, z: float = 1.96) -> Interval | None:
    """Wilson score interval for a binomial proportion. None when n <= 0."""
    if n is None or n <= 0:
        return None
    p = successes / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    se = math.sqrt(max(p * (1 - p), EPS) / n)
    return Interval(max(0.0, center - half), min(1.0, center + half), se)


def shrink_win_rate(observed: float | None, n: float | None, prior: float,
                    strength: float) -> tuple[float, bool]:
    """Empirical-Bayes shrinkage toward `prior` with pseudo-count `strength`.

    Returns (estimate, is_fallback). Without a sample size we cannot shrink;
    the prior is returned and explicitly flagged as fallback.
    """
    if observed is None or n is None or n <= 0:
        return prior, True
    est = (observed * n + prior * strength) / (n + strength)
    return est, False


def expected_matchup_wr(wr_a: float, wr_b: float) -> float:
    """Bradley-Terry style expectation from main effects only.

    logit(P(A beats B)) = logit(wr_A) - logit(wr_B).
    Two 50% champions -> 50%. This is the baseline the observed matchup
    must be compared against (adjusted delta), never the raw WR itself.
    """
    return sigmoid(logit(wr_a) - logit(wr_b))


def matchup_delta_logodds(observed: float | None, wr_a: float, wr_b: float) -> float | None:
    """Observed minus expected, in log-odds. None when no observation."""
    if observed is None:
        return None
    return logit(observed) - logit(expected_matchup_wr(wr_a, wr_b))


def sample_confidence(n: float | None, half_saturation: float = 200.0) -> float:
    """Monotone confidence in [0,1) from sample size; 0 when unknown."""
    if n is None or n <= 0:
        return 0.0
    return n / (n + half_saturation)


def entropy(probs: list[float]) -> float:
    """Shannon entropy in bits, normalized to [0,1] over len(probs)."""
    total = sum(p for p in probs if p > 0)
    if total <= 0 or len(probs) <= 1:
        return 0.0
    h = -sum((p / total) * math.log2(p / total) for p in probs if p > 0)
    return h / math.log2(len(probs))


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def cvar(values: list[float], alpha: float) -> float:
    """Conditional value at risk: mean of the worst `alpha` fraction (lower tail)."""
    if not values:
        return 0.0
    s = sorted(values)
    k = max(1, int(math.ceil(alpha * len(s))))
    return mean(s[:k])


def stderr(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = mean(values)
    var = sum((v - m) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(var / len(values))


def brier_score(probs: list[float], outcomes: list[int]) -> float:
    return mean([(p - o) ** 2 for p, o in zip(probs, outcomes)])


def log_loss(probs: list[float], outcomes: list[int]) -> float:
    return mean([-(o * math.log(clamp01(p)) + (1 - o) * math.log(1 - clamp01(p)))
                 for p, o in zip(probs, outcomes)])


def expected_calibration_error(probs: list[float], outcomes: list[int],
                               bins: int = 10) -> float:
    if not probs:
        return 0.0
    buckets: list[list[tuple[float, int]]] = [[] for _ in range(bins)]
    for p, o in zip(probs, outcomes):
        idx = min(bins - 1, int(p * bins))
        buckets[idx].append((p, o))
    ece = 0.0
    for b in buckets:
        if not b:
            continue
        acc = mean([o for _, o in b])
        conf = mean([p for p, _ in b])
        ece += (len(b) / len(probs)) * abs(acc - conf)
    return ece
