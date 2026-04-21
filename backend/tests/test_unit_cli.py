"""Argparse-level smoke tests for backend/cli.py. Does not hit the network."""

from __future__ import annotations

import cli


def test_build_parser_known_subcommands():
    p = cli.build_parser()
    # Parsing --help would exit, but we can inspect subparser choices.
    sub = [a for a in p._subparsers._group_actions if a.choices][0]
    expected = {"ask", "list", "status", "frame", "publish", "report", "trending", "health"}
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
