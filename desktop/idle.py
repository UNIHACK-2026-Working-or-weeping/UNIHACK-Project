from pathlib import Path

from PySide6.QtCore import QTimer


class IdleAnimation:
    """
    After 5 seconds of inactivity, plays a look-left → look-right → default
    sprite sequence (0.5s each), then waits another 5 seconds before repeating.
    Resets if the user interacts with the mascot.
    """

    INACTIVITY_TIMEOUT_MS = 5000
    FRAME_DURATION_MS = 500

    # Sequence of named sprites to play (default is restored after)
    SEQUENCE = ["left", "right"]

    def __init__(self, window, base_dir: Path):
        self.window = window
        self.is_angry = False
        self.anger_level = 0

        self.sprites = {
            "default": base_dir / "mascot/mascot_centre.png",
            "left": base_dir / "mascot/mascot_left.png",
            "right": base_dir / "mascot/mascot_right.png",
        }
        self.angry_1_sprites = {
            "default": base_dir / "mascot/mascot_frown.png",
            "left": base_dir / "mascot/neckbreak_1.png",
            "right": base_dir / "mascot/neckbreak_2.png",
        }
        self.angry_2_sprites = {
            "default": base_dir / "mascot/mascot_smile.png",
            "left": base_dir / "mascot/neckbreak_1.png",
            "right": base_dir / "mascot/neckbreak_2.png",
        }

        self._playing = False
        self._frame_index = 0

        # Inactivity timer: fires once to start the sequence
        self._inactivity_timer = QTimer()
        self._inactivity_timer.setSingleShot(True)
        self._inactivity_timer.timeout.connect(self._start_sequence)

        # Frame timer: fires repeatedly during the sequence
        self._frame_timer = QTimer()
        self._frame_timer.setSingleShot(True)
        self._frame_timer.timeout.connect(self._advance_frame)

        self._start_inactivity_timer()

    def on_user_activity(self):
        self._stop_sequence()
        self._start_inactivity_timer()

    def _start_inactivity_timer(self):
        self._inactivity_timer.start(self.INACTIVITY_TIMEOUT_MS)

    def _start_sequence(self):
        self._playing = True
        self._frame_index = 0
        self._show_frame()

    def _show_frame(self):
        sequence = self.SEQUENCE  # ["left", "right"]
        if self._frame_index < len(sequence):
            sprite_key = sequence[self._frame_index]
            if self.is_angry:
                match self.anger_level:
                    case 1 | 2 | 3:
                        self.window.set_image(self.angry_1_sprites[sprite_key])
                    case _:
                        self.window.set_image(self.angry_2_sprites[sprite_key])
            else:
                self.window.set_image(self.sprites[sprite_key])

            self._frame_timer.start(self.FRAME_DURATION_MS)
        else:
            # Sequence done, restore default
            if self.is_angry:
                match self.anger_level:
                    case 1 | 2 | 3:
                        self.window.set_image(self.angry_1_sprites["default"])
                    case _:
                        self.window.set_image(self.angry_2_sprites["default"])
            else:
                self.window.set_image(self.sprites["default"])
            self._playing = False
            self._start_inactivity_timer()  # wait and potentially repeat

    def _advance_frame(self):
        self._frame_index += 1
        self._show_frame()

    def _stop_sequence(self):
        self._frame_timer.stop()
        self._inactivity_timer.stop()
        if self._playing:
            self.window.set_image(self.sprites["default"])
            self._playing = False
