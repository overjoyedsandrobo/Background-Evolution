import os
import threading


def start_tray_icon(icon_path, fallback_path, title, on_restore, on_exit):
    try:
        import pystray
        from PIL import Image as PILImage_local
    except Exception:
        return None

    img = None
    try:
        tray_path = icon_path if os.path.exists(icon_path) else fallback_path
        if os.path.exists(tray_path):
            img = PILImage_local.open(tray_path).convert("RGBA")
            resampling = getattr(PILImage_local, "Resampling", PILImage_local)
            lanczos = getattr(resampling, "LANCZOS", getattr(PILImage_local, "LANCZOS", 1))
            img = img.resize((64, 64), lanczos)
    except Exception:
        img = None

    if img is None:
        return None

    try:
        tray_icon = pystray.Icon(
            "evolution_idle",
            img,
            title,
            menu=pystray.Menu(
                pystray.MenuItem("Open", on_restore, default=True),
                pystray.MenuItem("Exit", on_exit),
            ),
        )
        thread = threading.Thread(target=tray_icon.run, daemon=True)
        thread.start()
        return tray_icon
    except Exception:
        return None
