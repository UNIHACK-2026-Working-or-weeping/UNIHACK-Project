import json
import queue
import random
import sys
import threading
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import IntFlag, auto
from pathlib import Path

import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from pydantic import BaseModel
from PySide6.QtCore import QObject, QPoint, QRect, QSize, Qt, QTimer
from PySide6.QtGui import (
    QAction,
    QGuiApplication,
    QIcon,
    QMouseEvent,
    QPixmap,
    QTransform,
)
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMenu,
    QSystemTrayIcon,
    QWidget,
)

CONFIG_PATH = Path(__file__).parent / "config.json"

try:
    from ai_inference import ensure_model_exists, generateAndPlaySound, getMessage

    ensure_model_exists()
    ai_features_enabled = True
except ImportError:
    print("Llama.cpp not installed, disabled AI features")
    ai_features_enabled = False

    def getMessage(domain: str, event: str | None = None) -> str:
        return "Generic passive aggressive quote goes here"

    def generateAndPlaySound(message: str) -> None:
        return None


from animation import AnimationController, AnimationMode


class ResizeRegion(IntFlag):
    NONE = 0
    LEFT = auto()
    RIGHT = auto()
    TOP = auto()
    BOTTOM = auto()


class MascotWindow(QWidget):
    def __init__(self, image_path: str):
        super().__init__()

        self.drag_offset = QPoint()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.Window
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setStyleSheet("background: transparent;")

        self.label = QLabel(self)
        self.label.setStyleSheet("background: transparent;")

        self.image_path: Path | None = None
        self.pixmap = QPixmap()
        self.alpha_image: Image.Image | None = None

        self.aspect_ratio = 1.0
        self.resize_margin = 10
        self.min_w = 80
        self.min_h = 80

        self._resize_region = ResizeRegion.NONE
        self._is_resizing = False
        self._resize_press_global = QPoint()
        self._resize_start_geometry = QRect()
        self._resize_anchor = QPoint()

        self._is_scaling = False
        self._scale_press_global = QPoint()
        self._scale_start_geometry = QRect()
        self._scale_start_center = QPoint()

        self._is_dragging = False

        self.setMinimumSize(self.min_w, self.min_h)
        self.setMouseTracking(True)
        self.label.setMouseTracking(True)

        self._last_pixmap_size = QSize(0, 0)
        self.flipped = False

        self.interrupt_on_user_activity: Callable[[], None] | None = None
        self.resume_after_user_activity: Callable[[], None] | None = None

        self.set_image(image_path)

    def set_image(self, image_path: str | Path) -> None:
        path = Path(image_path)
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            raise FileNotFoundError(f"Could not load image: {path}")

        self.image_path = path
        self.pixmap = pixmap
        self.aspect_ratio = (
            self.pixmap.width() / self.pixmap.height()
            if self.pixmap.height() > 0
            else 1.0
        )

        if self.size().width() <= 1 or self.size().height() <= 1:
            self.resize(self.pixmap.size())
        elif (
            self.pixmap.width() != self._last_pixmap_size.width()
            or self.pixmap.height() != self._last_pixmap_size.height()
        ):
            self._apply_aspect_resize_from_size(
                self.width(), self.height(), keep_center=True
            )

        self._update_scaled_label()

        self.alpha_image = Image.open(path).convert("RGBA")
        self._update_min_size_from_image()

        self._last_pixmap_size = self.pixmap.size()

    def _update_min_size_from_image(self) -> None:
        if self.pixmap.isNull():
            return
        self.min_w = max(40, int(self.pixmap.width() * 0.2))
        self.min_h = max(40, int(self.min_w / max(self.aspect_ratio, 1e-9)))
        self.setMinimumSize(self.min_w, self.min_h)

    def _update_scaled_label(self) -> None:
        if self.pixmap.isNull():
            return
        scaled = self.pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        if self.flipped:
            scaled = scaled.transformed(QTransform().scale(-1, 1))
        self.label.setPixmap(scaled)
        self.label.resize(self.size())
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_scaled_label()

    def _original_pixel_at(self, pos: QPoint) -> tuple[int, int] | None:
        if self.alpha_image is None:
            return None

        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0:
            return None

        draw_w = int(min(w, h * self.aspect_ratio))
        draw_h = int(min(h, w / max(self.aspect_ratio, 1e-9)))
        offset_x = (w - draw_w) // 2
        offset_y = (h - draw_h) // 2

        x = pos.x()
        y = pos.y()
        if (
            x < offset_x
            or y < offset_y
            or x >= offset_x + draw_w
            or y >= offset_y + draw_h
        ):
            return None

        local_x = x - offset_x
        local_y = y - offset_y

        src_x = int(local_x * self.alpha_image.width / max(draw_w, 1))
        src_y = int(local_y * self.alpha_image.height / max(draw_h, 1))

        src_x = max(0, min(self.alpha_image.width - 1, src_x))
        src_y = max(0, min(self.alpha_image.height - 1, src_y))
        return src_x, src_y

    def is_opaque_at(self, pos: QPoint, alpha_threshold: int = 10) -> bool:
        mapped = self._original_pixel_at(pos)
        if mapped is None or self.alpha_image is None:
            return False
        x, y = mapped
        pixel = self.alpha_image.getpixel((x, y))
        if isinstance(pixel, tuple):
            if len(pixel) >= 4:
                alpha = pixel[3]
                if alpha is None:
                    return False
                return alpha > alpha_threshold
            return True
        if pixel is None:
            return False
        return pixel > alpha_threshold

    def _hit_test_resize_region(self, pos: QPoint) -> ResizeRegion:
        r = self.rect()
        x = pos.x()
        y = pos.y()
        m = self.resize_margin

        region = ResizeRegion.NONE
        if x <= r.left() + m:
            region |= ResizeRegion.LEFT
        elif x >= r.right() - m:
            region |= ResizeRegion.RIGHT

        if y <= r.top() + m:
            region |= ResizeRegion.TOP
        elif y >= r.bottom() - m:
            region |= ResizeRegion.BOTTOM

        return region

    def _cursor_for_region(self, region: ResizeRegion) -> Qt.CursorShape:
        if region == (ResizeRegion.LEFT | ResizeRegion.TOP) or region == (
            ResizeRegion.RIGHT | ResizeRegion.BOTTOM
        ):
            return Qt.CursorShape.SizeFDiagCursor
        if region == (ResizeRegion.RIGHT | ResizeRegion.TOP) or region == (
            ResizeRegion.LEFT | ResizeRegion.BOTTOM
        ):
            return Qt.CursorShape.SizeBDiagCursor
        if region == ResizeRegion.LEFT or region == ResizeRegion.RIGHT:
            return Qt.CursorShape.SizeHorCursor
        if region == ResizeRegion.TOP or region == ResizeRegion.BOTTOM:
            return Qt.CursorShape.SizeVerCursor
        return Qt.CursorShape.ArrowCursor

    def _apply_aspect_resize_from_size(
        self, target_w: int, target_h: int, keep_center: bool = False
    ) -> None:
        target_w = max(target_w, self.minimumWidth())
        target_h = max(target_h, self.minimumHeight())

        ratio = self.aspect_ratio if self.aspect_ratio > 0 else 1.0
        w_from_h = int(target_h * ratio)
        h_from_w = int(target_w / ratio)

        if abs(w_from_h - target_w) < abs(h_from_w - target_h):
            new_w = max(w_from_h, self.minimumWidth())
            new_h = int(new_w / ratio)
        else:
            new_h = max(h_from_w, self.minimumHeight())
            new_w = int(new_h * ratio)

        new_w = max(new_w, self.minimumWidth())
        new_h = max(new_h, self.minimumHeight())

        if keep_center:
            center = self.geometry().center()
            x = center.x() - new_w // 2
            y = center.y() - new_h // 2
            self.setGeometry(x, y, new_w, new_h)
        else:
            self.resize(new_w, new_h)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            local_pos = event.position().toPoint()

            if (
                event.modifiers() & Qt.KeyboardModifier.ShiftModifier
            ) and self.is_opaque_at(local_pos):
                self._is_scaling = True
                self._scale_press_global = event.globalPosition().toPoint()
                self._scale_start_geometry = self.geometry()
                self._scale_start_center = self.geometry().center()
                self.setCursor(Qt.CursorShape.SizeAllCursor)
                if self.interrupt_on_user_activity:
                    self.interrupt_on_user_activity()
                event.accept()
                return

            region = self._hit_test_resize_region(local_pos)
            if region != ResizeRegion.NONE:
                self._is_resizing = True
                self._resize_region = region
                self._resize_press_global = event.globalPosition().toPoint()
                self._resize_start_geometry = self.geometry()

                if region & ResizeRegion.LEFT:
                    anchor_x = self._resize_start_geometry.right()
                elif region & ResizeRegion.RIGHT:
                    anchor_x = self._resize_start_geometry.left()
                else:
                    anchor_x = self._resize_start_geometry.center().x()

                if region & ResizeRegion.TOP:
                    anchor_y = self._resize_start_geometry.bottom()
                elif region & ResizeRegion.BOTTOM:
                    anchor_y = self._resize_start_geometry.top()
                else:
                    anchor_y = self._resize_start_geometry.center().y()

                self._resize_anchor = QPoint(anchor_x, anchor_y)
                self.setCursor(self._cursor_for_region(region))
                if self.interrupt_on_user_activity:
                    self.interrupt_on_user_activity()
                event.accept()
                return

            if self.is_opaque_at(local_pos):
                self._is_dragging = True
                self.drag_offset = (
                    event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                )
                if self.interrupt_on_user_activity:
                    self.interrupt_on_user_activity()
                event.accept()
                return

        event.ignore()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        local_pos = event.position().toPoint()

        if self._is_scaling and (event.buttons() & Qt.MouseButton.LeftButton):
            self._perform_shift_scale(event.globalPosition().toPoint())
            event.accept()
            return

        if self._is_resizing and (event.buttons() & Qt.MouseButton.LeftButton):
            self._perform_resize_aspect(event.globalPosition().toPoint())
            event.accept()
            return

        if self._is_dragging and (event.buttons() & Qt.MouseButton.LeftButton):
            self.move(event.globalPosition().toPoint() - self.drag_offset)
            event.accept()
            return

        if not event.buttons() & Qt.MouseButton.LeftButton:
            region = self._hit_test_resize_region(local_pos)
            self.setCursor(self._cursor_for_region(region))

        event.ignore()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self._is_scaling:
                self._is_scaling = False
                self.setCursor(Qt.CursorShape.ArrowCursor)
                if self.resume_after_user_activity:
                    self.resume_after_user_activity()
                event.accept()
                return
            if self._is_resizing:
                self._is_resizing = False
                self._resize_region = ResizeRegion.NONE
                self.setCursor(Qt.CursorShape.ArrowCursor)
                if self.resume_after_user_activity:
                    self.resume_after_user_activity()
                event.accept()
                return
            if self._is_dragging:
                self._is_dragging = False
                self.drag_offset = QPoint()
                if self.resume_after_user_activity:
                    self.resume_after_user_activity()
                event.accept()
                return
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event) -> None:
        if not self._is_resizing and not self._is_scaling:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().leaveEvent(event)

    def _perform_resize_aspect(self, global_pos: QPoint) -> None:
        start = self._resize_start_geometry
        delta = global_pos - self._resize_press_global
        region = self._resize_region
        ratio = self.aspect_ratio if self.aspect_ratio > 0 else 1.0

        if (region & (ResizeRegion.LEFT | ResizeRegion.RIGHT)) and not (
            region & (ResizeRegion.TOP | ResizeRegion.BOTTOM)
        ):
            width = start.width() + (
                -delta.x() if region & ResizeRegion.LEFT else delta.x()
            )
            width = max(width, self.minimumWidth())
            height = max(int(width / ratio), self.minimumHeight())
        elif (region & (ResizeRegion.TOP | ResizeRegion.BOTTOM)) and not (
            region & (ResizeRegion.LEFT | ResizeRegion.RIGHT)
        ):
            height = start.height() + (
                -delta.y() if region & ResizeRegion.TOP else delta.y()
            )
            height = max(height, self.minimumHeight())
            width = max(int(height * ratio), self.minimumWidth())
        else:
            dx = global_pos.x() - self._resize_anchor.x()
            dy = global_pos.y() - self._resize_anchor.y()
            width_from_x = abs(dx)
            width_from_y = int(abs(dy) * ratio)
            width = max(width_from_x, width_from_y, self.minimumWidth())
            height = max(int(width / ratio), self.minimumHeight())

        if region & ResizeRegion.LEFT:
            x = self._resize_anchor.x() - width
        elif region & ResizeRegion.RIGHT:
            x = self._resize_anchor.x()
        else:
            x = start.center().x() - width // 2

        if region & ResizeRegion.TOP:
            y = self._resize_anchor.y() - height
        elif region & ResizeRegion.BOTTOM:
            y = self._resize_anchor.y()
        else:
            y = start.center().y() - height // 2

        self.setGeometry(x, y, width, height)

    def _perform_shift_scale(self, global_pos: QPoint) -> None:
        delta = global_pos - self._scale_press_global
        ratio = self.aspect_ratio if self.aspect_ratio > 0 else 1.0

        scale_delta = delta.x() + delta.y()
        factor = 1.0 + (scale_delta / 400.0)
        factor = max(0.2, min(5.0, factor))

        start = self._scale_start_geometry
        new_w = max(int(start.width() * factor), self.minimumWidth())
        new_h = max(int(new_w / ratio), self.minimumHeight())

        center = self._scale_start_center
        x = center.x() - new_w // 2
        y = center.y() - new_h // 2
        self.setGeometry(x, y, new_w, new_h)


