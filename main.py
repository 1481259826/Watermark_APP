# main.py
import sys, os, io
from pathlib import Path
# from tkinter import Image
from PIL import Image
from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel, QListWidget, QListWidgetItem,
    QHBoxLayout, QVBoxLayout, QFileDialog, QGraphicsView, QGraphicsScene,
    QGraphicsPixmapItem, QSlider, QLineEdit, QComboBox, QMessageBox, QSpinBox, QFontComboBox, QColorDialog, QCheckBox
)
from PySide6.QtGui import QPixmap, QImage, Qt, QColor, QFont
from PySide6.QtCore import QSize, QPointF, Signal, QObject, QThread

from core.image_io import is_image_file, generate_thumbnail, open_image_fix_orientation
from core.watermark import create_text_watermark_image
from core.exporter import compose_watermark_on_image
from core.templates import load_templates, save_templates

from PIL.ImageQt import ImageQt

APP_NAME = "WatermarkerPy - MVP"

# Helper: pil Image -> QPixmap
def pil_to_qpixmap(img):
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    qim = ImageQt(img)
    pix = QPixmap.fromImage(QImage(qim))
    return pix

# Worker thread for export to avoid blocking UI
class ExportWorker(QThread):
    progress = Signal(int, int, str)  # done, total, message
    finished_signal = Signal()

    def __init__(self, tasks):
        super().__init__()
        self.tasks = tasks

    def run(self):
        total = len(self.tasks)
        done = 0
        for t in self.tasks:
            try:
                compose_watermark_on_image(
                    t['src_path'],
                    t['dst_path'],
                    watermark_img=t['watermark_img'],
                    anchor=t.get('anchor', (0.5,0.5)),
                    output_format=t.get('output_format','png'),
                    jpeg_quality=t.get('jpeg_quality', 90),
                    resize_to=t.get('resize_to', None)
                )
                done += 1
                self.progress.emit(done, total, f"Saved: {t['dst_path']}")
            except Exception as e:
                self.progress.emit(done, total, f"Error ({os.path.basename(t['src_path'])}): {e}")
        self.finished_signal.emit()

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1100, 700)

        # model
        self.image_paths = []   # list of str
        self.current_index = None
        self.thumb_size = 180

        # left: thumbnail list
        self.list_widget = QListWidget()
        self.list_widget.setIconSize(QSize(self.thumb_size, self.thumb_size))
        self.list_widget.itemClicked.connect(self.on_thumb_clicked)

        import_btn = QPushButton("导入图片/文件夹")
        import_btn.clicked.connect(self.on_import)

        # center: preview (QGraphicsView)
        self.view = QGraphicsView()
        self.scene = QGraphicsScene()
        self.view.setScene(self.scene)
        self.base_item = None
        self.wm_item = None

        # right: controls
        self.text_input = QLineEdit("© 2025 MyBrand")

        # 字体文件选择
        self.font_btn = QPushButton("选择字体文件(.ttf)")
        self.font_btn.clicked.connect(self.select_font_file)
        self.font_path = "C:\\code\\Photo_Watermark2\\resources\\华文中宋.ttf"  # 默认字体

        # 字号
        self.fontsize_spin = QSpinBox()
        self.fontsize_spin.setRange(8, 512)
        self.fontsize_spin.setValue(64)

        # 粗体/斜体复选框
        self.bold_cb = QCheckBox("粗体")
        self.italic_cb = QCheckBox("斜体")

        # 文字阴影
        self.show_blur_spin = QSpinBox()
        self.show_blur_spin.setRange(1, 100)
        self.show_blur_spin.setValue(4)

        # 颜色选择
        self.font_color = QColor(255, 255, 255)  # 默认白色
        self.color_btn = QPushButton("选择颜色")
        self.color_btn.clicked.connect(self.choose_color)

        # 透明度
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(0,100)
        self.opacity_slider.setValue(60)

        # 旋转角度
        self.rotate_spin = QSlider(Qt.Horizontal)
        self.rotate_spin.setRange(0, 360)
        self.rotate_spin.setValue(0)

        # 位置
        self.pos_combo = QComboBox()
        self.pos_combo.addItems(["左上","正上","右上","左中","中心","右中","左下","正下","右下"])

        # 其他导出配置
        self.export_btn = QPushButton("导出所选并保存水印")
        self.export_btn.clicked.connect(self.on_export)
        self.output_dir_btn = QPushButton("选择输出文件夹")
        self.output_dir_btn.clicked.connect(self.select_output_dir)
        self.output_dir_label = QLabel("未选择")
        self.format_combo = QComboBox(); self.format_combo.addItems(["png","jpeg"])
        self.prefix_input = QLineEdit("")
        self.suffix_input = QLineEdit("_wm")

        # layout
        left_v = QVBoxLayout()
        left_v.addWidget(import_btn)
        left_v.addWidget(self.list_widget)

        right_v = QVBoxLayout()
        right_v.addWidget(QLabel("水印文本"))
        right_v.addWidget(self.text_input)

        right_v.addWidget(QLabel("字体"))
        right_v.addWidget(self.font_btn)

        right_v.addWidget(QLabel("字体大小"))
        right_v.addWidget(self.fontsize_spin)

        right_v.addWidget(self.bold_cb)   # 粗体按钮
        right_v.addWidget(self.italic_cb) # 斜体按钮

        right_v.addWidget(QLabel("文字阴影"))
        right_v.addWidget(self.show_blur_spin)

        right_v.addWidget(QLabel("字体颜色"))
        right_v.addWidget(self.color_btn)

        right_v.addWidget(QLabel("透明度"))
        right_v.addWidget(self.opacity_slider)

        right_v.addWidget(QLabel("旋转角度"))
        right_v.addWidget(self.rotate_spin)

        right_v.addWidget(QLabel("位置（九宫格）"))
        right_v.addWidget(self.pos_combo)

        right_v.addWidget(self.output_dir_btn)
        right_v.addWidget(self.output_dir_label)

        right_v.addWidget(QLabel("输出格式"))
        right_v.addWidget(self.format_combo)

        right_v.addWidget(QLabel("前缀"))
        right_v.addWidget(self.prefix_input)

        right_v.addWidget(QLabel("后缀"))
        right_v.addWidget(self.suffix_input)
        right_v.addWidget(self.export_btn)
        right_v.addStretch()

        main_h = QHBoxLayout(self)
        main_h.addLayout(left_v, 2)
        main_h.addWidget(self.view, 6)
        main_h.addLayout(right_v, 3)

        # signals / interactions
        self.text_input.textChanged.connect(self.update_preview_watermark)
        self.fontsize_spin.valueChanged.connect(self.update_preview_watermark)
        self.bold_cb.stateChanged.connect(self.update_preview_watermark)
        self.italic_cb.stateChanged.connect(self.update_preview_watermark)
        self.show_blur_spin.valueChanged.connect(self.update_preview_watermark)
        self.opacity_slider.valueChanged.connect(self.update_preview_watermark)
        self.rotate_spin.valueChanged.connect(self.update_preview_watermark)
        self.pos_combo.currentIndexChanged.connect(self.on_pos_changed)

        # output dir
        self.output_dir = None

        # load templates (not surfaced in UI now)
        self.templates = load_templates()

        # enable drag & drop for window
        self.setAcceptDrops(True)

    def select_font_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择字体文件", "", "Font Files (*.ttf *.otf)"
        )
        if path:
            self.font_path = path
            self.font_btn.setText(os.path.basename(path))
            self.update_preview_watermark()

    def choose_color(self):
        color = QColorDialog.getColor(self.font_color, self, "选择字体颜色")
        if color.isValid():
            self.font_color = color
            hex_code = color.name().upper()  # 转换成 #RRGGBB
            self.color_btn.setText(hex_code)
            # 设置按钮背景色
            self.color_btn.setStyleSheet(
                f"background-color: {hex_code}; color: black;"
            )
            self.update_preview_watermark()


    # drag & drop handling
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        paths = [u.toLocalFile() for u in urls]
        self.add_paths(paths)

    def on_import(self):
        dlg = QFileDialog(self, "选择图片或文件夹")
        dlg.setFileMode(QFileDialog.ExistingFiles)
        dlg.setNameFilters(["Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)"])
        if dlg.exec():
            files = dlg.selectedFiles()
            self.add_paths(files)

    def add_paths(self, paths):
        # if folder, iterate
        new = []
        for p in paths:
            p = Path(p)
            if p.is_dir():
                for f in p.rglob("*"):
                    if is_image_file(str(f)):
                        new.append(str(f))
            elif p.is_file() and is_image_file(str(p)):
                new.append(str(p))
        # append and unique
        for s in new:
            if s not in self.image_paths:
                self.image_paths.append(s)
                self.add_thumbnail_item(s)

    def add_thumbnail_item(self, path):
        thumb = generate_thumbnail(path, max_size=self.thumb_size)
        pix = pil_to_qpixmap(thumb)
        item = QListWidgetItem(Path(path).name)
        item.setData(Qt.UserRole, path)
        item.setIcon(pix)
        self.list_widget.addItem(item)

    def on_thumb_clicked(self, item):
        path = item.data(Qt.UserRole)
        idx = self.image_paths.index(path)
        self.current_index = idx
        self.show_preview(path)

    def show_preview(self, path):
        # clear scene
        self.scene.clear()
        img = generate_thumbnail(path, max_size=1200)
        self.current_preview_image = img  # PIL.Image
        pix = pil_to_qpixmap(img)
        self.base_item = QGraphicsPixmapItem(pix)
        self.base_item.setZValue(0)
        self.scene.addItem(self.base_item)

        # create watermark pixmap initial
        wm_pil = self.make_watermark_image_for_preview()
        wm_pix = pil_to_qpixmap(wm_pil)
        self.wm_item = QGraphicsPixmapItem(wm_pix)
        self.wm_item.setFlags(QGraphicsPixmapItem.ItemIsMovable | QGraphicsPixmapItem.ItemIsSelectable)
        self.wm_item.setZValue(1)
        # default pos: bottom-right
        bw = pix.width(); bh = pix.height()
        wmw = wm_pix.width(); wmh = wm_pix.height()
        self.scene.addItem(self.wm_item)
        self.wm_item.setPos(bw - wmw - 20, bh - wmh - 20)

        # fit view
        self.view.fitInView(self.scene.itemsBoundingRect(), Qt.KeepAspectRatio)

    def make_watermark_image_for_preview(self):
        text = self.text_input.text()
        font_size = self.fontsize_spin.value()
        opacity = self.opacity_slider.value() / 100.0
        # color white for now
        color = self.font_color.getRgb()
        bold = self.bold_cb.isChecked()
        italic = self.italic_cb.isChecked()
        shadow_blur = self.show_blur_spin.value() if self.show_blur_spin.value() > 0 else 0

        wm = create_text_watermark_image(
            text=text,
            font_path=self.font_path,  # can be None
            font_size=font_size,
            color=color,  # (r,g,b,a)
            opacity=opacity,
            stroke_width=0,
            stroke_fill=(0,0,0,255),
            shadow_blur=shadow_blur,
            bold=bold,
            italic=italic   
        )

        # 旋转角度
        angle = self.rotate_spin.value()
        if angle != 0:
            wm = wm.rotate(angle, expand=True, resample=Image.BICUBIC)
        
        return wm


    def update_preview_watermark(self):
        if not self.base_item or not self.wm_item:
            return
        wm_pil = self.make_watermark_image_for_preview()
        pix = pil_to_qpixmap(wm_pil)
        self.wm_item.setPixmap(pix)

    def on_pos_changed(self, idx):
        # 快捷位置：9宫格
        if not self.base_item or not self.wm_item:
            return
        base_rect = self.base_item.pixmap().rect()
        w = base_rect.width(); h = base_rect.height()
        wm_rect = self.wm_item.pixmap().rect()
        positions = {
            0: (10,10),
            1: ((w-wm_rect.width())//2, 10),
            2: (w-wm_rect.width()-10, 10),
            3: (10, (h-wm_rect.height())//2),
            4: ((w-wm_rect.width())//2, (h-wm_rect.height())//2),
            5: (w-wm_rect.width()-10, (h-wm_rect.height())//2),
            6: (10, h-wm_rect.height()-10),
            7: ((w-wm_rect.width())//2, h-wm_rect.height()-10),
            8: (w-wm_rect.width()-10, h-wm_rect.height()-10),
        }
        pos = positions.get(idx, (10,10))
        self.wm_item.setPos(pos[0], pos[1])

    def select_output_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择输出文件夹")
        if d:
            self.output_dir = d
            self.output_dir_label.setText(d)

    def on_export(self):
        if self.current_index is None:
            QMessageBox.warning(self, "提示", "请先选择一张图片")
            return
        if not self.output_dir:
            QMessageBox.warning(self, "提示", "请选择输出文件夹")
            return
        src = self.image_paths[self.current_index]
        # prevent exporting to same folder as source by default
        src_dir = str(Path(src).parent)
        if os.path.abspath(src_dir) == os.path.abspath(self.output_dir):
            QMessageBox.warning(self, "禁止", "默认禁止导出到原文件夹。请选择其他输出文件夹。")
            return

        # build watermark image at original scale
        # load original to get size
        orig = open_image_fix_orientation(src)
        iw, ih = orig.size

        # compute relative position of watermark center
        # get wm_item pos and size in preview coordinates, map to original by scale factor
        # we used thumbnails for preview; assume preview size equals base_item.pixmap size
        base_pix = self.base_item.pixmap()
        preview_w = base_pix.width(); preview_h = base_pix.height()
        wm_pix = self.wm_item.pixmap()
        wm_w = wm_pix.width(); wm_h = wm_pix.height()
        wm_pos = self.wm_item.pos()
        # center coordinates in preview
        center_x_preview = wm_pos.x() + wm_w/2
        center_y_preview = wm_pos.y() + wm_h/2
        # map to original
        anchor_x = center_x_preview / preview_w
        anchor_y = center_y_preview / preview_h
        anchor = (anchor_x, anchor_y)

        # create high-res watermark scaled to original image:
        # we want the watermark width on original to be similar proportional to preview:
        # scale_ratio = (iw / preview_w)
        scale_ratio = iw / preview_w
        font_size = int(self.fontsize_spin.value() * scale_ratio)
        if font_size < 8: font_size = 8

        wm_pil_high = create_text_watermark_image(
            text=self.text_input.text(),
            font_path=self.font_path,  # can be None
            font_size=font_size,
            color=self.font_color.getRgb(),
            opacity=self.opacity_slider.value()/100.0,
            stroke_width=0,
            shadow_blur=self.show_blur_spin.value() if self.show_blur_spin.value() > 0 else 0,
            bold=self.bold_cb.isChecked(),
            italic=self.italic_cb.isChecked()
        )

        # 旋转角度
        angle = self.rotate_spin.value()
        if angle != 0:
            wm_pil_high = wm_pil_high.rotate(angle, expand=True, resample=Image.BICUBIC)

        # no further resizing for now; could scale more precisely if needed

        # build dst path
        prefix = self.prefix_input.text() or ""
        suffix = self.suffix_input.text() or ""
        fmt = self.format_combo.currentText()
        src_name = Path(src).stem
        src_ext = ".png" if fmt == "png" else ".jpg"
        dst_name = f"{prefix}{src_name}{suffix}{src_ext}"
        dst_path = os.path.join(self.output_dir, dst_name)
        # avoid overwrite by appending index
        idx = 1
        base_dst = dst_path
        while os.path.exists(dst_path):
            dst_path = os.path.join(self.output_dir, f"{prefix}{src_name}{suffix}_{idx}{src_ext}")
            idx += 1

        # start export in worker
        task = {
            'src_path': src,
            'dst_path': dst_path,
            'watermark_img': wm_pil_high,
            'anchor': anchor,
            'output_format': fmt,
            'jpeg_quality': 90
        }
        self.export_btn.setEnabled(False)
        self.worker = ExportWorker([task])
        self.worker.progress.connect(self.on_export_progress)
        self.worker.finished_signal.connect(self.on_export_finished)
        self.worker.start()

    def on_export_progress(self, done, total, message):
        print(f"[{done}/{total}] {message}")

    def on_export_finished(self):
        self.export_btn.setEnabled(True)
        QMessageBox.information(self, "导出完成", "图片导出完成。")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())
