"""Tests for the pure state-transition planner.

Loads planner.py (and the const it imports) directly, without triggering the
package __init__, so these run without Home Assistant installed.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import types

BASE = (
    pathlib.Path(__file__).resolve().parent.parent
    / "custom_components"
    / "vornado_transom"
)
_pkg = types.ModuleType("vt")
_pkg.__path__ = [str(BASE)]
sys.modules.setdefault("vt", _pkg)


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"vt.{name}", BASE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"vt.{name}"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


const = _load("const")
planner = _load("planner")

TransomState = planner.TransomState
plan = planner.plan_presses

POW, UP, DN, DIR, AUTO = (
    const.CODE_POWER,
    const.CODE_UP,
    const.CODE_DOWN,
    const.CODE_DIRECTION,
    const.CODE_AUTO,
)


def S(**kw) -> "TransomState":
    return TransomState(**kw)


def test_turn_on():
    assert plan(S(power=False), S(power=True)) == [(POW, 1)]


def test_turn_off_ignores_other_diffs():
    # Off ends the transition; the fan remembers speed/auto for next power-on.
    assert plan(
        S(power=True, speed=1, auto=True), S(power=False, speed=3, auto=False)
    ) == [(POW, 1)]


def test_no_change():
    assert plan(S(power=True, speed=2), S(power=True, speed=2)) == []


def test_speed_up_and_down():
    assert plan(S(power=True, speed=1), S(power=True, speed=3)) == [(UP, 2)]
    assert plan(S(power=True, speed=4), S(power=True, speed=2)) == [(DN, 2)]


def test_direction_toggle():
    assert plan(
        S(power=True, direction="direct"), S(power=True, direction="exhaust")
    ) == [(DIR, 1)]


def test_enable_auto_without_temp_change():
    assert plan(
        S(power=True, auto=False, target_temp=70),
        S(power=True, auto=True, target_temp=70),
    ) == [(AUTO, 1)]


def test_disable_auto_is_single_press():
    assert plan(S(power=True, auto=True), S(power=True, auto=False)) == [(AUTO, 1)]


def test_temp_change_already_in_auto_reopens_window():
    # Already in auto -> leave + re-enter (2 presses) to reopen the temp window.
    assert plan(
        S(power=True, auto=True, target_temp=70),
        S(power=True, auto=True, target_temp=73),
    ) == [(AUTO, 2), (UP, 3)]


def test_temp_change_from_auto_off_just_enters():
    assert plan(
        S(power=True, auto=False, target_temp=70),
        S(power=True, auto=True, target_temp=68),
    ) == [(AUTO, 1), (DN, 2)]


def test_speed_before_temp():
    # The defining ordering rule: speed steps happen while the temp window is
    # still closed (arrows = speed); temp is opened and set last.
    assert plan(
        S(power=True, speed=1, auto=True, target_temp=70),
        S(power=True, speed=3, auto=True, target_temp=72),
    ) == [(UP, 2), (AUTO, 2), (UP, 2)]


def test_everything_at_once_from_off():
    assert plan(
        S(power=False, speed=1, direction="direct", auto=False, target_temp=70),
        S(power=True, speed=2, direction="exhaust", auto=True, target_temp=72),
    ) == [(POW, 1), (DIR, 1), (UP, 1), (AUTO, 1), (UP, 2)]
