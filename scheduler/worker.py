"""Background scheduler for MetGuardian.

A single background thread runs a scan cycle, waits for the configured interval
(re-read every time, so settings changes take effect without a restart), and
repeats. The thread is a daemon and stops cleanly when asked.

Decoupling
----------
The scheduler does not know about the UI or the notifier. After each cycle it
invokes an optional ``on_cycle_complete(report)`` callback; the application
wires that to "refresh the UI" and "notify about newly damaged files". This
keeps the scheduler focused purely on *timing*.

Concurrency
-----------
A lock serializes cycles, so a manual :meth:`scan_now` can never overlap with
the periodic cycle. ``scan_now`` runs synchronously and returns the report,
which is convenient for the UI bridge (it can refresh with fresh data
immediately after the user saves new folders).
"""

import logging
import threading

__version__ = "1.0.0"

logger = logging.getLogger("metguardian.scheduler")

# Config key and fallback for the interval between scans.
CFG_INTERVAL = "scan_interval_seconds"
DEFAULT_INTERVAL = 300  # 5 minutes


class ScanScheduler:
    """Runs :meth:`StateMachine.run_cycle` on a timer in a background thread.

    Args:
        state_machine: the :class:`~core.state_machine.StateMachine` to run.
        repository: the data-access layer (used to read the interval).
        on_cycle_complete: optional callable invoked with the ``ScanReport``
            after every cycle (periodic or manual).
    """

    def __init__(self, state_machine, repository, on_cycle_complete=None):
        self.sm = state_machine
        self.repo = repository
        self.on_cycle_complete = on_cycle_complete

        self._thread = None
        self._stop = threading.Event()   # set -> the loop should exit
        self._wake = threading.Event()   # set -> cut the current wait short
        self._lock = threading.Lock()    # serializes cycles

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def start(self):
        """Start the background loop (runs an immediate first cycle).

        Calling start twice is a no-op while the thread is alive.
        """
        if self.is_running():
            return
        self._stop.clear()
        self._wake.clear()
        self._thread = threading.Thread(
            target=self._loop, name="metguardian-scanner", daemon=True
        )
        self._thread.start()
        logger.info("Scheduler started.")

    def stop(self, timeout=5):
        """Ask the loop to exit and wait for the thread to finish.

        Args:
            timeout (int): seconds to wait for the thread to join.
        """
        self._stop.set()
        self._wake.set()  # interrupt any in-progress wait
        if self._thread:
            self._thread.join(timeout=timeout)
        logger.info("Scheduler stopped.")

    def is_running(self) -> bool:
        """Return ``True`` if the background thread is alive."""
        return self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------------ #
    # Scans
    # ------------------------------------------------------------------ #

    def scan_now(self):
        """Run a cycle immediately and return its report (synchronous).

        Used by the UI after the user changes folders, so the change takes
        effect at once instead of waiting for the next tick.

        Returns:
            ScanReport | None: the report, or ``None`` if the cycle raised.
        """
        return self._run_one_cycle()

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _loop(self):
        """The background loop: scan, then wait the interval, then repeat."""
        while not self._stop.is_set():
            self._run_one_cycle()
            # Wait up to the interval, but wake early on stop() or a manual
            # trigger. wait() returns True if the event was set, False on timeout.
            self._wake.wait(timeout=self._interval_seconds())
            self._wake.clear()

    def _run_one_cycle(self):
        """Run exactly one cycle under the lock, then fire the callback."""
        with self._lock:
            try:
                report = self.sm.run_cycle()
            except Exception:
                # The thread must survive any failure and keep scanning.
                logger.exception("Scan cycle failed")
                return None

            if self.on_cycle_complete is not None:
                try:
                    self.on_cycle_complete(report)
                except Exception:
                    logger.exception("on_cycle_complete callback failed")
            return report

    def _interval_seconds(self) -> int:
        """Read the scan interval from config, falling back to the default."""
        raw = self.repo.get_config(CFG_INTERVAL)
        try:
            value = int(raw)
            return value if value > 0 else DEFAULT_INTERVAL
        except (TypeError, ValueError):
            return DEFAULT_INTERVAL
