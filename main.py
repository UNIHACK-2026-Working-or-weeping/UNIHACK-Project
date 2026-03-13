import sys
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QPoint, Qt
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


class MascotApp:
    def __init__(self, app: QApplication):
        self.app = app
        self.base_dir = Path(__file__).parent
        self.default_image = self.base_dir / "mascot.png"
        self.teeth_image = self.base_dir / "mascot_teeth.png"
        self.using_teeth = False

        self.window = MascotWindow(str(self.default_image))
        self._position_window()

        self.tray = self._create_tray_icon()

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

        self.swap_action = QAction("Swap to mascot_teeth.png", menu)
        self.swap_action.triggered.connect(self.toggle_image)
        menu.addAction(self.swap_action)

        menu.addSeparator()

        quit_action = QAction("Close App", menu)
        quit_action.triggered.connect(self.app.quit)
        menu.addAction(quit_action)

        tray_icon.setContextMenu(menu)
        tray_icon.show()
        return tray_icon

    def toggle_image(self) -> None:
        target = self.teeth_image if not self.using_teeth else self.default_image
        self.window.set_image(target)
        self.using_teeth = not self.using_teeth

        if self.using_teeth:
            self.swap_action.setText("Swap to mascot.png")
        else:
            self.swap_action.setText("Swap to mascot_teeth.png")

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
