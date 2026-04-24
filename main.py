import sys
import os
import time
import ctypes
import math
from ctypes import wintypes
from typing import Optional
import pygame
from save_system import load_save_slots, write_save_slots, new_slot_state
from ui_helpers import ShakeAnimation, format_time
from win32_types import RECT, POINT, MINMAXINFO, MONITORINFO
from tray_support import start_tray_icon
from screens import (
    draw_extra_stats_page,
    draw_game_screen,
    draw_save_select,
    draw_start_menu,
    get_environment_card_rect,
    get_stats_row_rect_for_label,
    get_start_button_rect,
    get_ui_layout,
)

WINDOW_W, WINDOW_H = 300, 600
RESOLUTION_SCALE = 4
ASPECT_RATIO = WINDOW_W / WINDOW_H
FPS = 240
NUM_SAVE_SLOTS = 3
AUTOSAVE_INTERVAL_SECONDS = 1.0
START_MENU_BACKGROUND_PATH = os.path.join("assets", "icons", "background", "start_menu.png")
PETAWARU_IMAGE_PATH = os.path.join("assets", "icons", "monster", "petawaru.png")
HIDDEN_UNLOCK_THRESHOLD_SECONDS = 60.0


# tray support is imported at runtime inside start_tray() to satisfy static analysis
HAS_PYSTRAY = False


