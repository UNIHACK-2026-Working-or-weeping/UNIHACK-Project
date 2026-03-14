import random
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication

class AnimationState(Enum):
    # Idle variants (randomly chosen)
    BLINK = auto()
    WALK = auto()
    SLEEP = auto()
    # Interaction reactions
    PRESS_BLINK = auto()
    MAD = auto()

@dataclass
class Animation:
    frames: list[Path]
    frame_ms: int = 500 # number of ms between frames
    loop: bool = True

def build_animations(base_dir: Path) -> dict[AnimationState, Animation]:
    v2 = base_dir / "mascot/v2"
    return {
        AnimationState.BLINK: Animation(
            frames=[v2 / "default_1.png", v2 / "default_2.png"], frame_ms=2000
        ),
        AnimationState.WALK: Animation(
            frames=[v2 / "walk_2.png", v2 / "walk_1.png", v2 / "walk_3.png", v2 / "walk_1.png"], frame_ms=625
        ),
        AnimationState.SLEEP: Animation(
            frames=[v2 / "idle_1.png", v2 / "idle_2.png", v2 / "idle_3.png"], frame_ms=500
        ),
        AnimationState.MAD: Animation(
            frames=[v2 / "mad_1.png", v2 / "mad_2.png"], frame_ms=1000
        ),
    }

_IDLE_STATES = [AnimationState.WALK, AnimationState.BLINK, AnimationState.SLEEP]
_IDLE_WEIGHTS = [1, 6, 3] # 10% to get walk, 60% to get blink, 30% to get sleep

class AnimationController():
    INACTIVITY_TIMEOUT_MS = 10000
    WALK_STEP_PX = 1
    WALK_TICK_MS = 16

    def __init__(self, window, base_dir: Path):
        self._window = window
        self._animations = build_animations(base_dir)
        self._state = AnimationState.BLINK # Default animation
        self._frame_index = 0
        self._mad_level = 0
        self._walk_direction = -1 # -1 = left, +1 = right

        # Inactivity timer: fires once to start the sequence
        self._inactivity_timer = QTimer()
        self._inactivity_timer.setSingleShot(True)
        self._inactivity_timer.timeout.connect(self._start_random_idle)

        # Frame timer: fires repeatedly during the sequence
        self._frame_timer = QTimer()
        self._frame_timer.setSingleShot(True)
        self._frame_timer.timeout.connect(self._advance_frame)

        # High frequency timer to move avatar
        self._walk_timer = QTimer()
        self._walk_timer.timeout.connect(self._walk_step)
        
        self._start_inactivity_timer()

    def interrupt_on_user_activity(self):
        self._play(AnimationState.BLINK)
        self._interrupt()

    def resume_after_user_activity(self):
        self._play(AnimationState.BLINK)
        self._start_inactivity_timer()

    def go_mad(self):
        self._mad_level += 1
        self._interrupt()
        self._play(AnimationState.MAD)

    def go_calm(self):
        self._mad_level = 0
        self._interrupt()
        self._play(AnimationState.BLINK)
        self._start_inactivity_timer()

    def deactivate(self):
        self._interrupt()
    
    def _start_inactivity_timer(self):
        self._inactivity_timer.start(self.INACTIVITY_TIMEOUT_MS)

    def _interrupt(self):
        self._inactivity_timer.stop()
        self._frame_timer.stop()
        self._walk_timer.stop()

    def _start_random_idle(self):
        chosen = random.choices(_IDLE_STATES, weights=_IDLE_WEIGHTS, k=1)[0]
        self._play(chosen)
        self._start_inactivity_timer()

    def _play(self, state: AnimationState, then: AnimationState | None = None):
        self._state = state
        self._frame_index = 0

        if state == AnimationState.WALK:
            self._walk_timer.start(self.WALK_TICK_MS)
        else:
            self._walk_timer.stop()
        
        self._show_frame()

    def _walk_step(self):
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return

        bounds = screen.availableGeometry()
        geo = self._window.geometry()
        new_x = geo.x() + self.WALK_STEP_PX * self._walk_direction

        # Flip at screen edges
        if new_x <= bounds.left():
            new_x = bounds.left()
            self._walk_direction = 1
            self._window.flipped = True
            self._update_displayed_frame()
        elif new_x + geo.width() >= bounds.right():
            new_x = bounds.right() - geo.width()
            self._walk_direction = -1
            self._window.flipped = False
            self._update_displayed_frame()

        self._window.move(new_x, geo.y())

    def _show_frame(self):
        anim = self._animations[self._state]
        if self._frame_index < len(anim.frames):
            self._window.set_image(anim.frames[self._frame_index])
            self._frame_timer.start(anim.frame_ms)
        else:
            self._frame_index = 0
            self._window.set_image(anim.frames[self._frame_index])
            self._frame_timer.start(anim.frame_ms)

    def _update_displayed_frame(self):
        anim = self._animations[self._state]
        idx = min(self._frame_index, len(anim.frames) - 1)
        self._window.set_image(anim.frames[idx])

    def _advance_frame(self):
        self._frame_index += 1
        self._show_frame()
