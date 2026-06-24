"""System tray icon for MetGuardian.

A small teal shield sits near the clock with an Open / Exit menu. Closing the
window hides the app to the tray; Exit really quits.

Two backends, one interface
---------------------------
* **Linux** -> Qt's ``QSystemTrayIcon``. The window already runs inside a Qt
  application (pywebview's Qt backend), and Qt's tray has full menu/click
  support, installs entirely via pip (PyQt6), and cleans up on exit. This is
  what lets us avoid asking the user to install PyGObject/system packages.
* **Windows / macOS** -> ``pystray`` (native tray, works great there).

Both are hidden behind :class:`TrayIcon`, so the rest of the app does not care
which one is in use.

Qt threading note
-----------------
Qt objects must be created and driven on the Qt GUI thread. ``start`` is called
from pywebview's worker thread, so on the Qt branch I marshal the icon creation
onto the GUI thread via ``QTimer.singleShot`` posted to the QApplication, and
all menu actions are delivered to the supplied callbacks (which themselves use
pywebview's thread-safe ``window.show()`` / ``destroy()``).
"""

import sys
import logging
import threading

__version__ = "2.0.0"

logger = logging.getLogger("metguardian.tray")

# MetGuardian teal (#0d9488).
TEAL = (13, 148, 136, 255)
WHITE = (255, 255, 255, 255)


def make_tray_image(size=64):
    """Draw the tray icon: a teal shield with a white check mark.

    Args:
        size (int): icon size in pixels (square).

    Returns:
        PIL.Image.Image: the RGBA icon image.
    """
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    w = h = size
    shield = [
        (w * 0.50, h * 0.07), (w * 0.88, h * 0.22), (w * 0.88, h * 0.54),
        (w * 0.50, h * 0.93), (w * 0.12, h * 0.54), (w * 0.12, h * 0.22),
    ]
    draw.polygon(shield, fill=TEAL)
    stroke = max(3, size // 11)
    draw.line(
        [(w * 0.33, h * 0.50), (w * 0.45, h * 0.63), (w * 0.69, h * 0.34)],
        fill=WHITE, width=stroke, joint="curve",
    )
    return img


class TrayIcon:
    """System tray icon with an Open / Exit menu.

    Args:
        app_name (str): name shown by the OS and as the icon tooltip.
        on_open (callable | None): called when the user picks Open / clicks.
        on_exit (callable | None): called when the user picks Exit.
    """

    def __init__(self, app_name="MetGuardian", on_open=None, on_exit=None):
        self.app_name = app_name
        self.on_open = on_open
        self.on_exit = on_exit
        self._backend = None      # "qt" or "pystray"
        self._icon = None         # pystray.Icon (Windows/macOS)
        self._qt_icon = None      # QSystemTrayIcon (Linux)
        self._qt_menu = None      # keep the QMenu alive
        self._thread = None

    def start(self) -> bool:
        """Create and run the tray icon. Returns True on success.

        On Linux I use Qt; elsewhere pystray. Any failure degrades gracefully
        (returns False) so the app can fall back to quitting on window close.
        """
        if sys.platform.startswith("linux"):
            return self._start_qt()
        return self._start_pystray()

    def stop(self):
        """Stop / remove the tray icon (safe to call more than once)."""
        try:
            if self._backend == "pystray" and self._icon is not None:
                self._icon.stop()
                self._icon = None
            elif self._backend == "qt" and self._qt_icon is not None:
                icon = self._qt_icon
                self._qt_icon = None
                self._qt_run(lambda: icon.hide())
        except Exception:
            logger.exception("Failed to stop tray icon.")

    # ------------------------------------------------------------------ #
    # Qt backend (Linux)
    # ------------------------------------------------------------------ #

    def _start_qt(self) -> bool:
        try:
            import time
            from qtpy.QtWidgets import QApplication, QSystemTrayIcon

            # start() runs on a worker thread; the QApplication may not exist
            # for a brief moment after the GUI loop begins. Poll for it.
            app = None
            for _ in range(30):  # up to ~3 seconds
                app = QApplication.instance()
                if app is not None:
                    break
                time.sleep(0.1)
            if app is None:
                logger.warning("No QApplication yet; cannot create Qt tray.")
                return False
            if not QSystemTrayIcon.isSystemTrayAvailable():
                logger.warning("Qt reports no system tray available.")
                return False

            self._backend = "qt"
            self._qt_run(self._qt_build_icon)  # build on the GUI thread
            logger.info("Tray icon started (Qt backend).")
            return True
        except Exception:
            logger.exception("Qt tray unavailable; continuing without it.")
            return False

    def _qt_run(self, fn):
        """Run ``fn`` on the Qt GUI thread via a single-shot timer."""
        from qtpy.QtCore import QTimer
        from qtpy.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            return
        # Posting with the app as the timer's context object makes fn run on the
        # GUI thread's event loop, no matter which thread calls this.
        QTimer.singleShot(0, app, fn)

    def _qt_build_icon(self):
        """Create the QSystemTrayIcon (must run on the GUI thread)."""
        import io
        from qtpy.QtWidgets import QSystemTrayIcon, QMenu
        from qtpy.QtGui import QIcon, QPixmap
        from qtpy.QtCore import QByteArray

        # Convert the Pillow image to a QIcon via PNG bytes.
        buf = io.BytesIO()
        make_tray_image().save(buf, format="PNG")
        pix = QPixmap()
        pix.loadFromData(QByteArray(buf.getvalue()))
        icon = QIcon(pix)

        tray = QSystemTrayIcon(icon)
        tray.setToolTip(self.app_name)

        menu = QMenu()
        open_action = menu.addAction("Open")
        open_action.triggered.connect(lambda: self._safe(self.on_open))
        exit_action = menu.addAction("Exit")
        exit_action.triggered.connect(lambda: self._safe(self.on_exit))
        tray.setContextMenu(menu)

        # Left-click / double-click also opens the window.
        def on_activated(reason):
            trigger = QSystemTrayIcon.ActivationReason.Trigger
            dbl = QSystemTrayIcon.ActivationReason.DoubleClick
            if reason in (trigger, dbl):
                self._safe(self.on_open)

        tray.activated.connect(on_activated)
        tray.show()

        # Keep references alive (the menu must outlive this function).
        self._qt_icon = tray
        self._qt_menu = menu

    # ------------------------------------------------------------------ #
    # pystray backend (Windows / macOS)
    # ------------------------------------------------------------------ #

    def _start_pystray(self) -> bool:
        try:
            import pystray

            menu = pystray.Menu(
                pystray.MenuItem("Open", lambda i, it: self._safe(self.on_open), default=True),
                pystray.MenuItem("Exit", lambda i, it: self._safe(self.on_exit)),
            )
            self._icon = pystray.Icon(
                self.app_name, make_tray_image(), self.app_name, menu
            )
            if not getattr(self._icon, "HAS_MENU", True):
                logger.warning("pystray backend has no menu support; disabling tray.")
                self._icon = None
                return False
            self._backend = "pystray"
            self._thread = threading.Thread(
                target=self._icon.run, name="metguardian-tray", daemon=True
            )
            self._thread.start()
            logger.info("Tray icon started (pystray backend).")
            return True
        except Exception:
            logger.exception("pystray tray unavailable; continuing without it.")
            self._icon = None
            return False

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _safe(self, fn):
        """Invoke a callback, logging (never raising) on failure."""
        if fn is None:
            return
        try:
            fn()
        except Exception:
            logger.exception("Tray action handler failed")
