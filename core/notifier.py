"""Desktop notifications for MetGuardian.

I raise a notification only when a file *becomes* damaged. The state machine
already gives me exactly that set (``report.newly_damaged``), so notifications
never repeat every cycle for a file that is still damaged.

Cross-platform (Portable-ready):
* Windows -> ``win11toast`` (native toast);
* macOS / Linux -> ``plyer`` (native notification service).

A single :meth:`notify` hides the platform difference. The actual send runs on
a short daemon thread so it can never block a scan cycle, and any failure (no
notification service, missing library) is logged and swallowed rather than
crashing the scan.

For tests, a custom ``send_fn`` can be injected to bypass the OS backend.
"""

import sys
import logging
import threading

__version__ = "1.0.0"

logger = logging.getLogger("metguardian.notifier")

# How many slot numbers to list before collapsing into "+N more".
MAX_LISTED = 5


class Notifier:
    """Sends desktop notifications, choosing the right backend per OS.

    Args:
        app_name (str): the application name shown by the OS.
        send_fn (callable | None): optional ``send_fn(title, message)`` used
            instead of the OS backend (handy for tests).
    """

    def __init__(self, app_name="MetGuardian", send_fn=None):
        self.app_name = app_name
        self._send_fn = send_fn

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def notify(self, title, message):
        """Show a notification without blocking the caller.

        Args:
            title (str): notification title.
            message (str): notification body.
        """
        thread = threading.Thread(
            target=self._send_safe,
            args=(title, message),
            name="metguardian-notify",
            daemon=True,
        )
        thread.start()

    def notify_damaged(self, numbers):
        """Notify about files that have just become damaged.

        Args:
            numbers (list[str]): slot numbers that turned DAMAGED this cycle.
                If empty, nothing happens.
        """
        if not numbers:
            return
        title, message = self._build_damaged_message(numbers)
        self.notify(title, message)

    # ------------------------------------------------------------------ #
    # Message building (pure, easy to test)
    # ------------------------------------------------------------------ #

    @staticmethod
    def _build_damaged_message(numbers):
        """Build the (title, message) for a set of newly damaged files.

        Args:
            numbers (list[str]): the damaged slot numbers.

        Returns:
            tuple[str, str]: title and message.
        """
        count = len(numbers)
        listed = ["#" + str(n) for n in numbers[:MAX_LISTED]]
        extra = count - len(listed)
        if extra > 0:
            listed.append("+%d more" % extra)
        which = ", ".join(listed)
        noun = "file" if count == 1 else "files"
        title = "MetGuardian — damaged %s detected" % noun
        message = (
            "%d damaged %s in the eMule temp folder (%s). "
            "Earlier valid backups are kept and recovery may be possible."
            % (count, noun, which)
        )
        return title, message

    # ------------------------------------------------------------------ #
    # Backend dispatch
    # ------------------------------------------------------------------ #

    def _send_safe(self, title, message):
        """Run the actual send, swallowing and logging any failure."""
        try:
            if self._send_fn is not None:
                self._send_fn(title, message)
            elif sys.platform.startswith("win"):
                self._send_windows(title, message)
            else:
                self._send_plyer(title, message)
        except Exception:
            # A missing notification service must never break a scan cycle.
            logger.exception("Failed to show notification: %s", title)

    def _send_windows(self, title, message):
        """Windows native toast via win11toast."""
        from win11toast import toast
        toast(title, message, app_id=self.app_name)

    def _send_plyer(self, title, message):
        """macOS / Linux notification via plyer."""
        from plyer import notification
        notification.notify(
            title=title,
            message=message,
            app_name=self.app_name,
            timeout=10,
        )