class MessagePopup(QWidget):
    def __init__(self, mascot_window: MascotWindow):
        super().__init__()
        self.mascot_window = mascot_window
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.Window
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.label = QLabel(self)
        self.label.setStyleSheet("""
            QLabel {
                background: rgba(30, 30, 30, 230);
                border-radius: 12px;
                padding: 16px;
                color: white;
                font-size: 14px;
            }
        """)
        self.label.setWordWrap(True)

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide)

        self.hide()

    def show_message(self, message: str, duration_ms: int = 4000) -> None:
        self.label.setText(message)
        self.label.adjustSize()
        self.resize(self.label.size())

        mascot_rect = self.mascot_window.geometry()
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            screen_rect = screen.availableGeometry()

            popup_width = self.width()
            preferred_x = mascot_rect.left() - popup_width - 20

            if preferred_x < screen_rect.left():
                x = mascot_rect.right() + 20
            else:
                x = preferred_x

            y = mascot_rect.center().y() - self.height() // 2

            x = max(screen_rect.left(), min(x, screen_rect.right() - popup_width))
            y = max(screen_rect.top(), min(y, screen_rect.bottom() - self.height()))
        else:
            x = mascot_rect.left() - self.width() - 20
            y = mascot_rect.center().y() - self.height() // 2

        self.move(x, y)
        self.show()
        self.timer.start(duration_ms)


