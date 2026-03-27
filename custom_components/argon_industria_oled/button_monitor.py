"""GPIO button monitor for the Argon Industria OLED module."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import Any

_LOGGER = logging.getLogger(__name__)

# BCM GPIO pin 4 (physical pin 7) - hardwired on the Argon ONE V5 PCB.
BUTTON_PIN = 4

# Chip indices to probe, in priority order.
# Raspberry Pi 5 exposes its main GPIO bank on gpiochip4; older models use gpiochip0.
_CHIP_INDICES = (4, 0, 1, 2, 3, 5)

# Press classification thresholds (mirror the logic from the reference add-on).
# pulsetime = int(total_hold_seconds * 10), so pulsetime >= 6 means >= 0.6 s.
_LONG_PRESS_PULSETIME = 6
_DOUBLE_PRESS_WINDOW = 0.5  # seconds to wait for a second press after the first
_POLL_INTERVAL = 0.05  # seconds between GPIO polls
_THREAD_SHUTDOWN_TIMEOUT = 5.0  # seconds to wait for the monitor thread to exit cleanly
# Number of poll iterations between heartbeat log messages (~10 s at default poll interval).
_HEARTBEAT_INTERVAL_POLLS = int(10.0 / _POLL_INTERVAL)

try:  # pragma: no cover - optional hardware dependency
    import gpiod
    from gpiod.line import Bias, Direction
    from gpiod.line import Value as _LineValue

    _GPIOD_AVAILABLE = True
    _LOGGER.debug(
        "gpiod imported successfully (version: %s)",
        getattr(gpiod, "__version__", "unknown"),
    )
except ImportError as _import_err:  # pragma: no cover - optional hardware dependency
    _GPIOD_AVAILABLE = False
    _LOGGER.warning(
        "gpiod is not installed; button monitoring will be disabled (%s)",
        _import_err,
    )


class ButtonMonitor:
    """Poll a GPIO button and fire press-type callbacks.

    The monitor runs in its own daemon thread.  Three press types are detected,
    matching the logic from the BenWolstencroft/home-assistant-addons reference:

    * ``single_press``  - tap and release in < 0.6 s, no second tap within 0.5 s
    * ``double_press``  - two presses with < 0.5 s gap
    * ``long_press``    - held for >= 0.6 s
    """

    def __init__(
        self,
        on_event: Callable[[str], None],
        pin: int = BUTTON_PIN,
    ) -> None:
        self._on_event = on_event
        self._pin = pin
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._line_request: Any | None = None
        self._chip: Any | None = None
        _LOGGER.debug(
            "ButtonMonitor created (pin=%d, gpiod_available=%s)",
            self._pin,
            _GPIOD_AVAILABLE,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> bool:
        """Open GPIO and start the monitoring thread.

        Returns ``True`` when monitoring started successfully, ``False`` when
        GPIO is unavailable (gpiod not installed or no compatible chip found).
        """
        _LOGGER.debug("ButtonMonitor.start() called")

        if not _GPIOD_AVAILABLE:
            _LOGGER.warning(
                "gpiod is not installed; button monitoring is disabled. "
                "Install gpiod>=2.2.1 and ensure the 'gpio' system group is configured."
            )
            return False

        chip, line_request = self._open_gpio()
        if line_request is None:
            _LOGGER.warning(
                "ButtonMonitor: no usable GPIO chip found for pin %d; "
                "button monitoring is disabled",
                self._pin,
            )
            return False

        self._chip = chip
        self._line_request = line_request
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="argon_industria_oled_button",
        )
        self._thread.start()
        _LOGGER.info(
            "Button monitoring started (GPIO pin %d, thread=%s)",
            self._pin,
            self._thread.name,
        )
        return True

    def stop(self) -> None:
        """Stop the monitoring thread and release GPIO resources."""
        _LOGGER.debug("ButtonMonitor.stop() called")
        self._stop_event.set()

        if self._thread is not None:
            _LOGGER.debug("Waiting for button monitor thread to finish...")
            self._thread.join(timeout=_THREAD_SHUTDOWN_TIMEOUT)
            if self._thread.is_alive():
                _LOGGER.warning(
                    "Button monitor thread did not finish within %.1f s timeout",
                    _THREAD_SHUTDOWN_TIMEOUT,
                )
            else:
                _LOGGER.debug("Button monitor thread finished cleanly")
            self._thread = None

        if self._line_request is not None:
            _LOGGER.debug("Releasing GPIO line request")
            try:
                self._line_request.release()
                _LOGGER.debug("GPIO line request released")
            except Exception as err:  # pylint: disable=broad-exception-caught
                _LOGGER.warning("Error releasing GPIO line request: %s", err)
            self._line_request = None

        if self._chip is not None:
            _LOGGER.debug("Closing GPIO chip handle")
            try:
                self._chip.close()
                _LOGGER.debug("GPIO chip handle closed")
            except Exception as err:  # pylint: disable=broad-exception-caught
                _LOGGER.warning("Error closing GPIO chip: %s", err)
            self._chip = None

        _LOGGER.info("Button monitoring stopped")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _open_gpio(self) -> tuple[Any, Any] | tuple[None, None]:
        """Probe each gpiochip device and return (chip, line_request) or (None, None)."""
        _LOGGER.debug("Probing GPIO chips for button on pin %d...", self._pin)

        for idx in _CHIP_INDICES:
            path = f"/dev/gpiochip{idx}"
            _LOGGER.debug("Checking %s...", path)

            if not gpiod.is_gpiochip_device(path):
                _LOGGER.debug("%s is not a gpiochip device, skipping", path)
                continue

            _LOGGER.debug("%s is a gpiochip device, opening...", path)
            chip = gpiod.Chip(path)
            info = chip.get_info()
            _LOGGER.debug(
                "%s chip info: name=%r label=%r num_lines=%d",
                path,
                info.name,
                info.label,
                info.num_lines,
            )

            if "pinctrl" not in info.label:
                _LOGGER.debug(
                    "%s label %r does not contain 'pinctrl', "
                    "not the main GPIO controller - skipping",
                    path,
                    info.label,
                )
                chip.close()
                continue

            _LOGGER.debug(
                "%s looks like the main GPIO controller, requesting line %d...",
                path,
                self._pin,
            )
            try:
                line_request = chip.request_lines(
                    consumer="argon_industria_oled",
                    config={
                        self._pin: gpiod.LineSettings(
                            direction=Direction.INPUT,
                            bias=Bias.PULL_UP,
                        )
                    },
                )
                _LOGGER.info(
                    "Button GPIO opened successfully on %s pin %d (label=%r)",
                    path,
                    self._pin,
                    info.label,
                )
                return chip, line_request
            except Exception as err:  # pylint: disable=broad-exception-caught
                _LOGGER.warning(
                    "Cannot request GPIO line %d on %s: %s - trying next chip",
                    self._pin,
                    path,
                    err,
                )
                chip.close()

        _LOGGER.warning(
            "No compatible GPIO chip found for pin %d; button monitoring is disabled. "
            "Probed chips: %s",
            self._pin,
            [f"/dev/gpiochip{i}" for i in _CHIP_INDICES],
        )
        return None, None

    def _wait_for_release(self, press_start: float) -> tuple[float, int]:
        """Poll until the button pin goes high (released).

        Returns ``(total_hold_seconds, pulsetime)`` where
        ``pulsetime = int(total_hold * 10)``.
        """
        while not self._stop_event.is_set():
            if (
                self._line_request.get_value(self._pin)  # type: ignore[union-attr]
                != _LineValue.INACTIVE
            ):
                break
            time.sleep(_POLL_INTERVAL)
        total_hold = time.monotonic() - press_start
        return total_hold, int(total_hold * 10)

    def _check_for_second_press(self, deadline: float) -> str | None:
        """Poll the pin until *deadline* looking for a second press.

        Returns the event type string (``"double_press"`` or ``"long_press"``)
        when a second press is detected within the window, or ``None`` when
        the window expires without one.
        """
        while time.monotonic() < deadline and not self._stop_event.is_set():
            if (
                self._line_request.get_value(self._pin)  # type: ignore[union-attr]
                == _LineValue.INACTIVE
            ):
                p2_start = time.monotonic()
                _LOGGER.debug("Second press detected on pin %d - waiting for release...", self._pin)
                p2_hold, p2_pulsetime = self._wait_for_release(p2_start)
                _LOGGER.debug(
                    "Second press released on pin %d (hold=%.3f s, pulsetime=%d)",
                    self._pin,
                    p2_hold,
                    p2_pulsetime,
                )
                if p2_pulsetime >= _LONG_PRESS_PULSETIME:
                    return "long_press"
                return "double_press"
            time.sleep(_POLL_INTERVAL)
        return None

    def _monitor_loop(self) -> None:
        """Main polling loop - runs in its own daemon thread."""
        _LOGGER.debug(
            "Button monitor loop started (pin=%d, poll_interval=%.3f s)",
            self._pin,
            _POLL_INTERVAL,
        )

        iterations = 0

        while not self._stop_event.is_set():
            try:
                current_val = self._line_request.get_value(self._pin)  # type: ignore[union-attr]

                # Periodically log that the loop is alive (every ~10 s)
                iterations += 1
                if iterations % _HEARTBEAT_INTERVAL_POLLS == 0:
                    _LOGGER.debug(
                        "Button monitor heartbeat - pin %d current value: %s",
                        self._pin,
                        current_val,
                    )

                if current_val != _LineValue.INACTIVE:
                    time.sleep(_POLL_INTERVAL)
                    continue

                # Button pressed (active-low with pull-up resistor)
                press_start = time.monotonic()
                _LOGGER.debug("Button pressed on pin %d - waiting for release...", self._pin)
                total_hold, pulsetime = self._wait_for_release(press_start)
                _LOGGER.debug(
                    "Button released on pin %d - hold=%.3f s, pulsetime=%d",
                    self._pin,
                    total_hold,
                    pulsetime,
                )

                # Long press: classify immediately — no double-press check required.
                if pulsetime >= _LONG_PRESS_PULSETIME:
                    _LOGGER.info(
                        "Button event: long_press (pulsetime=%d >= %d, hold=%.3f s)",
                        pulsetime,
                        _LONG_PRESS_PULSETIME,
                        total_hold,
                    )
                    self._on_event("long_press")
                    continue

                # Short press: actively poll for a second press within the window.
                # Using an active poll (instead of time.sleep) ensures the second
                # tap is never missed even if it arrives immediately after release.
                _LOGGER.debug(
                    "Short press detected (pulsetime=%d). "
                    "Waiting up to %.2f s for a second press...",
                    pulsetime,
                    _DOUBLE_PRESS_WINDOW,
                )
                deadline = time.monotonic() + _DOUBLE_PRESS_WINDOW
                second_press_event = self._check_for_second_press(deadline)

                if second_press_event is not None:
                    _LOGGER.info("Button event: %s", second_press_event)
                    self._on_event(second_press_event)
                elif not self._stop_event.is_set():
                    _LOGGER.info(
                        "Button event: single_press (pulsetime=%d, hold=%.3f s)",
                        pulsetime,
                        total_hold,
                    )
                    self._on_event("single_press")

            except Exception as err:  # pylint: disable=broad-exception-caught
                _LOGGER.error(
                    "Button monitor loop error on pin %d: %s - retrying in 1 s",
                    self._pin,
                    err,
                    exc_info=True,
                )
                time.sleep(1.0)

        _LOGGER.debug("Button monitor loop exited (pin=%d)", self._pin)
