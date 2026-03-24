from __future__ import annotations

from typing import Any, get_args
from unittest.mock import patch

import pytest
from PySide6 import QtCore
from PySide6.QtCore import QObject

from pymodoro.check_in_screen_widgets import (
    ActivityWidget,
    ExerciseWidget,
    FulluseRatingWidget,
    LeverageWidget,
    ProjectWidget,
    PromptCard,
)
from pymodoro.metrics_io import Leverage

# -- Helpers ------------------------------------------------------------------


class _StubOverlay(QObject):
    """Minimal stand-in for _PromptOverlay that exposes the real signal without any GUI."""

    prompt_selected = QtCore.Signal(str)

    def __init__(self, prompts: list[str], current: str, parent: Any) -> None:
        super().__init__(parent)
        self.prompts = prompts
        self.current = current


def _make_card_with_stub(
    prompts: list[str], current: str
) -> tuple[PromptCard, list[_StubOverlay]]:
    card = PromptCard(current, prompts=prompts)
    created: list[_StubOverlay] = []

    class CapturingStub(_StubOverlay):
        def __init__(self, p, c, parent):
            super().__init__(p, c, parent)
            created.append(self)

    with patch("pymodoro.check_in_screen_widgets._PromptOverlay", CapturingStub):
        card._on_prompt_clicked()

    return card, created


# -- PromptCard ---------------------------------------------------------------


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


# -- _ExclusiveToggleRow (via FulluseRatingWidget) ------------------------------


def test_toggle_row_buttons_have_capitalized_labels(qcoreapp: Any) -> None:
    widget = ActivityWidget(["coding", "reading"])
    labels = [btn.text() for btn in widget._buttons]
    assert labels == ["Coding", "Reading"]


def test_toggle_row_click_selects(qcoreapp: Any) -> None:
    widget = ActivityWidget(["coding", "reading"])
    widget._buttons[0].click()
    assert widget.selected == "coding"


def test_toggle_row_click_again_deselects(qcoreapp: Any) -> None:
    widget = ActivityWidget(["coding", "reading"])
    widget._buttons[0].click()
    widget._buttons[0].click()
    assert widget.selected is None


def test_toggle_row_only_one_selected(qcoreapp: Any) -> None:
    widget = ActivityWidget(["a", "b", "c"])
    widget._buttons[0].click()
    widget._buttons[2].click()
    assert widget.selected == "c"
    assert widget._buttons[0].isChecked() is False
    assert widget._buttons[2].isChecked() is True


def test_toggle_row_tooltips_applied(qcoreapp: Any) -> None:
    widget = FulluseRatingWidget()
    assert widget._buttons[0].toolTip() == "Very distracted"
    assert widget._buttons[4].toolTip() == "Deep focus"
    assert widget._buttons[2].toolTip() == ""


def test_toggle_row_no_tooltips_is_fine(qcoreapp: Any) -> None:
    widget = ActivityWidget(["coding", "reading"])
    assert widget._buttons[0].toolTip() == ""


def test_toggle_row_initial_selection_is_none(qcoreapp: Any) -> None:
    widget = ActivityWidget(["a", "b"])
    assert widget.selected is None


def test_toggle_row_tab_focus_on_first_button_by_default(qcoreapp: Any) -> None:
    widget = ActivityWidget(["a", "b", "c"])
    assert widget._buttons[0].focusPolicy() == QtCore.Qt.FocusPolicy.TabFocus
    assert widget._buttons[1].focusPolicy() == QtCore.Qt.FocusPolicy.ClickFocus


def test_toggle_row_tab_focus_moves_to_checked_button(qcoreapp: Any) -> None:
    widget = ActivityWidget(["a", "b", "c"])
    widget._buttons[2].click()
    assert widget._buttons[0].focusPolicy() == QtCore.Qt.FocusPolicy.ClickFocus
    assert widget._buttons[2].focusPolicy() == QtCore.Qt.FocusPolicy.TabFocus


# -- FulluseRatingWidget --------------------------------------------------------


def test_fulluse_rating_has_five_buttons(qcoreapp: Any) -> None:
    widget = FulluseRatingWidget()
    assert len(widget._buttons) == 5
    assert [btn.text() for btn in widget._buttons] == ["1", "2", "3", "4", "5"]


def test_fulluse_rating_returns_int(qcoreapp: Any) -> None:
    widget = FulluseRatingWidget()
    widget._buttons[2].click()
    assert widget.rating == 3


def test_fulluse_rating_returns_none_when_unselected(qcoreapp: Any) -> None:
    widget = FulluseRatingWidget()
    assert widget.rating is None


# -- LeverageWidget -----------------------------------------------------------


def test_leverage_has_correct_options(qcoreapp: Any) -> None:
    widget = LeverageWidget()
    expected = list[str](get_args(Leverage))
    labels = [btn.text() for btn in widget._buttons]
    assert labels == [o.capitalize() for o in expected]


def test_leverage_returns_typed_value(qcoreapp: Any) -> None:
    widget = LeverageWidget()
    widget._buttons[0].click()
    expected_first = list[str](get_args(Leverage))[0]
    assert widget.leverage == expected_first


def test_leverage_returns_none_when_unselected(qcoreapp: Any) -> None:
    widget = LeverageWidget()
    assert widget.leverage is None


# -- ActivityWidget -----------------------------------------------------------


def test_activity_returns_selected(qcoreapp: Any) -> None:
    widget = ActivityWidget(["coding", "meeting"])
    widget._buttons[1].click()
    assert widget.activity == "meeting"


def test_activity_returns_none_when_unselected(qcoreapp: Any) -> None:
    widget = ActivityWidget(["coding"])
    assert widget.activity is None


# -- ProjectWidget ------------------------------------------------------------


def test_project_returns_none_when_empty(qcoreapp: Any) -> None:
    widget = ProjectWidget(["proj-a", "proj-b"])
    assert widget.project is None


def test_project_returns_selected_text(qcoreapp: Any) -> None:
    widget = ProjectWidget(["proj-a", "proj-b"])
    widget._combo.setCurrentIndex(0)
    assert widget.project == "proj-a"


def test_project_with_no_options(qcoreapp: Any) -> None:
    widget = ProjectWidget([])
    assert widget.project is None


# -- ExerciseWidget -----------------------------------------------------------


def test_exercise_result_none_when_incomplete(qcoreapp: Any) -> None:
    widget = ExerciseWidget(["pushups", "squats"])
    assert widget.exercise_result is None


def test_exercise_result_none_when_only_reps(qcoreapp: Any) -> None:
    widget = ExerciseWidget(["pushups"])
    widget._rep_count_input.setValue(10)
    assert widget.exercise_result is None


def test_exercise_result_none_when_only_name(qcoreapp: Any) -> None:
    widget = ExerciseWidget(["pushups"])
    widget._combo.setCurrentIndex(0)
    assert widget.exercise_result is None


def test_exercise_result_returns_tuple(qcoreapp: Any) -> None:
    widget = ExerciseWidget(["pushups", "squats"])
    widget._combo.setCurrentIndex(1)
    widget._rep_count_input.setValue(15)
    assert widget.exercise_result == ("squats", 15)


def test_exercise_name_and_rep_count(qcoreapp: Any) -> None:
    widget = ExerciseWidget(["pushups"])
    widget._combo.setCurrentIndex(0)
    widget._rep_count_input.setValue(20)
    assert widget.exercise_name == "pushups"
    assert widget.rep_count == 20
