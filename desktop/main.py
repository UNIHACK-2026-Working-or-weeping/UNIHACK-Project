import queue
import sys
import threading
from dataclasses import dataclass
from enum import IntFlag, auto
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from pydantic import BaseModel
from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QAction, QGuiApplication, QIcon, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMenu,
    QSystemTrayIcon,
    QWidget,
)

try:
    from ai_inference import ensure_model_exists, getMessage

    ai_features_enabled = True
except ImportError:
    print("Llama.cpp not installed, disabled AI features")
    ai_features_enabled = False


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

        self.setMinimumSize(self.min_w, self.min_h)
        self.setMouseTracking(True)
        self.label.setMouseTracking(True)

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
        else:
            self._apply_aspect_resize_from_size(
                self.width(), self.height(), keep_center=True
            )

        self._update_scaled_label()

        self.alpha_image = Image.open(path).convert("RGBA")
        self._update_min_size_from_image()

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
        _, _, _, a = self.alpha_image.getpixel((x, y))
        return a > alpha_threshold

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
                event.accept()
                return

            if self.is_opaque_at(local_pos):
                self.drag_offset = (
                    event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                )
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

        if event.buttons() & Qt.MouseButton.LeftButton:
            if self.is_opaque_at(local_pos):
                self.move(event.globalPosition().toPoint() - self.drag_offset)
                event.accept()
                return
        else:
            region = self._hit_test_resize_region(local_pos)
            self.setCursor(self._cursor_for_region(region))

        event.ignore()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self._is_scaling:
                self._is_scaling = False
                self.setCursor(Qt.CursorShape.ArrowCursor)
                event.accept()
                return
            if self._is_resizing:
                self._is_resizing = False
                self._resize_region = ResizeRegion.NONE
                self.setCursor(Qt.CursorShape.ArrowCursor)
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


class FastAPIController:
    def __init__(self, mascot_app: "MascotApp"):
        self.mascot_app = mascot_app
        self.app = FastAPI(title="Mascot Control API", version="1.0.0")

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
                "using_teeth": self.mascot_app.using_teeth,
            }

        @self.app.post("/image/toggle")
        def toggle_image():
            self.mascot_app.request_toggle()
            return {"ok": True, "action": "toggle"}

        @self.app.post("/image/default")
        def set_default():
            self.mascot_app.request_set_named_image("default")
            return {"ok": True, "action": "set_default"}

        @self.app.post("/image/teeth")
        def set_teeth(payload: SetTeethRequest):
            if payload.domain:
                if ai_features_enabled:
                    print("Generic Passive Aggressive Quote goes herre")
                else:
                    print(getMessage(payload.domain))
            self.mascot_app.request_set_named_image("teeth")
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


class MascotApp:
    def __init__(self, app: QApplication):
        self.app = app
        self.base_dir = Path(__file__).parent
        self.default_image = self.base_dir / "mascot.png"
        self.teeth_image = self.base_dir / "mascot_1.png"
        self.using_teeth = False

        self.window = MascotWindow(str(self.default_image))
        self.window.resize(200, 200)
        self._position_window()

        self.tray = self._create_tray_icon()

        self._pending_command: str | None = None
        self._command_lock = threading.Lock()

        self.api = FastAPIController(self)
        self._start_api_server()

        self.command_timer = QTimer(self.window)
        self.command_timer.timeout.connect(self._process_pending_command)
        self.command_timer.start(100)

    def _position_window(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            geometry = screen.availableGeometry()
            x = geometry.right() - self.window.width() - 40
            y = geometry.bottom() - self.window.height() - 40
            self.window.move(x, y)

    def _create_tray_icon(self) -> QSystemTrayIcon:
        tray_icon = QSystemTrayIcon(self.app)
        icon = QIcon(str(self.default_image))
        if icon.isNull():
            icon = self.app.style().standardIcon(
                self.app.style().StandardPixmap.SP_ComputerIcon
            )
        tray_icon.setIcon(icon)
        tray_icon.setToolTip("Mascot App")

        menu = QMenu()

        self.swap_action = QAction("Swap to mascot_1.png", menu)
        self.swap_action.triggered.connect(self.toggle_image)
        menu.addAction(self.swap_action)

        menu.addSeparator()

        quit_action = QAction("Close App", menu)
        quit_action.triggered.connect(self.app.quit)
        menu.addAction(quit_action)

        tray_icon.setContextMenu(menu)
        tray_icon.show()
        return tray_icon

    def _start_api_server(self) -> None:
        config = uvicorn.Config(
            self.api.app,
            host="127.0.0.1",
            port=8000,
            log_level="info",
        )
        server = uvicorn.Server(config)

        self.api_thread = threading.Thread(
            target=server.run,
            daemon=True,
            name="fastapi-server-thread",
        )
        self.api_thread.start()

    def request_toggle(self) -> None:
        with self._command_lock:
            self._pending_command = "toggle"

    def request_set_named_image(self, image_name: str) -> None:
        with self._command_lock:
            self._pending_command = image_name

    def _process_pending_command(self) -> None:
        cmd = None
        with self._command_lock:
            if self._pending_command is not None:
                cmd = self._pending_command
                self._pending_command = None

        if cmd is None:
            return

        if cmd == "toggle":
            self.toggle_image()
        elif cmd == "default":
            if self.using_teeth:
                self.toggle_image()
        elif cmd == "teeth":
            if not self.using_teeth:
                self.toggle_image()

    def toggle_image(self) -> None:
        target = self.teeth_image if not self.using_teeth else self.default_image
        self.window.set_image(target)
        self.using_teeth = not self.using_teeth

        if self.using_teeth:
            self.swap_action.setText("Swap to mascot.png")
        else:
            self.swap_action.setText("Swap to mascot_1.png")

    def run(self) -> int:
        self.window.show()
        return self.app.exec()


def main():
    app = QApplication(sys.argv)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("System tray is not available on this system.")
    mascot_app = MascotApp(app)

    sys.exit(mascot_app.run())


if __name__ == "__main__":
    main()
