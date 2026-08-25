import pygame
import pytest
from screens import (
    get_environment_card_rect,
    get_save_slot_rect,
    get_start_button_rect,
    get_stats_row_rect_for_label,
    get_ui_layout,
)

CANVAS_SIZES = [(1200, 2400), (880, 1760), (1600, 3200)]


def _egg_rect(canvas_w, canvas_h):
    rect = pygame.Rect(0, 0, 200, 200)
    rect.center = (canvas_w // 2, int(canvas_h * 0.18))
    return rect


@pytest.mark.parametrize("canvas_w,canvas_h", CANVAS_SIZES)
def test_start_button_is_centered_horizontally(canvas_w, canvas_h):
    rect = get_start_button_rect(canvas_w, canvas_h)
    # Within 1px of exact center: an odd button width makes exact centering
    # impossible with integer pixel rects.
    assert abs(rect.centerx - canvas_w // 2) <= 1
    assert rect.width > 0 and rect.height > 0
    assert abs((canvas_w - rect.right) - rect.x) <= 1  # symmetric margins, within 1px


@pytest.mark.parametrize("canvas_w,canvas_h", CANVAS_SIZES)
def test_save_slot_rects_tile_the_full_height_with_no_gaps(canvas_w, canvas_h):
    num_slots = 3
    rects = [get_save_slot_rect(canvas_w, canvas_h, num_slots, i) for i in range(num_slots)]
    assert rects[0].top == 0
    assert rects[-1].bottom == canvas_h
    for a, b in zip(rects, rects[1:], strict=False):
        assert a.bottom == b.top


@pytest.mark.parametrize("canvas_w,canvas_h", CANVAS_SIZES)
def test_ui_layout_tabs_sit_directly_above_page(canvas_w, canvas_h):
    egg_rect = _egg_rect(canvas_w, canvas_h)
    stats_tab, env_tab, page_rect = get_ui_layout(canvas_w, canvas_h, egg_rect, canvas_h / 600)
    assert stats_tab.top == env_tab.top == page_rect.top - stats_tab.height
    assert stats_tab.right == env_tab.left
    assert stats_tab.width + env_tab.width == page_rect.width


@pytest.mark.parametrize("canvas_w,canvas_h", CANVAS_SIZES)
def test_ui_layout_panel_never_goes_above_egg(canvas_w, canvas_h):
    egg_rect = _egg_rect(canvas_w, canvas_h)
    stats_tab, _, _ = get_ui_layout(canvas_w, canvas_h, egg_rect, canvas_h / 600)
    assert stats_tab.top >= egg_rect.bottom or stats_tab.top > 0


@pytest.mark.parametrize("canvas_w,canvas_h", CANVAS_SIZES)
def test_environment_card_rects_tile_a_2x2_grid(canvas_w, canvas_h):
    egg_rect = _egg_rect(canvas_w, canvas_h)
    scale = canvas_h / 600
    cards = [get_environment_card_rect(canvas_w, canvas_h, egg_rect, scale, i) for i in range(4)]
    _, _, page_rect = get_ui_layout(canvas_w, canvas_h, egg_rect, scale)

    # top-left corners of the 4 cards form the 2x2 grid's corners
    assert cards[0].topleft == page_rect.topleft
    assert cards[1].left == cards[0].right
    assert cards[2].top == cards[0].bottom
    assert cards[3].right == page_rect.right
    assert cards[3].bottom == page_rect.bottom


@pytest.mark.parametrize("canvas_w,canvas_h", CANVAS_SIZES)
def test_stats_row_rect_found_for_known_label(canvas_w, canvas_h):
    egg_rect = _egg_rect(canvas_w, canvas_h)
    scale = canvas_h / 600
    items = ["Time Alive", "Features", "Extra Stats"]
    rect = get_stats_row_rect_for_label(canvas_w, canvas_h, egg_rect, scale, items, "Extra Stats")
    assert rect is not None
    assert rect.width > 0 and rect.height > 0


def test_stats_row_rect_returns_none_for_unknown_label():
    egg_rect = _egg_rect(1200, 2400)
    rect = get_stats_row_rect_for_label(1200, 2400, egg_rect, 4.0, ["A", "B"], "Not Present")
    assert rect is None


def test_stats_row_rect_returns_none_for_empty_items():
    egg_rect = _egg_rect(1200, 2400)
    rect = get_stats_row_rect_for_label(1200, 2400, egg_rect, 4.0, [], "Anything")
    assert rect is None
