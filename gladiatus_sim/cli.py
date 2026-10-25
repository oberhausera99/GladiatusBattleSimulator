"""Command line interface: arena, turma and compare."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import fields

from .arena import simulate_arena
from .fighter import Fighter
from .turma import TurmaRules, simulate_turma


def _load_team(items):
    return [Fighter.from_dict(d) for d in items]


def _rules(data) -> TurmaRules:
    return TurmaRules(**(data or {}))


def cmd_arena(args) -> int:
    data = json.load(open(args.file))
    a, d = Fighter.from_dict(data["attacker"]), Fighter.from_dict(data["defender"])
    print(simulate_arena(a, d, runs=args.runs, seed=args.seed, life_mode=args.life_mode))
    return 0


def cmd_turma(args) -> int:
    data = json.load(open(args.file))
    res = simulate_turma(_load_team(data["attackers"]), _load_team(data["defenders"]),
                         runs=args.runs, seed=args.seed, rules=_rules(data.get("rules")))
    print(res)
    print(f"deaths per battle: attackers {res.avg_deaths[0]:.2f}, defenders {res.avg_deaths[1]:.2f}")
    return 0


def cmd_compare(args) -> int:
    """Run the simulator on a recorded real report and print sim vs observed."""
    data = json.load(open(args.file))
    obs = data["observed"]
    rules = _rules(data.get("rules"))
    for kv in args.rule or []:
        key, val = kv.split("=")
        cur = getattr(rules, key)
        setattr(rules, key, type(cur)(val) if not isinstance(cur, bool) else val == "true")
    res = simulate_turma(_load_team(data["attackers"]), _load_team(data["defenders"]),
                         runs=args.runs, seed=args.seed, rules=rules)
    print(f"rules: {rules}\n{res.runs} simulated battles vs 1 real report\n")
    print(f"{'':32s}{'simulated':>12s}{'observed':>12s}")
    for s, side in enumerate(("attackers", "defenders")):
        print(f"[{side}]")
        print(f"  {'team points':30s}{res.avg_points[s]:12.0f}{obs['points'][s]:12.0f}")
        print(f"  {'deaths':30s}{res.avg_deaths[s]:12.2f}{obs['deaths'][s]:12.0f}")
        print(f"  {'swings at enemy main char':30s}{res.main_hit_share[s]*100:11.0f}%"
              f"{obs['swings_received_on_main'][1-s]/obs['swings_received_total'][1-s]*100:11.0f}%")
        for i, x in enumerate(res.avg_stats[s]):
            print(f"  {x.name:30s} dmg {x.damage_done:7.0f} / {obs['damage_done'][s][i]:<7d}"
                  f" taken {x.damage_taken:7.0f} / {obs['damage_taken'][s][i]:<7d}")
        print(f"  {'healing done':30s}{sum(x.heal_done for x in res.avg_stats[s]):12.0f}{obs['heal_done'][s]:12d}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="gladiatus-sim")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn, runs in (("arena", cmd_arena, 10000), ("turma", cmd_turma, 1000),
                           ("compare", cmd_compare, 500)):
        sp = sub.add_parser(name)
        sp.add_argument("file")
        sp.add_argument("--runs", type=int, default=runs)
        sp.add_argument("--seed", type=int, default=None)
        sp.set_defaults(fn=fn)
        if name == "arena":
            sp.add_argument("--life-mode", default="current", choices=["current", "full", "unlimited"])
        if name == "compare":
            sp.add_argument("--rule", action="append", metavar="KEY=VALUE",
                            help="override a TurmaRules field, e.g. main_multiplier=10")
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