class FastAPIController:
    def __init__(self, mascot_app: "MascotApp"):
        self.mascot_app = mascot_app
        self.app = FastAPI(title="Mascot Control API", version="1.0.0")
        self.already_queued = False
        self._queue_lock = threading.Lock()

        self.app.add_middleware(
            CORSMiddleware,  # ty: ignore[invalid-argument-type]
            allow_origins="*",
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        self._configure_routes()

    def _configure_routes(self) -> None:
        class SetImageRequest(BaseModel):
            image: str

        class SetTeethRequest(BaseModel):
            domain: str | None = None
            event: dict[str, str] | None = None

        class ShowMascotRequest(BaseModel):
            message: str | None = None

        class SetAvatarRequest(BaseModel):
            version: str

        @self.app.get("/health")
        def health():
            return {"status": "ok"}

        @self.app.get("/image")
        def get_current_image():
            current = (
                self.mascot_app.window.image_path.name
                if self.mascot_app.window.image_path is not None
                else None
            )
            return {
                "current_image": current,
                "is_angry": self.mascot_app.is_angry,
            }

        @self.app.post("/image/calm")
        def toggle_image():
            self.mascot_app.get_calm()
            return {"ok": True, "action": "toggle"}

        @self.app.post("/image/default")
        def set_default():
            self.mascot_app.request_set_named_image("default")
            return {"ok": True, "action": "set_default"}

        @self.app.post("/image/angry")
        def set_teeth(payload: SetTeethRequest, background_tasks: BackgroundTasks):
            with self._queue_lock:
                if self.already_queued:
                    return {"ok": True, "action": "set_teeth"}
                self.already_queued = True

            def process_teeth_async(domain: str | None):
                if payload.domain:
                    # Parse event first regardless of AI
                    parsed_event: str | None = None
                    if payload.event:
                        event_title = payload.event.get("title", "").strip()
                        event_start_raw = payload.event.get("start", "").strip()
                        if event_title and event_start_raw:
                            try:
                                event_start = datetime.fromisoformat(
                                    event_start_raw.replace("Z", "+00:00")
                                )
                                now = datetime.now(event_start.tzinfo)
                                days_until_event = (
                                    event_start.date() - now.date()
                                ).days
                                if days_until_event >= 0:
                                    if days_until_event < 3:
                                        parsed_event = f"{event_title} on {event_start.strftime('%A')}"
                                    else:
                                        parsed_event = f"{event_title} in {days_until_event} days"
                            except ValueError:
                                parsed_event = None

                    self.mascot_app.request_angry()

                    if not ai_features_enabled:
                        if parsed_event:
                            message = f"Get off {payload.domain}! You have {parsed_event}"
                        else:
                            message = f"Stop scrolling on {payload.domain}!"
                    else:
                        if parsed_event:
                            message = getMessage(payload.domain, parsed_event)
                        else:
                            message = getMessage(payload.domain)

                        if message == "":
                            if parsed_event:
                                message = getMessage(payload.domain, parsed_event)
                            else:
                                message = getMessage(payload.domain)

                    print(f"[/image/angry] Generated message: {message}")
                    self.mascot_app.request_show_message(message, permanent=True)
                    if self.mascot_app.get_voice_enabled():
                        generateAndPlaySound(message)

                self.already_queued = False
                print("[/image/angry] Processing completed")

            background_tasks.add_task(process_teeth_async, payload.domain)
            return {"ok": True, "action": "set_teeth"}

        @self.app.post("/image/set")
        def set_image(payload: SetImageRequest):
            image_name = payload.image.strip().lower()
            if image_name not in {"default", "teeth"}:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid image. Use 'default' or 'teeth'.",
                )
            self.mascot_app.request_set_named_image(image_name)
            return {"ok": True, "action": "set_image", "image": image_name}

        @self.app.post("/image/hide")
        def hide_mascot():
            try:
                self.mascot_app.request_set_named_image("default")
                self.mascot_app.request_show_message("Mascot turned off", permanent=False)
                self.mascot_app._command_queue.put("hide")
                return {"ok": True, "action": "hide", "message": "Mascot turned off"}
            except Exception as e:
                print("[ERROR] hide_mascot:", e)
                return {"ok": False, "action": "hide", "error": str(e)}

        @self.app.post("/image/show")
        async def show_mascot(request: Request):
            payload = None
            try:
                body = await request.body()
                if body:
                    payload = ShowMascotRequest(**json.loads(body))
            except Exception:
                pass
            try:
                self.mascot_app._command_queue.put("show")
                self.mascot_app.request_set_named_image("default")
                msg = (
                    (payload.message or "").strip()
                    if payload and payload.message
                    else None
                )
                if msg:
                    self.mascot_app.request_show_message(msg, permanent=False)
                else:
                    self.mascot_app.request_show_message("Mascot turned on", permanent=False)
                return {"ok": True, "action": "show", "message": msg or "Mascot turned on"}
            except Exception as e:
                print("[ERROR] show_mascot:", e)
                return {"ok": False, "action": "show", "error": str(e)}

        @self.app.post("/message/hide")
        def hide_message():
            self.mascot_app._command_queue.put("hide_message")
            return {"ok": True}

        @self.app.get("/test/popup")
        def test_popup():
            self.mascot_app.request_show_message(
                "Test popup message!", permanent=False
            )
            return {"ok": True, "action": "test_popup"}

        @self.app.post("/avatar/set")
        def set_avatar(payload: SetAvatarRequest):
            version = payload.version.strip().lower()
            if version not in {"v1", "v2"}:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid version. Use 'v1' or 'v2'.",
                )
            mode = AnimationMode.V1 if version == "v1" else AnimationMode.V2
            self.mascot_app.toggle_animation_version(mode == AnimationMode.V1)
            return {"ok": True, "action": "set_avatar", "version": version}

