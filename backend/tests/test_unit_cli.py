"""Argparse-level smoke tests for backend/cli.py. Does not hit the network."""

from __future__ import annotations

import cli


def test_build_parser_known_subcommands():
    p = cli.build_parser()
    # Parsing --help would exit, but we can inspect subparser choices.
    sub = [a for a in p._subparsers._group_actions if a.choices][0]
    expected = {"ask", "list", "status", "wait", "stop", "frame", "publish", "report", "cost", "trending", "health"}
    assert expected.issubset(set(sub.choices.keys()))


def test_ask_requires_positional():
    p = cli.build_parser()
    args = p.parse_args(["ask", "Will X happen?"])
    assert args.cmd == "ask"
    assert args.question == "Will X happen?"
    assert args.func is cli.cmd_ask


def test_frame_parses_int_round():
    p = cli.build_parser()
    args = p.parse_args(["frame", "sim_abc123", "7"])
    assert args.round == 7
    assert args.simulation_id == "sim_abc123"


def test_publish_unpublish_flag():
    p = cli.build_parser()
    args = p.parse_args(["publish", "sim_abc123", "--unpublish"])
    assert args.unpublish is True


def test_cost_parses_positional():
    p = cli.build_parser()
    args = p.parse_args(["cost", "sim_abc123"])
    assert args.cmd == "cost"
    assert args.simulation_id == "sim_abc123"
    assert args.func is cli.cmd_cost


def test_stop_parses_positional():
    p = cli.build_parser()
    args = p.parse_args(["stop", "sim_abc123"])
    assert args.cmd == "stop"
    assert args.simulation_id == "sim_abc123"
    assert args.func is cli.cmd_stop


def test_wait_defaults_and_overrides():
    p = cli.build_parser()
    args = p.parse_args(["wait", "sim_abc123"])
    assert args.cmd == "wait"
    assert args.simulation_id == "sim_abc123"
    assert args.func is cli.cmd_wait
    # Polling knobs default sensibly and parse as floats.
    assert args.interval == 5.0
    assert args.timeout == 600.0
    overridden = p.parse_args(["wait", "sim_abc123", "--interval", "2", "--timeout", "30"])
    assert overridden.interval == 2.0
    assert overridden.timeout == 30.0