def main():
    pygame.init()
    win_hook_refs = {}
    is_interactive_resizing = False
    live_redraw = None
    image_not_found_path = os.path.join("assets", "icons", "misc", "image_not_found.webp")

    def load_image_with_fallback(primary_path):
        for path in (primary_path, image_not_found_path):
            try:
                if os.path.exists(path):
                    surf = pygame.image.load(path)
                    if pygame.display.get_surface() is not None:
                        try:
                            surf = surf.convert_alpha()
                        except Exception:
                            surf = surf.convert()
                        # For assets that use color-key transparency instead of alpha,
                        # treat the top-left pixel as transparent.
                        if not (surf.get_flags() & pygame.SRCALPHA):
                            surf.set_colorkey(surf.get_at((0, 0)))
                        return surf
                    return surf
            except Exception:
                pass
        return None

    # Windows helper functions to hide/show the native window (remove from taskbar)
    def _get_hwnd():
        try:
            info = pygame.display.get_wm_info()
            # common key on Windows is 'window'
            return info.get('window') or info.get('hwnd')
        except Exception:
            return None

    def hide_window():
        if sys.platform != 'win32':
            return
        hwnd = _get_hwnd()
        if not hwnd:
            return
        try:
            SW_HIDE = 0
            ctypes.windll.user32.ShowWindow(int(hwnd), SW_HIDE)
        except Exception:
            pass

    def show_window():
        if sys.platform != 'win32':
            return
        hwnd = _get_hwnd()
        if not hwnd:
            return
        try:
            SW_SHOW = 5
            SW_RESTORE = 9
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            # Try a straightforward restore + foreground first
            user32.ShowWindow(int(hwnd), SW_RESTORE)
            user32.SetForegroundWindow(int(hwnd))

            # If SetForegroundWindow fails due to focus restrictions, try AttachThreadInput trick
            fg = user32.GetForegroundWindow()
            if fg and fg != int(hwnd):
                cur_thread = kernel32.GetCurrentThreadId()
                foreground_thread = user32.GetWindowThreadProcessId(fg, 0)
                try:
                    user32.AttachThreadInput(cur_thread, foreground_thread, True)
                    user32.SetForegroundWindow(int(hwnd))
                    user32.SetActiveWindow(int(hwnd))
                    user32.BringWindowToTop(int(hwnd))
                finally:
                    user32.AttachThreadInput(cur_thread, foreground_thread, False)
        except Exception:
            pass

    # Use egg sprite as the app icon for both title bar and tray.
    egg_path = os.path.join("assets", "icons", "egg", "egg1.png")
    icon_path = egg_path
    lock_path = os.path.join("assets", "icons", "misc", "lock.webp")
    lock_image: Optional[pygame.Surface] = None
    try:
        icon_surf = load_image_with_fallback(icon_path)
        if icon_surf is not None:
            pygame.display.set_icon(icon_surf)
    except Exception:
        pass

    pygame.display.set_caption("Egg UI Demo")
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H), pygame.RESIZABLE)
    lock_image = load_image_with_fallback(lock_path)
    canvas_w = WINDOW_W * RESOLUTION_SCALE
    canvas_h = WINDOW_H * RESOLUTION_SCALE
    canvas = pygame.Surface((canvas_w, canvas_h))
    window_size = [WINDOW_W, WINDOW_H]
    viewport = pygame.Rect(0, 0, WINDOW_W, WINDOW_H)
    clock = pygame.time.Clock()

    def update_viewport(size=None):
        nonlocal viewport
        if size is None:
            sw, sh = screen.get_size()
        else:
            sw, sh = size
        if sw == window_size[0] and sh == window_size[1]:
            return
        window_size[0], window_size[1] = sw, sh
        scale = min(sw / WINDOW_W, sh / WINDOW_H)
        draw_w = max(1, int(WINDOW_W * scale))
        draw_h = max(1, int(WINDOW_H * scale))
        viewport = pygame.Rect((sw - draw_w) // 2, (sh - draw_h) // 2, draw_w, draw_h)

    def window_to_canvas(pos):
        if not viewport.collidepoint(pos):
            return None
        rel_x = (pos[0] - viewport.x) * canvas_w / viewport.width
        rel_y = (pos[1] - viewport.y) * canvas_h / viewport.height
        return int(rel_x), int(rel_y)

    update_viewport()

    # Keep native window controls functional, but suppress the icon/system-menu popup.
    def suppress_system_menu_popup():
        if sys.platform != 'win32':
            return
        try:
            hwnd = _get_hwnd()
            if not hwnd:
                return
            user32 = ctypes.WinDLL("user32", use_last_error=True)

            GetSystemMenu = user32.GetSystemMenu
            GetSystemMenu.argtypes = [wintypes.HWND, wintypes.BOOL]
            GetSystemMenu.restype = wintypes.HMENU

            # Reset system menu first so Close/Minimize/Maximize remain intact.
            GetSystemMenu(int(hwnd), True)

            if ctypes.sizeof(ctypes.c_void_p) == 8:
                get_long_ptr = user32.GetWindowLongPtrW
                set_long_ptr = user32.SetWindowLongPtrW
            else:
                get_long_ptr = user32.GetWindowLongW
                set_long_ptr = user32.SetWindowLongW

            get_long_ptr.argtypes = [wintypes.HWND, ctypes.c_int]
            get_long_ptr.restype = ctypes.c_void_p
            set_long_ptr.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
            set_long_ptr.restype = ctypes.c_void_p

            CallWindowProc = user32.CallWindowProcW
            CallWindowProc.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
            CallWindowProc.restype = ctypes.c_ssize_t
            MonitorFromWindow = user32.MonitorFromWindow
            MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
            MonitorFromWindow.restype = wintypes.HANDLE
            GetMonitorInfoW = user32.GetMonitorInfoW
            GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MONITORINFO)]
            GetMonitorInfoW.restype = wintypes.BOOL

            GWL_WNDPROC = -4
            WM_GETMINMAXINFO = 0x0024
            WM_SIZE = 0x0005
            WM_SYSCOMMAND = 0x0112
            WM_SIZING = 0x0214
            WM_ENTERSIZEMOVE = 0x0231
            WM_EXITSIZEMOVE = 0x0232
            WM_NCLBUTTONDOWN = 0x00A1
            WM_NCLBUTTONUP = 0x00A2
            WM_NCLBUTTONDBLCLK = 0x00A3
            WM_NCRBUTTONUP = 0x00A5
            SC_MOUSEMENU = 0xF090
            SC_KEYMENU = 0xF100
            HTSYSMENU = 3
            WMSZ_LEFT = 1
            WMSZ_RIGHT = 2
            WMSZ_TOP = 3
            WMSZ_TOPLEFT = 4
            WMSZ_TOPRIGHT = 5
            WMSZ_BOTTOM = 6
            WMSZ_BOTTOMLEFT = 7
            WMSZ_BOTTOMRIGHT = 8
            MONITOR_DEFAULTTONEAREST = 2
            MIN_W = 220
            MIN_H = int(MIN_W / ASPECT_RATIO)

            old_proc = get_long_ptr(int(hwnd), GWL_WNDPROC)
            if not old_proc:
                return

            WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

            def get_max_window_bounds(target_hwnd):
                max_w = window_size[0]
                max_h = window_size[1]
                max_x = 0
                max_y = 0
                monitor = MonitorFromWindow(target_hwnd, MONITOR_DEFAULTTONEAREST)
                if monitor:
                    monitor_info = MONITORINFO()
                    monitor_info.cbSize = ctypes.sizeof(MONITORINFO)
                    if GetMonitorInfoW(monitor, ctypes.byref(monitor_info)):
                        work_w = monitor_info.rcWork.right 
                        work_h = monitor_info.rcWork.bottom
                        max_w = int((work_h) * ASPECT_RATIO)
                        max_h = work_h + 10
                        RIGHT_EDGE_NUDGE = 10
                        # Clamp to monitor bounds for safety.
                        max_x = (work_w - max_w)+ RIGHT_EDGE_NUDGE
                max_w = max(MIN_W, max_w)
                max_h = max(MIN_H, max_h)
                return max_w, max_h, max_x, max_y

            def fit_by_width(target_w, max_w, max_h):
                new_w = max(MIN_W, min(target_w, max_w))
                new_h = int(round(new_w / ASPECT_RATIO))
                if new_h > max_h:
                    new_h = max_h
                    new_w = int(round(new_h * ASPECT_RATIO))
                return max(MIN_W, new_w), max(MIN_H, new_h)

            def fit_by_height(target_h, max_w, max_h):
                new_h = max(MIN_H, min(target_h, max_h))
                new_w = int(round(new_h * ASPECT_RATIO))
                if new_w > max_w:
                    new_w = max_w
                    new_h = int(round(new_w / ASPECT_RATIO))
                return max(MIN_W, new_w), max(MIN_H, new_h)

            def _wndproc(h, msg, wparam, lparam):
                nonlocal is_interactive_resizing
                # Prevent title-bar icon clicks/double-clicks from opening system menu
                # or triggering the default "close on icon double-click" behavior.
                if msg in (WM_NCLBUTTONDOWN, WM_NCLBUTTONUP, WM_NCLBUTTONDBLCLK, WM_NCRBUTTONUP):
                    if int(wparam) == HTSYSMENU:
                        return 0

                if msg == WM_ENTERSIZEMOVE:
                    is_interactive_resizing = True
                elif msg == WM_EXITSIZEMOVE:
                    is_interactive_resizing = False

                if msg == WM_GETMINMAXINFO:
                    mmi = ctypes.cast(lparam, ctypes.POINTER(MINMAXINFO)).contents
                    max_w, max_h, max_x, max_y = get_max_window_bounds(h)
                    mmi.ptMinTrackSize.x = MIN_W
                    mmi.ptMinTrackSize.y = MIN_H
                    mmi.ptMaxTrackSize.x = max_w
                    mmi.ptMaxTrackSize.y = max_h
                    mmi.ptMaxSize.x = max_w
                    mmi.ptMaxSize.y = max_h
                    mmi.ptMaxPosition.x = max_x
                    mmi.ptMaxPosition.y = max_y
                    return 0

                if msg == WM_SIZE:
                    width = int(lparam) & 0xFFFF
                    height = (int(lparam) >> 16) & 0xFFFF
                    if width > 0 and height > 0:
                        update_viewport((width, height))
                    result = CallWindowProc(old_proc, h, msg, wparam, lparam)
                    if live_redraw is not None and width > 0 and height > 0:
                        try:
                            live_redraw(True)
                        except Exception:
                            pass
                    return result

                if msg == WM_SIZING:
                    rect = ctypes.cast(lparam, ctypes.POINTER(RECT)).contents
                    max_w, max_h, _, _ = get_max_window_bounds(h)
                    width = rect.right - rect.left
                    height = rect.bottom - rect.top

                    if int(wparam) in (WMSZ_LEFT, WMSZ_RIGHT):
                        new_w, new_h = fit_by_width(width, max_w, max_h)
                        if int(wparam) == WMSZ_LEFT:
                            rect.left = rect.right - new_w
                        else:
                            rect.right = rect.left + new_w
                        rect.bottom = rect.top + new_h
                    elif int(wparam) in (WMSZ_TOP, WMSZ_BOTTOM):
                        new_w, new_h = fit_by_height(height, max_w, max_h)
                        rect.right = rect.left + new_w
                        if int(wparam) == WMSZ_TOP:
                            rect.top = rect.bottom - new_h
                        else:
                            rect.bottom = rect.top + new_h
                    elif int(wparam) == WMSZ_TOPLEFT:
                        new_w, new_h = fit_by_width(width, max_w, max_h)
                        rect.left = rect.right - new_w
                        rect.top = rect.bottom - new_h
                    elif int(wparam) == WMSZ_TOPRIGHT:
                        new_w, new_h = fit_by_width(width, max_w, max_h)
                        rect.right = rect.left + new_w
                        rect.top = rect.bottom - new_h
                    elif int(wparam) == WMSZ_BOTTOMLEFT:
                        new_w, new_h = fit_by_width(width, max_w, max_h)
                        rect.left = rect.right - new_w
                        rect.bottom = rect.top + new_h
                    elif int(wparam) == WMSZ_BOTTOMRIGHT:
                        new_w, new_h = fit_by_width(width, max_w, max_h)
                        rect.right = rect.left + new_w
                        rect.bottom = rect.top + new_h
                    # Forward WM_SIZING so SDL/Pygame still receives live size updates
                    # during the drag operation.
                    return CallWindowProc(old_proc, h, msg, wparam, lparam)

                if msg == WM_SYSCOMMAND:
                    cmd = int(wparam) & 0xFFF0
                    if cmd in (SC_MOUSEMENU, SC_KEYMENU):
                        return 0
                return CallWindowProc(old_proc, h, msg, wparam, lparam)

            # Keep references alive for the lifetime of the app.
            win_hook_refs["old_proc"] = old_proc
            win_hook_refs["proc_ref"] = WNDPROC(_wndproc)

            set_long_ptr(int(hwnd), GWL_WNDPROC, ctypes.cast(win_hook_refs["proc_ref"], ctypes.c_void_p))
        except Exception:
            pass

    suppress_system_menu_popup()

    font = pygame.font.SysFont(None, 22 * RESOLUTION_SCALE)
    status_font = pygame.font.SysFont(None, int(34 * RESOLUTION_SCALE))
    evolution_stage = "dormant"
    evolution_click_progress = 0
    status_flash_text = ""
    status_flash_timer = 0.0
    hatching_animation_active = False
    hatching_animation_timer = 0.0
    hatching_animation_duration = 5.0
    current_tab = "stats"
    stat_items = ["Time Alive", "Features", "Power", "Survivability", "Adaptivness", "Extra Stats"]
    extra_stats_items = [
        "Charisma",
        "Happiness",
        "Violence",
        "Curiosity",
        "Laziness",
        "Purpose",
        "Sex Drive",
        "Likeliness of being a pikachu",
        "Stability",
        "Wisdom",
        "Intelligence",
        "More to come soon....",
    ]
    environment_items = ["Water", "Earth", "Air", "Hidden"]
    selected_environment = None
    environment_time_seconds = {"water": 0.0, "earth": 0.0, "air": 0.0}
    hidden_revealed = False
    app_screen = "start_menu"
    save_slots = load_save_slots(NUM_SAVE_SLOTS)
    active_slot_index: Optional[int] = None
    time_alive_seconds = 0.0
    save_dirty = False
    autosave_timer = 0.0
    start_bg_image: Optional[pygame.Surface] = load_image_with_fallback(START_MENU_BACKGROUND_PATH)
    environment_backgrounds = {
        "water": load_image_with_fallback(os.path.join("assets", "icons", "background", "water.png")),
        "earth": load_image_with_fallback(os.path.join("assets", "icons", "background", "earth.png")),
        "air": load_image_with_fallback(os.path.join("assets", "icons", "background", "air.png")),
        "hidden": load_image_with_fallback(os.path.join("assets", "icons", "background", "hidden.png")),
    }

    def mark_save_dirty():
        nonlocal save_dirty
        if active_slot_index is None:
            return
        save_dirty = True

    def get_stage_label():
        if evolution_stage == "cracked":
            return "Cracked"
        if evolution_stage == "hatching":
            return "Hatching"
        if evolution_stage == "petawaru":
            return "Petawaru"
        return "Dormant"

    def get_status_text():
        if status_flash_timer > 0.0 and status_flash_text:
            return status_flash_text
        return get_stage_label()

    def save_active_slot(force=False):
        nonlocal save_dirty
        if active_slot_index is None:
            return
        if (not force) and (not save_dirty):
            return
        slot = save_slots[active_slot_index]
        slot["used"] = True
        slot["current_tab"] = current_tab
        slot["time_alive_seconds"] = max(0.0, float(time_alive_seconds))
        slot["evolution_stage"] = evolution_stage
        slot["evolution_click_progress"] = max(0, min(2, int(evolution_click_progress)))
        slot["selected_environment"] = selected_environment
        slot["environment_time_seconds"] = {
            "water": max(0.0, float(environment_time_seconds["water"])),
            "earth": max(0.0, float(environment_time_seconds["earth"])),
            "air": max(0.0, float(environment_time_seconds["air"])),
        }
        slot["hidden_revealed"] = bool(hidden_revealed)
        try:
            write_save_slots(save_slots)
            save_dirty = False
        except Exception:
            pass

    def enter_slot(slot_index, force_new=False):
        nonlocal active_slot_index, app_screen, current_tab, time_alive_seconds, save_dirty, autosave_timer
        nonlocal evolution_stage, evolution_click_progress, status_flash_text, status_flash_timer
        nonlocal hatching_animation_active, hatching_animation_timer, egg_image
        nonlocal selected_environment, environment_time_seconds, hidden_revealed
        active_slot_index = slot_index
        slot = save_slots[slot_index]

        if force_new or (not slot.get("used", False)):
            current_tab = "stats"
            time_alive_seconds = 0.0
            save_slots[slot_index] = new_slot_state()
            save_slots[slot_index]["used"] = True
            evolution_stage = "dormant"
            evolution_click_progress = 0
            selected_environment = None
            environment_time_seconds = {"water": 0.0, "earth": 0.0, "air": 0.0}
            hidden_revealed = False
        else:
            current_tab = "environment" if slot.get("current_tab") == "environment" else "stats"
            time_alive_seconds = max(0.0, float(slot.get("time_alive_seconds", 0.0)))
            evolution_stage = slot.get("evolution_stage", "dormant")
            if evolution_stage not in {"dormant", "cracked", "hatching", "petawaru"}:
                evolution_stage = "dormant"
            evolution_click_progress = max(0, min(2, int(slot.get("evolution_click_progress", 0))))
            selected_raw = slot.get("selected_environment", None)
            if selected_raw is None:
                selected_environment = None
            else:
                selected_environment = str(selected_raw).lower()
                if selected_environment not in {"water", "earth", "air", "hidden"}:
                    selected_environment = None
            loaded_times = slot.get("environment_time_seconds", {})
            environment_time_seconds = {
                "water": max(0.0, float(loaded_times.get("water", 0.0))),
                "earth": max(0.0, float(loaded_times.get("earth", 0.0))),
                "air": max(0.0, float(loaded_times.get("air", 0.0))),
            }
            hidden_revealed = bool(slot.get("hidden_revealed", False))
            if (environment_time_seconds["water"] + environment_time_seconds["earth"] + environment_time_seconds["air"]) >= HIDDEN_UNLOCK_THRESHOLD_SECONDS:
                hidden_revealed = True
            if selected_environment == "hidden" and not hidden_revealed:
                selected_environment = None
            if evolution_stage == "hatching":
                # Resume from the pre-hatch state and require the final trigger again.
                evolution_stage = "cracked"
                evolution_click_progress = 1

        status_flash_text = ""
        status_flash_timer = 0.0
        hatching_animation_active = False
        hatching_animation_timer = 0.0
        egg_image = petawaru_image if evolution_stage == "petawaru" else base_egg_image
        rebuild_egg_sprite()
        app_screen = "game"
        save_dirty = True
        autosave_timer = 0.0
        save_active_slot(force=True)

    # tray / visibility state
    window_visible = True
    tray_icon = None

    # start tray icon unless running headless (SDL dummy driver)
    if os.environ.get("SDL_VIDEODRIVER", "") != "dummy":
        def on_restore(icon, item):
            try:
                pygame.event.post(pygame.event.Event(pygame.USEREVENT, {"action": "restore"}))
            except Exception:
                pass

        def on_exit(icon, item):
            try:
                pygame.event.post(pygame.event.Event(pygame.USEREVENT, {"action": "exit"}))
            except Exception:
                pass

        tray_icon = start_tray_icon(
            icon_path=icon_path,
            fallback_path=image_not_found_path,
            title="Background Evolution",
            on_restore=on_restore,
            on_exit=on_exit,
        )

    # egg sprite setup
    egg_radius_base = 90
    egg_y_base = 220
    shake_magnitude_base = 5
    base_egg_image: Optional[pygame.Surface] = load_image_with_fallback(egg_path)
    petawaru_image: Optional[pygame.Surface] = load_image_with_fallback(PETAWARU_IMAGE_PATH)
    egg_image: Optional[pygame.Surface] = petawaru_image if evolution_stage == "petawaru" else base_egg_image
    egg_box_width = int(egg_radius_base * RESOLUTION_SCALE * 3)
    egg_box_height = int(egg_radius_base * RESOLUTION_SCALE * 3)
    egg_sprite: pygame.Surface = pygame.Surface((egg_box_width, egg_box_height), pygame.SRCALPHA)
    pygame.draw.ellipse(egg_sprite, (245, 240, 220), egg_sprite.get_rect())
    egg_mask: pygame.mask.Mask = pygame.mask.from_surface(egg_sprite)

    def get_canvas_scale():
        return canvas_h / WINDOW_H

    def rebuild_egg_sprite():
        nonlocal egg_sprite, egg_mask
        egg_radius = max(1, int(egg_radius_base * get_canvas_scale()))
        egg_box_w = max(1, int(egg_radius * 3))
        egg_box_h = max(1, int(egg_radius * 3))

        if egg_image is None:
            egg_sprite = pygame.Surface((1, 1), pygame.SRCALPHA)
            egg_mask = pygame.mask.from_surface(egg_sprite)
            return

        img_w, img_h = egg_image.get_size()
        fit_scale = min(egg_box_w / img_w, egg_box_h / img_h)
        draw_w = max(1, int(img_w * fit_scale))
        draw_h = max(1, int(img_h * fit_scale))
        egg_sprite = pygame.transform.smoothscale(egg_image, (draw_w, draw_h))
        egg_mask = pygame.mask.from_surface(egg_sprite)

    def get_egg_rect(offset_x=0):
        rect = egg_sprite.get_rect()
        egg_x = canvas_w // 2
        egg_y = int(egg_y_base * get_canvas_scale())
        rect.center = (egg_x + offset_x, egg_y)
        return rect

    def get_draw_egg_for_frame(offset_x):
        if not hatching_animation_active:
            rect = get_egg_rect(offset_x)
            return egg_sprite, rect, 0.0

        progress = min(1.0, max(0.0, hatching_animation_timer / hatching_animation_duration))
        pulse = math.sin(progress * math.pi * 10.0)
        size_scale = 1.0 + 0.12 * pulse
        anim_w = max(1, int(egg_sprite.get_width() * size_scale))
        anim_h = max(1, int(egg_sprite.get_height() * size_scale))
        anim_sprite = pygame.transform.smoothscale(egg_sprite, (anim_w, anim_h))

        shake = int((1.0 - progress * 0.4) * 18 * math.sin(progress * math.pi * 34.0))
        rect = anim_sprite.get_rect(center=(canvas_w // 2 + offset_x + shake, int(egg_y_base * get_canvas_scale())))
        return anim_sprite, rect, progress

    def draw_hatching_cracks(rect, progress):
        if progress <= 0.0:
            return
        crack_color = (40, 24, 18)
        branches = [
            ((0.00, -0.32), (0.02, 0.12)),
            ((0.02, 0.12), (-0.15, 0.32)),
            ((0.02, 0.12), (0.18, 0.36)),
            ((-0.10, -0.12), (-0.22, 0.06)),
            ((0.08, -0.20), (0.25, -0.02)),
        ]
        visible = max(1, int(len(branches) * progress + 0.99))
        thickness = max(1, int(2 * get_canvas_scale() * (0.35 + progress)))
        for idx in range(min(visible, len(branches))):
            (sx, sy), (ex, ey) = branches[idx]
            start = (int(rect.centerx + sx * rect.width), int(rect.centery + sy * rect.height))
            end = (int(rect.centerx + ex * rect.width), int(rect.centery + ey * rect.height))
            pygame.draw.line(canvas, crack_color, start, end, thickness)

    rebuild_egg_sprite()

    def sync_canvas_resolution():
        nonlocal canvas, canvas_w, canvas_h, font, status_font
        target_w = max(1, viewport.width * RESOLUTION_SCALE)
        target_h = max(1, viewport.height * RESOLUTION_SCALE)
        if target_w == canvas_w and target_h == canvas_h:
            return
        canvas_w, canvas_h = target_w, target_h
        canvas = pygame.Surface((canvas_w, canvas_h))
        font_size = max(12, int(22 * get_canvas_scale()))
        status_font_size = max(18, int(34 * get_canvas_scale()))
        font = pygame.font.SysFont(None, font_size)
        status_font = pygame.font.SysFont(None, status_font_size)
        rebuild_egg_sprite()

    shake = ShakeAnimation(magnitude=shake_magnitude_base * RESOLUTION_SCALE)

    def draw_frame(force_fast_scale=False):
        if not window_visible:
            return

        # Keep viewport synced even when platform-specific resize events are delayed.
        current_size = screen.get_size()
        if current_size[0] != window_size[0] or current_size[1] != window_size[1]:
            update_viewport(current_size)
        sync_canvas_resolution()

        canvas.fill((30, 30, 30))
        shake.magnitude = max(1, int(shake_magnitude_base * get_canvas_scale()))
        scale = get_canvas_scale()

        if app_screen == "start_menu":
            draw_start_menu(canvas, canvas_w, canvas_h, font, start_bg_image)

        elif app_screen == "save_select":
            draw_save_select(canvas, canvas_w, canvas_h, font, save_slots, NUM_SAVE_SLOTS, scale, format_time)

        elif app_screen == "game":
            offset_x = shake.get_offset()
            egg_draw_sprite, egg_rect_draw, hatch_progress = get_draw_egg_for_frame(offset_x)
            layout_anchor_rect = get_egg_rect(offset_x)
            active_environment_bg = environment_backgrounds.get(selected_environment) if selected_environment else None
            environments_unlocked = evolution_stage == "petawaru"
            draw_game_screen(
                canvas,
                canvas_w,
                canvas_h,
                font,
                status_font,
                scale,
                get_status_text(),
                egg_draw_sprite,
                egg_rect_draw,
                layout_anchor_rect,
                current_tab,
                stat_items,
                environment_items,
                time_alive_seconds,
                format_time,
                lock_image,
                selected_environment,
                hidden_revealed,
                active_environment_bg,
                environment_backgrounds,
                environments_unlocked,
            )
            if hatching_animation_active:
                draw_hatching_cracks(egg_rect_draw, hatch_progress)
        else:
            draw_extra_stats_page(
                canvas,
                canvas_w,
                canvas_h,
                font,
                scale,
                extra_stats_items,
            )

        screen.fill((18, 18, 18))
        scaled = pygame.transform.smoothscale(canvas, (viewport.width, viewport.height))
        screen.blit(scaled, viewport.topleft)

        pygame.display.flip()

    live_redraw = draw_frame

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        if app_screen in ("game", "extra_stats"):
            time_alive_seconds += dt
            mark_save_dirty()
            autosave_timer += dt
            if autosave_timer >= AUTOSAVE_INTERVAL_SECONDS:
                autosave_timer = 0.0
                save_active_slot(force=False)

        if app_screen == "game":
            if selected_environment in {"water", "earth", "air"}:
                environment_time_seconds[selected_environment] += dt
            total_visible_env_time = (
                environment_time_seconds["water"]
                + environment_time_seconds["earth"]
                + environment_time_seconds["air"]
            )
            if (not hidden_revealed) and total_visible_env_time >= HIDDEN_UNLOCK_THRESHOLD_SECONDS:
                hidden_revealed = True
            mark_save_dirty()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                # explicit close should terminate app (and tray)
                save_active_slot(force=True)
                if tray_icon is not None:
                    try:
                        tray_icon.stop()
                    except Exception:
                        pass
                running = False
            elif event.type == pygame.WINDOWMINIMIZED:
                # handle minimize event -> send to tray
                window_visible = False
                # hide the native window so it is removed from the taskbar
                hide_window()
                # also iconify as a fallback
                try:
                    pygame.display.iconify()
                except Exception:
                    pass
            elif event.type in (pygame.WINDOWRESIZED, getattr(pygame, "WINDOWSIZECHANGED", -1)):
                new_w = getattr(event, "x", None)
                new_h = getattr(event, "y", None)
                if new_w is not None and new_h is not None:
                    update_viewport((new_w, new_h))
                else:
                    update_viewport()
            elif event.type == getattr(pygame, "VIDEORESIZE", -1):
                update_viewport((event.w, event.h))
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_pos = window_to_canvas(event.pos)
                if mouse_pos is None:
                    continue

                if app_screen == "start_menu":
                    if get_start_button_rect(canvas_w, canvas_h).collidepoint(mouse_pos):
                        app_screen = "save_select"
                    continue

                if app_screen == "save_select":
                    selected_slot = min(NUM_SAVE_SLOTS - 1, max(0, (mouse_pos[1] * NUM_SAVE_SLOTS) // max(1, canvas_h)))
                    enter_slot(selected_slot, force_new=False)
                    continue
                if app_screen == "extra_stats":
                    continue

                stats_tab_rect, environment_tab_rect, _ = get_ui_layout(
                    canvas_w,
                    canvas_h,
                    get_egg_rect(shake.get_offset()),
                    get_canvas_scale(),
                )
                if stats_tab_rect.collidepoint(mouse_pos):
                    if current_tab != "stats":
                        current_tab = "stats"
                        mark_save_dirty()
                    continue
                if environment_tab_rect.collidepoint(mouse_pos):
                    if current_tab != "environment":
                        current_tab = "environment"
                        mark_save_dirty()
                    continue
                if current_tab == "environment":
                    layout_anchor_rect = get_egg_rect(shake.get_offset())
                    card_handled = False
                    environments_unlocked = evolution_stage == "petawaru"
                    for idx, label in enumerate(environment_items):
                        env_key = label.lower()
                        card_rect = get_environment_card_rect(
                            canvas_w,
                            canvas_h,
                            layout_anchor_rect,
                            get_canvas_scale(),
                            idx,
                        )
                        if not card_rect.collidepoint(mouse_pos):
                            continue
                        card_handled = True
                        if env_key in {"water", "earth", "air"} and not environments_unlocked:
                            break
                        if env_key == "hidden" and not hidden_revealed:
                            break
                        if env_key in {"water", "earth", "air", "hidden"}:
                            if selected_environment != env_key:
                                selected_environment = env_key
                                mark_save_dirty()
                        break
                    if card_handled:
                        continue
                if current_tab == "stats":
                    extra_stats_rect = get_stats_row_rect_for_label(
                        canvas_w,
                        canvas_h,
                        get_egg_rect(shake.get_offset()),
                        get_canvas_scale(),
                        stat_items,
                        "Extra Stats",
                    )
                    if extra_stats_rect is not None and extra_stats_rect.collidepoint(mouse_pos):
                        app_screen = "extra_stats"
                        continue
                egg_hit_rect = get_egg_rect(shake.get_offset())
                if egg_hit_rect.collidepoint(mouse_pos):
                    local_x = mouse_pos[0] - egg_hit_rect.left
                    local_y = mouse_pos[1] - egg_hit_rect.top
                    if egg_mask.get_at((local_x, local_y)):
                        if hatching_animation_active:
                            continue

                        shake.trigger()
                        if evolution_stage == "petawaru":
                            status_flash_text = "Petting"
                            status_flash_timer = 0.35
                        else:
                            status_flash_text = "Shaking"
                            status_flash_timer = 0.25

                        if evolution_stage in {"dormant", "cracked"}:
                            evolution_click_progress += 1
                            mark_save_dirty()
                            if evolution_stage == "dormant" and evolution_click_progress >= 2:
                                evolution_stage = "cracked"
                                evolution_click_progress = 0
                                status_flash_text = ""
                                status_flash_timer = 0.0
                                mark_save_dirty()
                            elif evolution_stage == "cracked" and evolution_click_progress >= 2:
                                evolution_stage = "hatching"
                                evolution_click_progress = 0
                                hatching_animation_active = True
                                hatching_animation_timer = 0.0
                                status_flash_text = ""
                                status_flash_timer = 0.0
                                mark_save_dirty()
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if app_screen == "extra_stats":
                    app_screen = "game"
                elif app_screen == "game":
                    save_active_slot(force=True)
                    app_screen = "save_select"
                    active_slot_index = None
                elif app_screen == "save_select":
                    app_screen = "start_menu"
            elif event.type == pygame.USEREVENT:
                # events from tray callbacks
                action = getattr(event, "action", None)
                if action == "restore":
                    window_visible = True
                    # restore native window and bring to foreground
                    show_window()
                    try:
                        screen = pygame.display.set_mode((window_size[0], window_size[1]), pygame.RESIZABLE)
                        update_viewport()
                    except Exception:
                        pass
                elif action == "exit":
                    # stop tray then quit
                    save_active_slot(force=True)
                    if tray_icon is not None:
                        try:
                            tray_icon.stop()
                        except Exception:
                            pass
                    running = False

        if app_screen == "game":
            prev_active = shake.active
            shake.update(dt)
            if status_flash_timer > 0.0:
                status_flash_timer = max(0.0, status_flash_timer - dt)
                if status_flash_timer <= 0.0:
                    status_flash_text = ""

            if hatching_animation_active:
                hatching_animation_timer += dt
                if hatching_animation_timer >= hatching_animation_duration:
                    hatching_animation_active = False
                    hatching_animation_timer = 0.0
                    evolution_stage = "petawaru"
                    egg_image = petawaru_image if petawaru_image is not None else base_egg_image
                    rebuild_egg_sprite()
                    mark_save_dirty()

        if window_visible:
            draw_frame()
        else:
            # when minimized to tray, sleep briefly to avoid busy-looping
            time.sleep(0.06)

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