class MascotApp(QObject):
    def __init__(self, app: QApplication):
        super().__init__()
        self.app = app
        self.base_dir = Path(__file__).parent
        self.app_icon = self.base_dir / "mascot_logo.png"
        self.default_image = self.base_dir / "mascot/v2/default_1.png"
        self.is_angry = False
        self.animation_mode = self._load_saved_version()

        self.window = MascotWindow(str(self.default_image))
        self.window.resize(200, 200)
        self._position_window()

        self.voice_enabled = False
        self._voice_lock = threading.Lock()

        self.message_popup = MessagePopup(self.window)

        self.tray = self._create_tray_icon()

        self._command_queue: queue.Queue[str] = queue.Queue()

        self._pending_message: tuple[str, bool] | None = None
        self._message_lock = threading.Lock()

        self.api = FastAPIController(self)
        self._start_api_server()

        self.command_timer = QTimer(self.window)
        self.command_timer.timeout.connect(self._process_pending_command)
        self.command_timer.start(100)

    def _load_saved_version(self):
        try:
            with open(CONFIG_PATH) as f:
                data = json.load(f)
                return AnimationMode.V1 if data.get("avatarVersion") == "v1" else AnimationMode.V2
        except (FileNotFoundError, json.JSONDecodeError):
            self._save_version("v2")
            return AnimationMode.V2

    def _position_window(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            geometry = screen.availableGeometry()
            x = geometry.right() - self.window.width() - 40
            y = geometry.bottom() - self.window.height() - 40
            self.window.move(x, y)

    def _create_tray_icon(self) -> QSystemTrayIcon:
        tray_icon = QSystemTrayIcon(self.app)
        icon = QIcon(str(self.app_icon))
        tray_icon.setIcon(icon)
        tray_icon.setToolTip("Mascot App")

        menu = QMenu()

        toggle_voice_action = QAction("Enable Voice", menu)
        toggle_voice_action.setCheckable(True)
        toggle_voice_action.setChecked(self.voice_enabled)
        toggle_voice_action.triggered.connect(self.toggle_voice)
        menu.addAction(toggle_voice_action)

        toggle_legacy_animation_action = QAction("Use Alternate Costume", menu)
        toggle_legacy_animation_action.setCheckable(True)
        toggle_legacy_animation_action.setChecked(
            self.animation_mode == AnimationMode.V1
        )
        toggle_legacy_animation_action.toggled.connect(self.toggle_animation_version)
        menu.addAction(toggle_legacy_animation_action)

        menu.addSeparator()

        quit_action = QAction("Close App", menu)
        quit_action.triggered.connect(self.app.quit)
        menu.addAction(quit_action)

        tray_icon.setContextMenu(menu)
        tray_icon.show()
        return tray_icon

    def _is_port_in_use(self, port: int) -> bool:
        import socket

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            result = sock.connect_ex(("127.0.0.1", port))
            return result == 0

    def _start_api_server(self) -> None:
        preferred_port = 8000
        if self._is_port_in_use(preferred_port):
            print(
                f"[WARNING] Port {preferred_port} is already in use. API server will not start."
            )
            print(
                "Please close the other service or restart this app. The mascot UI will still run, but extension API calls will fail until port 8000 is free."
            )
            self.api_thread = None
            return

        config = uvicorn.Config(
            self.api.app,
            host="127.0.0.1",
            port=preferred_port,
            log_level="info",
        )
        server = uvicorn.Server(config)

        def run_server():
            try:
                server.run()
            except Exception as e:
                print(f"[ERROR] FastAPI server thread failed: {e}")
            finally:
                if hasattr(self, "animation"):
                    self._command_queue.put("server_down")

        self.api_thread = threading.Thread(
            target=run_server,
            daemon=True,
            name="fastapi-server-thread",
        )
        self.api_thread.start()

    def request_toggle(self) -> None:
        self._command_queue.put("toggle")

    def request_angry(self) -> None:
        self._command_queue.put("make_angry")

    def request_set_named_image(self, image_name: str) -> None:
        self._command_queue.put(image_name)

    def request_show_message(self, message: str, permanent: bool = False) -> None:
        with self._message_lock:
            self._pending_message = (message, permanent)

    def toggle_voice(self) -> None:
        with self._voice_lock:
            self.voice_enabled = not self.voice_enabled

    def get_voice_enabled(self) -> bool:
        with self._voice_lock:
            return self.voice_enabled

    def toggle_animation_version(self, checked: bool) -> None:
        self._command_queue.put("anim_v1" if checked else "anim_v2")

    def _process_pending_command(self) -> None:
        while not self._command_queue.empty():
            try:
                cmd = self._command_queue.get_nowait()
            except queue.Empty:
                break

            if cmd == "default":
                if self.is_angry:
                    self.get_calm()
            elif cmd == "teeth":
                self.get_angry()
            elif cmd == "make_angry":
                self.get_angry()
            elif cmd == "server_down":
                self.command_timer.stop()
                self.animation.deactivate()
            elif cmd == "anim_v1":
                self.animation_mode = AnimationMode.V1
                self.animation.set_mode(self.animation_mode)
                self._save_version("v1")
            elif cmd == "anim_v2":
                self.animation_mode = AnimationMode.V2
                self.animation.set_mode(self.animation_mode)
                self._save_version("v2")
            elif cmd == "show":
                self.window.show()
            elif cmd == "hide":
                self.window.hide()
            elif cmd == "hide_message":
                self.message_popup.hide()
                self.message_popup.timer.stop()

        msg = None
        with self._message_lock:
            if self._pending_message is not None:
                msg = self._pending_message
                self._pending_message = None

        if msg is not None:
            message, permanent = msg
            duration = 999_999_999 if permanent else 4500
            self.message_popup.show_message(message, duration_ms=duration)

    def _save_version(self, version: str):
        try:
            with open(CONFIG_PATH, "w") as f:
                json.dump({ "avatarVersion": version }, f)
        except OSError as e:
            print(f"Failed to save config: {e}")

    def get_angry(self) -> None:
        self.is_angry = True
        self.animation.go_mad()

    def get_calm(self) -> None:
        if not self.is_angry:
            return
        self.is_angry = False
        self.animation.go_calm()

    def run(self) -> int:
        self.window.show()
        self.animation = AnimationController(
            self.window, self.base_dir, mode=self.animation_mode
        )
        self.window.interrupt_on_user_activity = (
            self.animation.interrupt_on_user_activity
        )
        self.window.resume_after_user_activity = (
            self.animation.resume_after_user_activity
        )
        return self.app.exec()


def main():
    app = QApplication(sys.argv)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("System tray is not available on this system.")
    mascot_app = MascotApp(app)

    sys.exit(mascot_app.run())


if __name__ == "__main__":
    main()