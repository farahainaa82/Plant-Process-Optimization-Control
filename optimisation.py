"""Synthetic telemetry, process response model and constrained decision ranking."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import cos, sin

INTERVAL_MINUTES = 15
FIRST_SCAN = 47
DEMO_START = datetime(2026, 11, 6, 0, 0, tzinfo=timezone(timedelta(hours=8)))


@dataclass(frozen=True)
class Process:
    feed: float         # dry tonnes of ore per hour
    power: float        # kW
    feed_grade: float   # mass fraction
    grade: float        # concentrate mass fraction
    recovery: float     # fraction of feed metal recovered
    stability: float    # simulated index, 0–100

    @property
    def product(self):
        return self.feed * self.feed_grade * self.recovery / self.grade

    @property
    def intensity(self):
        return self.power / self.product


@dataclass(frozen=True)
class Line:
    code: str
    name: str
    profile: str
    nominal: Process
    feed_cap: float
    power_cap: float
    energy_target: float


LINES = (
    Line("N01", "North Plant · Line 01", "Grinding and flotation",
         Process(110, 2180, .30, .622, .877, 82), 118, 2450, 44),
    Line("C02", "Central Plant · Line 02", "Grinding and flotation",
         Process(129, 2470, .31, .627, .899, 89), 140, 2880, 44),
    Line("S03", "South Plant · Line 03", "Grinding and flotation",
         Process(95, 1900, .30, .609, .866, 75), 104, 2130, 43),
)


@dataclass(frozen=True)
class Limits:
    feed_cap: float
    power_cap: float
    min_grade: float = .61
    min_recovery: float = .86
    min_stability: float = 76


@dataclass(frozen=True)
class Economics:
    hours: int = 8
    product_value: float = 160     # MYR/t concentrate, before feed and electricity
    feed_cost: float = 25          # MYR/t ore feed
    tariff: float = .42            # MYR/kWh


@dataclass(frozen=True)
class Action:
    name: str
    instruction: str
    feed_change: float = 0
    power_change: float = 0
    blend: bool = False
    cost: float = 0


ACTIONS = (
    Action("Hold current settings", "Continue monitoring the current settings."),
    Action("Trim mill power", "Trial a 5% lower mill power target at the current feed rate.",
           power_change=-.05, cost=35),
    Action("Stabilise feed blend", "Trial steadier feed blending and a 2% lower mill power target.",
           power_change=-.02, blend=True, cost=120),
    Action("Lift feed with blend", "Trial 5% higher feed and 3% higher mill power with steadier blending.",
           feed_change=.05, power_change=.03, blend=True, cost=180),
    Action("Push maximum throughput", "Model a 12% feed increase and 10% higher mill power.",
           feed_change=.12, power_change=.10, cost=90),
    Action("Blend and ease feed", "Trial steadier blending, 4% lower feed and 3% lower mill power.",
           feed_change=-.04, power_change=-.03, blend=True, cost=120),
)


@dataclass(frozen=True)
class Impact:
    product: float
    feed: float
    power: float
    action_cost: float

    @property
    def net(self):
        return self.product + self.feed + self.power - self.action_cost

    @property
    def sensitivity(self):
        spread = .20 * (abs(self.product) + abs(self.power))
        return self.net - spread, self.net + spread


@dataclass(frozen=True)
class Scenario:
    action: Action
    process: Process
    impact: Impact
    violations: tuple[str, ...]


def scan_time(step):
    return DEMO_START + timedelta(minutes=step * INTERVAL_MINUTES)


def readings(line, step):
    """Deterministic 15-minute synthetic averages, with a recurring ore disturbance."""
    index = LINES.index(line)
    phase = step * .31 + index * 1.3
    disturbance = (1 + cos((step - FIRST_SCAN + index * 4) * .19)) / 2
    nominal = line.nominal
    return Process(
        feed=nominal.feed + 2.1 * sin(phase) - 1.1 * disturbance,
        power=nominal.power + 48 * cos(phase) + 104 * disturbance,
        feed_grade=nominal.feed_grade + .004 * sin(phase * .7) - .005 * disturbance,
        grade=nominal.grade + .004 * cos(phase * 1.2) - .007 * disturbance,
        recovery=nominal.recovery + .006 * sin(phase) - .012 * disturbance,
        stability=nominal.stability + 3.5 * cos(phase) - 5.5 * disturbance,
    )


def baseline_for(line, step):
    """Aggregate four equally long intervals, weighting assays and recovery by mass."""
    samples = [readings(line, period) for period in range(step - 3, step + 1)]
    feed = sum(sample.feed for sample in samples)
    input_metal = sum(sample.feed * sample.feed_grade for sample in samples)
    recovered_metal = sum(sample.feed * sample.feed_grade * sample.recovery for sample in samples)
    concentrate = sum(sample.product for sample in samples)
    return Process(feed / 4, sum(sample.power for sample in samples) / 4,
                   input_metal / feed, recovered_metal / concentrate,
                   recovered_metal / input_metal, sum(sample.stability for sample in samples) / 4)


def simulate(base, action):
    if action == ACTIONS[0]:
        return base
    severity = max(0, (90 - base.stability) / 20)
    blend_gain = min(severity, 1.3) if action.blend else 0
    specific_power_change = (1 + action.power_change) / (1 + action.feed_change) - 1
    return Process(
        feed=base.feed * (1 + action.feed_change),
        power=base.power * (1 + action.power_change),
        feed_grade=base.feed_grade,
        grade=base.grade + .011 * blend_gain + .07 * specific_power_change - .04 * action.feed_change,
        recovery=base.recovery + .022 * blend_gain + .24 * specific_power_change - .07 * action.feed_change,
        stability=min(100, base.stability + 11 * blend_gain - 40 * action.feed_change),
    )


def violations_for(process, limits):
    checks = (
        (process.feed > limits.feed_cap, f"Feed cap {limits.feed_cap:g} t/h"),
        (process.power > limits.power_cap, f"Power cap {limits.power_cap:,.0f} kW"),
        (process.grade < limits.min_grade, f"Grade floor {limits.min_grade:.1%}"),
        (process.recovery < limits.min_recovery, f"Recovery floor {limits.min_recovery:.1%}"),
        (process.stability < limits.min_stability, f"Stability floor {limits.min_stability:g}/100"),
    )
    return tuple(label for failed, label in checks if failed)


def evaluate(base, limits, economics):
    scenarios = []
    for action in ACTIONS:
        process = simulate(base, action)
        impact = Impact(
            (process.product - base.product) * economics.hours * economics.product_value,
            (base.feed - process.feed) * economics.hours * economics.feed_cost,
            (base.power - process.power) * economics.hours * economics.tariff,
            action.cost,
        )
        scenarios.append(Scenario(action, process, impact, violations_for(process, limits)))
    return sorted(scenarios, key=lambda item: (bool(item.violations), -item.impact.net))
