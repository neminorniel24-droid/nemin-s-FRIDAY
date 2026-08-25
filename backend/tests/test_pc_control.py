"""
Tests for pc_control.py — focused on argument parsing/validation, not the
actual PowerShell execution (which needs a real Windows host and isn't
something CI can exercise).
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pc_control


def test_set_brightness_rejects_invalid_input():
    result = pc_control.set_brightness("garbage")
    assert not result.ok
    assert "brightness must be" in result.message


def test_set_volume_rejects_invalid_direction():
    result = pc_control.set_volume("sideways")
    assert not result.ok
    assert "direction must be" in result.message


def test_media_control_rejects_invalid_action():
    result = pc_control.media_control("rewind")
    assert not result.ok
    assert "action must be" in result.message


def test_open_folder_rejects_unlisted_folder():
    result = pc_control.open_folder("system32")
    assert not result.ok
    assert "isn't in the folder whitelist" in result.message


def test_open_and_type_requires_double_colon_separator():
    result = pc_control.open_and_type("notepad hello world")
    assert not result.ok
    assert "expected format" in result.message


def test_send_whatsapp_news_requires_a_number():
    original = pc_control.WHATSAPP_DEFAULT_NUMBER
    pc_control.WHATSAPP_DEFAULT_NUMBER = ""
    try:
        result = pc_control.send_whatsapp_news("")
        assert not result.ok
        assert "no phone number given" in result.message
    finally:
        pc_control.WHATSAPP_DEFAULT_NUMBER = original


def test_all_actions_are_registered_and_callable():
    assert len(pc_control.ACTIONS) == 20
    for name, fn in pc_control.ACTIONS.items():
        assert callable(fn), f"{name} is not callable"


def test_execute_rejects_unknown_action():
    result = pc_control.execute("delete_everything", "")
    assert not result.ok
    assert "unknown action" in result.message
