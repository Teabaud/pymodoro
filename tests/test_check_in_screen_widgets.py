from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from PySide6 import QtCore
from PySide6.QtCore import QObject

from pymodoro.check_in_screen_widgets import PromptCard


class _StubOverlay(QObject):
    """Minimal stand-in for _PromptOverlay that exposes the real signal without any GUI."""

    prompt_selected = QtCore.Signal(str)

    def __init__(self, prompts: list[str], current: str, parent: Any) -> None:
        super().__init__(parent)
        self.prompts = prompts
        self.current = current


def _make_card_with_stub(prompts: list[str], current: str) -> tuple[PromptCard, list[_StubOverlay]]:
    card = PromptCard(current, prompts=prompts)
    created: list[_StubOverlay] = []

    class CapturingStub(_StubOverlay):
        def __init__(self, p, c, parent):
            super().__init__(p, c, parent)
            created.append(self)

    with patch("pymodoro.check_in_screen_widgets._PromptOverlay", CapturingStub):
        card._on_prompt_clicked()

    return card, created


def test_prompt_card_placeholder_instructs_click(qcoreapp: Any) -> None:
    card = PromptCard("What did you focus on?", prompts=["Q1", "Q2"])
    assert "Click on the question" in card._input.placeholderText()


def test_prompt_card_label_has_pointer_cursor(qcoreapp: Any) -> None:
    card = PromptCard("Q?", prompts=["Q1"])
    assert (
        card._check_in_prompt.cursor().shape()
        == QtCore.Qt.CursorShape.PointingHandCursor
    )


def test_prompt_card_no_prompts_click_does_nothing(qcoreapp: Any) -> None:
    card = PromptCard("Q?", prompts=[])
    card._on_prompt_clicked()  # should not raise
    assert card.prompt == "Q?"


def test_prompt_card_selecting_from_overlay_updates_label(qcoreapp: Any) -> None:
    card, overlays = _make_card_with_stub(["Q1", "Q2", "Q3"], "Q1")
    assert len(overlays) == 1
    overlays[0].prompt_selected.emit("Q2")
    assert card.prompt == "Q2"


def test_prompt_card_dismissing_overlay_keeps_current_prompt(qcoreapp: Any) -> None:
    card, overlays = _make_card_with_stub(["Q1", "Q2", "Q3"], "Q1")
    # overlay closes without emitting — prompt unchanged
    assert card.prompt == "Q1"


def test_prompt_card_answer_preserved_after_prompt_switch(qcoreapp: Any) -> None:
    card, overlays = _make_card_with_stub(["Q1", "Q2"], "Q1")
    card._input.setPlainText("my answer")
    overlays[0].prompt_selected.emit("Q2")
    assert card.prompt == "Q2"
    assert card.answer == "my answer"


def test_prompt_card_overlay_receives_current_prompt(qcoreapp: Any) -> None:
    card, overlays = _make_card_with_stub(["Q1", "Q2", "Q3"], "Q2")
    assert overlays[0].current == "Q2"
    assert overlays[0].prompts == ["Q1", "Q2", "Q3"]
