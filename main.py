import sys
import os
import time
import threading
import ctypes
from ctypes import wintypes
from typing import Optional
import pygame

WINDOW_W, WINDOW_H = 300, 600
RESOLUTION_SCALE = 4
ASPECT_RATIO = WINDOW_W / WINDOW_H
FPS = 240


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class POINT(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_long),
        ("y", ctypes.c_long),
    ]


class MINMAXINFO(ctypes.Structure):
    _fields_ = [
        ("ptReserved", POINT),
        ("ptMaxSize", POINT),
        ("ptMaxPosition", POINT),
        ("ptMinTrackSize", POINT),
        ("ptMaxTrackSize", POINT),
    ]


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", wintypes.DWORD),
    ]


class ShakeAnimation:
    def __init__(self, duration=0.15, magnitude=5):
        self.active = False
        self.timer = 0.0
        self.duration = duration
        self.magnitude = magnitude

    def trigger(self):
        self.active = True
        self.timer = 0.0

    def update(self, dt):
        if not self.active:
            return
        self.timer += dt
        if self.timer > self.duration:
            self.active = False

    def get_offset(self):
        if not self.active:
            return 0
        phase = int(self.timer * 50)
        return int(self.magnitude * (-1 if phase % 2 == 0 else 1))


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
                        return surf.convert_alpha()
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
    egg_path = os.path.join("assets", "icons", "egg", "egg.png")
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
    status_text = "Dormant"
    current_tab = "stats"
    stat_items = ["Time Alive", "Features", "Power", "Survivability", "Adaptivness"]
    path_items = ["Water", "Earth", "Air", "Special"]

    # tray / visibility state
    window_visible = True
    tray_icon = None

    def start_tray():
        nonlocal tray_icon
        # Import pystray and Pillow at runtime to avoid static-analysis optional-member warnings
        try:
            import pystray
            from PIL import Image as PILImage_local
        except Exception:
            return

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

        # load PIL image for tray (resize to typical tray size)
        img = None
        try:
            if PILImage_local is not None:
                tray_path = icon_path if os.path.exists(icon_path) else image_not_found_path
                if os.path.exists(tray_path):
                    img = PILImage_local.open(tray_path).convert("RGBA")
                    # choose resampling constant in a version-safe way
                    resample = getattr(getattr(PILImage_local, 'Resampling', PILImage_local), 'LANCZOS', getattr(PILImage_local, 'LANCZOS', 1))
                    img = img.resize((64, 64), resample)
        except Exception:
            img = None

        if img is None:
            return

        try:
            tray_icon = pystray.Icon(
                "evolution_idle",
                img,
                "Evolution Idle",
                menu=pystray.Menu(
                    pystray.MenuItem("Open", on_restore, default=True),
                    pystray.MenuItem("Exit", on_exit),
                ),
            )

            t = threading.Thread(target=tray_icon.run, daemon=True)
            t.start()
        except Exception:
            tray_icon = None

    # start tray icon unless running headless (SDL dummy driver)
    # start_tray checks for pystray at runtime and will return if not available
    if os.environ.get("SDL_VIDEODRIVER", "") != "dummy":
        start_tray()

    # egg sprite setup
    egg_radius_base = 90
    egg_y_base = 220
    shake_magnitude_base = 5
    egg_image: Optional[pygame.Surface] = None
    egg_box_width = int(egg_radius_base * RESOLUTION_SCALE * 3)
    egg_box_height = int(egg_radius_base * RESOLUTION_SCALE * 3)
    egg_sprite: pygame.Surface = pygame.Surface((egg_box_width, egg_box_height), pygame.SRCALPHA)
    pygame.draw.ellipse(egg_sprite, (245, 240, 220), egg_sprite.get_rect())
    egg_mask: pygame.mask.Mask = pygame.mask.from_surface(egg_sprite)

    egg_image = load_image_with_fallback(egg_path)

    def get_canvas_scale():
        return canvas_h / WINDOW_H

    def get_ui_layout():
        scale = get_canvas_scale()
        padding = 0
        panel_gap = int(18 * scale)
        tab_height = int(34 * scale)
        bottom_margin = 0
        egg_rect = get_egg_rect(shake.get_offset())

        panel_top = egg_rect.bottom + panel_gap
        max_panel_top = canvas_h - bottom_margin - tab_height - int(120 * scale)
        panel_top = min(panel_top, max_panel_top)

        tabs_rect = pygame.Rect(padding, panel_top, max(1, canvas_w - padding * 2), tab_height)
        page_rect = pygame.Rect(
            padding,
            tabs_rect.bottom,
            max(1, canvas_w - padding * 2),
            max(1, canvas_h - tabs_rect.bottom - bottom_margin),
        )
        tab_w = tabs_rect.width // 2
        stats_tab_rect = pygame.Rect(tabs_rect.x, tabs_rect.y, tab_w, tabs_rect.height)
        path_tab_rect = pygame.Rect(tabs_rect.x + tab_w, tabs_rect.y, tabs_rect.width - tab_w, tabs_rect.height)

        return stats_tab_rect, path_tab_rect, page_rect

    def draw_lock_on_card(card_rect):
        if lock_image is None:
            return
        max_w = max(8, int(card_rect.width * 0.38))
        max_h = max(8, int(card_rect.height * 0.38))
        img_w, img_h = lock_image.get_size()
        fit = min(max_w / img_w, max_h / img_h)
        draw_w = max(1, int(img_w * fit))
        draw_h = max(1, int(img_h * fit))
        lock_scaled = pygame.transform.smoothscale(lock_image, (draw_w, draw_h))
        lock_rect = lock_scaled.get_rect(center=(card_rect.centerx, card_rect.centery))
        canvas.blit(lock_scaled, lock_rect)

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

    rebuild_egg_sprite()

    def sync_canvas_resolution():
        nonlocal canvas, canvas_w, canvas_h, font
        target_w = max(1, viewport.width * RESOLUTION_SCALE)
        target_h = max(1, viewport.height * RESOLUTION_SCALE)
        if target_w == canvas_w and target_h == canvas_h:
            return
        canvas_w, canvas_h = target_w, target_h
        canvas = pygame.Surface((canvas_w, canvas_h))
        font_size = max(12, int(22 * get_canvas_scale()))
        font = pygame.font.SysFont(None, font_size)
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

        status_surf = font.render(status_text, True, (220, 220, 220))
        status_rect = status_surf.get_rect(center=(canvas_w // 2, int(36 * get_canvas_scale())))
        canvas.blit(status_surf, status_rect)

        offset_x = shake.get_offset()
        egg_rect_draw = get_egg_rect(offset_x)
        canvas.blit(egg_sprite, egg_rect_draw)

        stats_tab_rect, path_tab_rect, page_rect = get_ui_layout()
        active_tab_color = (78, 98, 126)
        inactive_tab_color = (48, 48, 54)
        border_color = (90, 90, 96)
        text_color = (230, 230, 230)

        pygame.draw.rect(canvas, active_tab_color if current_tab == "stats" else inactive_tab_color, stats_tab_rect, border_radius=8)
        pygame.draw.rect(canvas, active_tab_color if current_tab == "path" else inactive_tab_color, path_tab_rect, border_radius=8)
        pygame.draw.rect(canvas, border_color, stats_tab_rect, 2, border_radius=8)
        pygame.draw.rect(canvas, border_color, path_tab_rect, 2, border_radius=8)

        stats_tab_text = font.render("Stats", True, text_color)
        path_tab_text = font.render("Path", True, text_color)
        canvas.blit(stats_tab_text, stats_tab_text.get_rect(center=stats_tab_rect.center))
        canvas.blit(path_tab_text, path_tab_text.get_rect(center=path_tab_rect.center))

        pygame.draw.rect(canvas, (40, 40, 44), page_rect, border_radius=10)
        pygame.draw.rect(canvas, border_color, page_rect, 2, border_radius=10)

        if current_tab == "stats":
            row_h = max(1, page_rect.height // len(stat_items))
            for i, label in enumerate(stat_items):
                row = pygame.Rect(page_rect.x, page_rect.y + i * row_h, page_rect.width, row_h)
                if i % 2 == 1:
                    pygame.draw.rect(canvas, (46, 46, 50), row)
                line_y = row.bottom - 1
                pygame.draw.line(canvas, (70, 70, 74), (row.x + 6, line_y), (row.right - 6, line_y), 1)

                label_surf = font.render(label, True, (210, 210, 210))
                value_surf = font.render("0", True, (190, 220, 190))
                canvas.blit(label_surf, label_surf.get_rect(midleft=(row.x + int(12 * get_canvas_scale()), row.centery)))
                canvas.blit(value_surf, value_surf.get_rect(midright=(row.right - int(12 * get_canvas_scale()), row.centery)))
        else:
            card_w = page_rect.width // 2
            card_h = page_rect.height // 2
            for idx, label in enumerate(path_items):
                col = idx % 2
                row = idx // 2
                card = pygame.Rect(
                    page_rect.x + col * card_w,
                    page_rect.y + row * card_h,
                    card_w if col == 0 else page_rect.width - card_w,
                    card_h if row == 0 else page_rect.height - card_h,
                )
                pygame.draw.rect(canvas, (95, 95, 95), card)
                draw_lock_on_card(card)
                label_surf = font.render(label, True, (240, 240, 240))
                canvas.blit(label_surf, label_surf.get_rect(midtop=(card.centerx, card.top + int(10 * get_canvas_scale()))))
                locked_surf = font.render("Locked", True, (70, 70, 70))
                canvas.blit(locked_surf, locked_surf.get_rect(midbottom=(card.centerx, card.bottom - int(10 * get_canvas_scale()))))

            divider_x = page_rect.x + card_w
            divider_y = page_rect.y + card_h
            pygame.draw.line(canvas, (0, 0, 0), (divider_x, page_rect.y), (divider_x, page_rect.bottom), 2)
            pygame.draw.line(canvas, (0, 0, 0), (page_rect.x, divider_y), (page_rect.right, divider_y), 2)

        screen.fill((18, 18, 18))
        scaled = pygame.transform.smoothscale(canvas, (viewport.width, viewport.height))
        screen.blit(scaled, viewport.topleft)

        pygame.display.flip()

    live_redraw = draw_frame

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                # explicit close should terminate app (and tray)
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
                stats_tab_rect, path_tab_rect, _ = get_ui_layout()
                if stats_tab_rect.collidepoint(mouse_pos):
                    current_tab = "stats"
                    continue
                if path_tab_rect.collidepoint(mouse_pos):
                    current_tab = "path"
                    continue
                egg_hit_rect = get_egg_rect(shake.get_offset())
                if egg_hit_rect.collidepoint(mouse_pos):
                    local_x = mouse_pos[0] - egg_hit_rect.left
                    local_y = mouse_pos[1] - egg_hit_rect.top
                    if egg_mask.get_at((local_x, local_y)):
                        shake.trigger()
                        status_text = "Shaking"
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
                    if tray_icon is not None:
                        try:
                            tray_icon.stop()
                        except Exception:
                            pass
                    running = False

        prev_active = shake.active
        shake.update(dt)
        # if shake stopped this frame, revert status
        if prev_active and not shake.active:
            status_text = "Dormant"

        if window_visible:
            draw_frame()
        else:
            # when minimized to tray, sleep briefly to avoid busy-looping
            time.sleep(0.06)

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
