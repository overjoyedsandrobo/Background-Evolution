import sys
import os
import time
import threading
import ctypes
from ctypes import wintypes
import pygame

WINDOW_W, WINDOW_H = 320, 600
FPS = 60


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

    # attempt to load window icon from assets/icon.png (optional)
    icon_path = os.path.join("assets", "icon.png")
    try:
        if os.path.exists(icon_path):
            icon_surf = pygame.image.load(icon_path)
            pygame.display.set_icon(icon_surf)
    except Exception:
        pass

    pygame.display.set_caption("Egg UI Demo")
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    clock = pygame.time.Clock()

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

            GWL_WNDPROC = -4
            WM_SYSCOMMAND = 0x0112
            WM_NCLBUTTONDOWN = 0x00A1
            WM_NCLBUTTONUP = 0x00A2
            WM_NCLBUTTONDBLCLK = 0x00A3
            WM_NCRBUTTONUP = 0x00A5
            SC_MOUSEMENU = 0xF090
            SC_KEYMENU = 0xF100
            HTSYSMENU = 3

            old_proc = get_long_ptr(int(hwnd), GWL_WNDPROC)
            if not old_proc:
                return

            WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

            def _wndproc(h, msg, wparam, lparam):
                # Ignore any non-client clicks on the title-bar icon (system menu hit target).
                if msg in (WM_NCLBUTTONDOWN, WM_NCLBUTTONUP, WM_NCLBUTTONDBLCLK, WM_NCRBUTTONUP):
                    if int(wparam) == HTSYSMENU:
                        return 0
                if msg == WM_SYSCOMMAND:
                    cmd = int(wparam) & 0xFFF0
                    if cmd == SC_MOUSEMENU or cmd == SC_KEYMENU:
                        return 0
                return CallWindowProc(old_proc, h, msg, wparam, lparam)

            # Keep references alive for the lifetime of the app.
            suppress_system_menu_popup._old_proc = old_proc
            suppress_system_menu_popup._proc_ref = WNDPROC(_wndproc)

            set_long_ptr(int(hwnd), GWL_WNDPROC, ctypes.cast(suppress_system_menu_popup._proc_ref, ctypes.c_void_p))
        except Exception:
            pass

    suppress_system_menu_popup()

    font = pygame.font.SysFont(None, 22)
    status_text = "Dormant"

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
            if os.path.exists(icon_path) and PILImage_local is not None:
                img = PILImage_local.open(icon_path).convert("RGBA")
                # choose resampling constant in a version-safe way
                resample = getattr(getattr(PILImage_local, 'Resampling', PILImage_local), 'LANCZOS', getattr(PILImage_local, 'LANCZOS', 1))
                img = img.resize((64, 64), resample)
        except Exception:
            img = None

        if img is None and PILImage_local is not None:
            img = PILImage_local.new("RGBA", (64, 64), (200, 200, 200, 255))

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

    # egg geometry
    egg_radius = 90
    egg_x = WINDOW_W // 2
    egg_y = 220
    # egg geometry: use separate width/height to make an egg-like oval
    egg_width = int(egg_radius * 2 * 0.82)  # slightly narrower
    egg_height = int(egg_radius * 2 * 1.18)  # slightly taller

    shake = ShakeAnimation()

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
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_pos = event.pos
                egg_hit_rect = pygame.Rect(egg_x - egg_width // 2, egg_y - egg_height // 2, egg_width, egg_height)
                if egg_hit_rect.collidepoint(mouse_pos):
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
                        pygame.display.set_mode((WINDOW_W, WINDOW_H))
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
            screen.fill((30, 30, 30))

            status_surf = font.render(status_text, True, (220, 220, 220))
            status_rect = status_surf.get_rect(center=(WINDOW_W // 2, 36))
            screen.blit(status_surf, status_rect)

            offset_x = shake.get_offset()
            egg_center = (egg_x + offset_x, egg_y)

            egg_rect_draw = pygame.Rect(0, 0, egg_width, egg_height)
            # bias the egg slightly downward to feel more egg-like
            egg_rect_draw.center = (egg_center[0], egg_center[1] + egg_height // 12)

            shadow_rect = egg_rect_draw.copy()
            shadow_rect.move_ip(6, 12)
            pygame.draw.ellipse(screen, (10, 10, 10), shadow_rect)

            pygame.draw.ellipse(screen, (245, 240, 220), egg_rect_draw)

            pygame.display.flip()
        else:
            # when minimized to tray, sleep briefly to avoid busy-looping
            time.sleep(0.06)

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
