import sys
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QGuiApplication, QMouseEvent, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QWidget


class MascotWindow(QWidget):
    def __init__(self, image_path: str):
        super().__init__()

        self.image_path = image_path
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

        self.pixmap = QPixmap(image_path)
        if self.pixmap.isNull():
            raise FileNotFoundError(f"Could not load image: {image_path}")

        self.label.setPixmap(self.pixmap)
        self.resize(self.pixmap.size())
        self.label.resize(self.pixmap.size())

        self.alpha_image = Image.open(image_path).convert("RGBA")

    def is_opaque_at(self, pos: QPoint, alpha_threshold: int = 10) -> bool:
        x = pos.x()
        y = pos.y()

        if x < 0 or y < 0 or x >= self.alpha_image.width or y >= self.alpha_image.height:
            return False

        _, _, _, a = self.alpha_image.getpixel((x, y))
        return a > alpha_threshold

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            local_pos = event.position().toPoint()
            if self.is_opaque_at(local_pos):
                self.drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
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


def main():
    app = QApplication(sys.argv)

    image_path = Path(__file__).with_name("mascot.png")
    window = MascotWindow(str(image_path))

    screen = QGuiApplication.primaryScreen()
    if screen is not None:
        geometry = screen.availableGeometry()
        x = geometry.right() - window.width() - 40
        y = geometry.bottom() - window.height() - 40
        window.move(x, y)

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
