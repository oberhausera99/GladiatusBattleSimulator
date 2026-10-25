"""Command line interface: arena, turma and compare."""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import fields

from .arena import simulate_arena
from .fetch import (Client, FetchError, fetch_arena_fighter, fetch_turma_team,
                    fighter_to_dict, parse_player_spec)
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


def _client(args) -> Client:
    from .fetch import DEFAULT_BASE
    return Client(base=os.environ.get("GLADIATUS_BASE", DEFAULT_BASE), debug_dir=args.save_html)


def _apply_rules(args) -> TurmaRules:
    rules = TurmaRules()
    for kv in getattr(args, "rule", None) or []:
        key, val = kv.split("=", 1)
        cur = getattr(rules, key)
        setattr(rules, key, (val == "true") if isinstance(cur, bool) else type(cur)(val))
    return rules


def _describe(f: Fighter) -> str:
    return (f"{f.name:34s} lvl {f.level:<4d} life {f.life:<7.0f} dmg {f.damage[0]:.0f}-{f.damage[1]:.0f}"
            f"  role {f.role:6s} threat {f.threat:.0f}")


def cmd_fight(args) -> int:
    client = _client(args)
    try:
        na, ca, sa = parse_player_spec(args.attacker)
        nd, cd, sd = parse_player_spec(args.defender)
        if args.mode == "arena":
            a = fetch_arena_fighter(client, na, ca, sa)
            d = fetch_arena_fighter(client, nd, cd, sd)
            print(_describe(a)); print(_describe(d))
            print(simulate_arena(a, d, runs=args.runs, seed=args.seed, life_mode=args.life_mode))
        else:
            ta = fetch_turma_team(client, na, ca, sa)
            td = fetch_turma_team(client, nd, cd, sd)
            print("attackers:"); [print("  " + _describe(f)) for f in ta]
            print("defenders:"); [print("  " + _describe(f)) for f in td]
            res = simulate_turma(ta, td, runs=args.runs, seed=args.seed, rules=_apply_rules(args))
            print(res)
            print(f"deaths per battle: attackers {res.avg_deaths[0]:.2f}, defenders {res.avg_deaths[1]:.2f}")
    except FetchError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0


def cmd_show(args) -> int:
    """Download a player and print the stats as JSON (usable as simulator input)."""
    client = _client(args)
    try:
        name, country, server = parse_player_spec(args.player)
        if args.mode == "arena":
            out = fighter_to_dict(fetch_arena_fighter(client, name, country, server))
        else:
            out = [fighter_to_dict(f) for f in fetch_turma_team(client, name, country, server)]
    except FetchError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(json.dumps(out, indent=1, ensure_ascii=False))
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
    fp = sub.add_parser("fight", help="download two players by NAME@SERVER and simulate")
    fp.add_argument("mode", choices=["arena", "turma"])
    fp.add_argument("--attacker", required=True, help='e.g. Aveloca@s59-en (use --attacker="-Name-@s1-en" if it starts with -)')
    fp.add_argument("--defender", required=True)
    fp.add_argument("--runs", type=int, default=2000)
    fp.add_argument("--seed", type=int, default=None)
    fp.add_argument("--life-mode", default="current", choices=["current", "full", "unlimited"])
    fp.add_argument("--rule", action="append", metavar="KEY=VALUE")
    fp.add_argument("--save-html", metavar="DIR", help="save the downloaded raw pages here (debugging)")
    fp.set_defaults(fn=cmd_fight)
    gp = sub.add_parser("gui", help="open the graphical interface")
    gp.set_defaults(fn=lambda args: __import__("gladiatus_sim.gui", fromlist=["main"]).main())
    sp2 = sub.add_parser("show", help="download one player and print JSON")
    sp2.add_argument("mode", choices=["arena", "turma"])
    sp2.add_argument("player", help="NAME@SERVER, e.g. Aveloca@s59-en")
    sp2.add_argument("--save-html", metavar="DIR")
    sp2.set_defaults(fn=cmd_show)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
