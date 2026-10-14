import sys
import os
import io

# Librerie QR
import qrcode
import segno
from segnomms import write as segno_write
from PIL import Image, ImageDraw

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QColorDialog,
    QFileDialog, QMessageBox, QGroupBox, QFormLayout, QCheckBox,
    QSpinBox, QSlider, QScrollArea
)
from PyQt6.QtGui import QPixmap, QColor
from PyQt6.QtCore import Qt, QTimer


class QRGeneratorBot(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QR Code Generator Bot")
        self.setGeometry(100, 100, 1150, 800)

        self.SCALE = 50

        self.bg_color = QColor(255, 255, 255)
        self.fg_color = QColor(0, 0, 0)
        self.bg_image_path = None
        self.logo_image_path = None
        self.generated_image = None

        self.preview_timer = QTimer()
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self.generate_qr)
        self.debounce_ms = 300

        self.init_ui()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout()
        central.setLayout(main_layout)

        left_panel = QScrollArea()
        left_panel.setWidgetResizable(True)
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_widget.setLayout(left_layout)
        left_panel.setWidget(left_widget)
        left_panel.setMinimumWidth(430)

        url_group = QGroupBox("Dati")
        url_form = QFormLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://esempio.com")
        self.url_input.textChanged.connect(self.schedule_preview)
        url_form.addRow("URL / Testo:", self.url_input)
        url_group.setLayout(url_form)
        left_layout.addWidget(url_group)

        color_group = QGroupBox("Colori")
        color_form = QFormLayout()
        self.fg_btn = QPushButton("Colore Moduli")
        self.fg_btn.clicked.connect(self.choose_fg_color)
        self.fg_btn.setStyleSheet(f"background-color: {self.fg_color.name()}; color: white;")
        color_form.addRow("Primo Piano:", self.fg_btn)

        self.bg_btn = QPushButton("Colore Sfondo")
        self.bg_btn.clicked.connect(self.choose_bg_color)
        self.bg_btn.setStyleSheet(f"background-color: {self.bg_color.name()}; color: black;")
        color_form.addRow("Sfondo:", self.bg_btn)
        color_group.setLayout(color_form)
        left_layout.addWidget(color_group)

        shape_group = QGroupBox("Forma Moduli (SegnoMMS)")
        shape_form = QFormLayout()

        self.shape_combo = QComboBox()
        self.shape_combo.addItems(["square", "circle", "rounded", "dot", "diamond", "hexagon", "star", "plus"])
        self.shape_combo.currentIndexChanged.connect(self.schedule_preview)
        shape_form.addRow("Forma:", self.shape_combo)

        shape_group.setLayout(shape_form)
        left_layout.addWidget(shape_group)

        size_group = QGroupBox("Dimensioni Output")
        size_form = QFormLayout()

        self.border_spin = QSpinBox()
        self.border_spin.setRange(0, 20)
        self.border_spin.setValue(4)
        self.border_spin.setSuffix(" moduli")
        self.border_spin.valueChanged.connect(self.schedule_preview)
        size_form.addRow("Bordo:", self.border_spin)

        size_group.setLayout(size_form)
        left_layout.addWidget(size_group)

        bg_img_group = QGroupBox("Sfondo Immagine")
        bg_img_layout = QVBoxLayout()
        self.use_bg_img = QCheckBox("Usa immagine di sfondo (al posto del colore)")
        self.use_bg_img.stateChanged.connect(self.toggle_bg_img)
        bg_img_layout.addWidget(self.use_bg_img)

        bg_row = QHBoxLayout()
        self.bg_img_btn = QPushButton("Seleziona Immagine")
        self.bg_img_btn.clicked.connect(self.select_bg_image)
        self.bg_img_btn.setEnabled(False)
        self.bg_img_label = QLabel("Nessuna")
        bg_row.addWidget(self.bg_img_btn)
        bg_row.addWidget(self.bg_img_label)
        bg_img_layout.addLayout(bg_row)

        bg_img_group.setLayout(bg_img_layout)
        left_layout.addWidget(bg_img_group)

        logo_group = QGroupBox("Logo Interno")
        logo_layout = QVBoxLayout()
        self.use_logo = QCheckBox("Inserisci logo al centro")
        self.use_logo.stateChanged.connect(self.toggle_logo)
        logo_layout.addWidget(self.use_logo)

        logo_row = QHBoxLayout()
        self.logo_btn = QPushButton("Seleziona Logo")
        self.logo_btn.clicked.connect(self.select_logo)
        self.logo_btn.setEnabled(False)
        self.logo_label = QLabel("Nessuno")
        logo_row.addWidget(self.logo_btn)
        logo_row.addWidget(self.logo_label)
        logo_layout.addLayout(logo_row)

        logo_size_layout = QHBoxLayout()
        logo_size_layout.addWidget(QLabel("Dimensione:"))
        self.logo_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.logo_size_slider.setRange(5, 40)
        self.logo_size_slider.setValue(20)
        self.logo_size_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.logo_size_slider.setTickInterval(5)
        self.logo_size_slider.valueChanged.connect(self.schedule_preview)
        self.logo_size_label = QLabel("20%")
        self.logo_size_slider.valueChanged.connect(
            lambda v: self.logo_size_label.setText(f"{v}%")
        )
        logo_size_layout.addWidget(self.logo_size_slider)
        logo_size_layout.addWidget(self.logo_size_label)
        logo_layout.addLayout(logo_size_layout)

        logo_group.setLayout(logo_layout)
        left_layout.addWidget(logo_group)

        left_layout.addStretch()
        main_layout.addWidget(left_panel)

        right_panel = QWidget()
        right_layout = QVBoxLayout()
        right_panel.setLayout(right_layout)

        self.preview_label = QLabel("L'anteprima apparirà qui")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("border: 2px dashed #aaa; background-color: #f5f5f5;")
        self.preview_label.setMinimumSize(500, 500)
        right_layout.addWidget(self.preview_label, stretch=1)

        self.save_btn = QPushButton("Salva come PNG")
        self.save_btn.clicked.connect(self.save_qr)
        self.save_btn.setEnabled(False)
        self.save_btn.setStyleSheet("font-size: 14px; padding: 8px;")
        right_layout.addWidget(self.save_btn)

        main_layout.addWidget(right_panel, stretch=1)

    def schedule_preview(self):
        self.preview_timer.start(self.debounce_ms)

    def toggle_bg_img(self, state):
        enabled = state == Qt.CheckState.Checked.value
        self.bg_img_btn.setEnabled(enabled)
        if not enabled:
            self.bg_image_path = None
            self.bg_img_label.setText("Nessuna")
        self.schedule_preview()

    def toggle_logo(self, state):
        enabled = state == Qt.CheckState.Checked.value
        self.logo_btn.setEnabled(enabled)
        if not enabled:
            self.logo_image_path = None
            self.logo_label.setText("Nessuno")
        self.schedule_preview()

    def choose_fg_color(self):
        color = QColorDialog.getColor(self.fg_color, self, "Colore Moduli")
        if color.isValid():
            self.fg_color = color
            self.fg_btn.setStyleSheet(
                f"background-color: {color.name()}; color: {'white' if color.lightness() < 128 else 'black'};"
            )
            self.schedule_preview()

    def choose_bg_color(self):
        color = QColorDialog.getColor(self.bg_color, self, "Colore Sfondo")
        if color.isValid():
            self.bg_color = color
            self.bg_btn.setStyleSheet(
                f"background-color: {color.name()}; color: {'white' if color.lightness() < 128 else 'black'};"
            )
            self.schedule_preview()

    def select_bg_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Immagine Sfondo", "",
            "Immagini (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if path:
            self.bg_image_path = path
            self.bg_img_label.setText(os.path.basename(path))
            self.schedule_preview()

    def select_logo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Logo", "", "Immagini (*.png *.jpg *.jpeg)"
        )
        if path:
            self.logo_image_path = path
            self.logo_label.setText(os.path.basename(path))
            self.schedule_preview()

    def generate_qr(self):
        url = self.url_input.text().strip()
        if not url:
            self.preview_label.setText("Inserisci un URL")
            self.generated_image = None
            self.save_btn.setEnabled(False)
            return

        try:
            self._generate_segno(url)
            self.save_btn.setEnabled(True)
        except Exception as e:
            self.preview_label.setText(f"Errore: {e}")
            self.generated_image = None
            self.save_btn.setEnabled(False)

    def _generate_segno(self, url):
        scale = self.SCALE
        border = self.border_spin.value()
        ec = 'h' if (self.use_logo.isChecked() and self.logo_image_path) else 'm'

        qr = segno.make(url, error=ec)
        modules_x, modules_y = qr.symbol_size(border=border)

        buf = io.BytesIO()
        segno_write(
            qr, buf, kind='svg',
            scale=1, border=border,
            shape=self.shape_combo.currentText(),
            dark=self.fg_color.name(),
            light='white',
        )
        svg_bytes = buf.getvalue()

        target_px = modules_x * scale

        import cairosvg
        png_data = cairosvg.svg2png(
            bytestring=svg_bytes,
            output_width=target_px,
            output_height=target_px,
        )
        qr_img = Image.open(io.BytesIO(png_data)).convert('RGB')

        fg_rgb = (self.fg_color.red(), self.fg_color.green(), self.fg_color.blue())
        qr_gray = qr_img.convert('L')
        mask = qr_gray.point(lambda x: 255 if x < 200 else 0)
        fg_layer = Image.new('RGB', qr_img.size, fg_rgb)

        if self.use_bg_img.isChecked() and self.bg_image_path:
            bg = Image.open(self.bg_image_path).convert('RGB').resize(
                qr_img.size, Image.Resampling.LANCZOS
            )
            qr_img = Image.composite(fg_layer, bg, mask)
        else:
            bg_rgb = (self.bg_color.red(), self.bg_color.green(), self.bg_color.blue())
            bg_layer = Image.new('RGB', qr_img.size, bg_rgb)
            qr_img = Image.composite(fg_layer, bg_layer, mask)

        if self.use_logo.isChecked() and self.logo_image_path:
            self._insert_logo(qr_img)

        self.generated_image = qr_img
        self._update_preview()

    def _insert_logo(self, qr_img):
        logo = Image.open(self.logo_image_path).convert('RGBA')
        qr_w, qr_h = qr_img.size

        logo_pct = self.logo_size_slider.value() / 100.0
        logo_size = int(qr_w * logo_pct)
        logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
        pos = ((qr_w - logo_size) // 2, (qr_h - logo_size) // 2)

        qr_img.paste(logo, pos, mask=logo)

    def _update_preview(self):
        if not self.generated_image:
            return
        temp = "temp_preview.png"
        self.generated_image.save(temp)
        pixmap = QPixmap(temp)
        scaled = pixmap.scaled(
            500, 500,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.preview_label.setPixmap(scaled)
        os.remove(temp)

    def save_qr(self):
        if not self.generated_image:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Salva QR", "qrcode.png", "PNG (*.png)"
        )
        if path:
            self.generated_image.save(path)
            QMessageBox.information(self, "Salvato", f"QR salvato in:\n{path}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = QRGeneratorBot()
    window.show()
    sys.exit(app.exec())
