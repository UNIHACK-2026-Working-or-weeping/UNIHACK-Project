import sys
import threading
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from pydantic import BaseModel
from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QAction, QGuiApplication, QIcon, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMenu,
    QSystemTrayIcon,
    QWidget,
)


class MascotWindow(QWidget):
    def __init__(self, image_path: str):
        super().__init__()

        self.drag_offset = QPoint()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)

        self.label = QLabel(self)
        self.label.setStyleSheet("background: transparent;")

        self.image_path: Path | None = None
        self.pixmap = QPixmap()
        self.alpha_image: Image.Image | None = None
        self.set_image(image_path)

    def set_image(self, image_path: str | Path) -> None:
        path = Path(image_path)
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            raise FileNotFoundError(f"Could not load image: {path}")

        self.image_path = path
        self.pixmap = pixmap
        self.label.setPixmap(self.pixmap)

        self.resize(self.pixmap.size())
        self.label.resize(self.pixmap.size())

        self.alpha_image = Image.open(path).convert("RGBA")

    def is_opaque_at(self, pos: QPoint, alpha_threshold: int = 10) -> bool:
        if self.alpha_image is None:
            return False

        x = pos.x()
        y = pos.y()

        if (
            x < 0
            or y < 0
            or x >= self.alpha_image.width
            or y >= self.alpha_image.height
        ):
            return False

        _, _, _, a = self.alpha_image.getpixel((x, y))
        return a > alpha_threshold

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            local_pos = event.position().toPoint()
            if self.is_opaque_at(local_pos):
                self.drag_offset = (
                    event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                )
                event.accept()
                return
        event.ignore()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            local_pos = event.position().toPoint()
            if self.is_opaque_at(local_pos):
                self.move(event.globalPosition().toPoint() - self.drag_offset)
                event.accept()
                return
        event.ignore()


class FastAPIController:
    def __init__(self, mascot_app: "MascotApp"):
        self.mascot_app = mascot_app
        self.app = FastAPI(title="Mascot Control API", version="1.0.0")

        self.app.add_middleware(
            CORSMiddleware,
            allow_origins="*",
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        self._configure_routes()

    def _configure_routes(self) -> None:
        class SetImageRequest(BaseModel):
            image: str

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
        @self.app.get("/image/teeth")
        def set_teeth():
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
