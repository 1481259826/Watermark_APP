# -*- coding: utf-8 -*-
"""
图片水印工具主程序
功能：为图片添加文字水印，支持批量处理、模板管理等功能
"""

# 标准库导入
import sys
import os
import io
from pathlib import Path

# 第三方库导入
from PIL import Image
from PIL.ImageQt import ImageQt
from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel, QListWidget, QListWidgetItem,
    QHBoxLayout, QVBoxLayout, QFileDialog, QGraphicsView, QGraphicsScene,
    QGraphicsPixmapItem, QSlider, QLineEdit, QComboBox, QMessageBox, QSpinBox, 
    QFontComboBox, QColorDialog, QCheckBox, QInputDialog, QGraphicsItem
)
from PySide6.QtGui import QPixmap, QImage, Qt, QColor, QFont
from PySide6.QtCore import QSize, QPointF, Signal, QObject, QThread

# 本地模块导入
from core.image_io import is_image_file, generate_thumbnail, open_image_fix_orientation
from core.watermark import create_text_watermark_image
from core.exporter import compose_watermark_on_image
from core.template_manager import TemplateManager

# 全局常量
APP_NAME = "WatermarkerPy - MVP"
SOURCE_DIR = "resources"  # 资源文件目录

def pil_to_qpixmap(img):
    """
    将PIL图像转换为Qt的QPixmap对象
    
    参数:
        img: PIL.Image对象
        
    返回:
        QPixmap: 转换后的QPixmap对象
    """
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    qim = ImageQt(img)
    pix = QPixmap.fromImage(QImage(qim))
    return pix

class ExportWorker(QThread):
    """
    导出工作线程类
    
    用于在后台处理图片水印添加任务，避免阻塞UI线程
    
    信号:
        progress: 发送处理进度信息 (已完成数量, 总数量, 消息)
        finished_signal: 任务完成时发送
    """
    progress = Signal(int, int, str)  # 已完成数量, 总数量, 消息
    finished_signal = Signal()

    def __init__(self, tasks):
        """
        初始化导出工作线程
        
        参数:
            tasks: 任务列表，每个任务为包含图片路径和水印参数的字典
        """
        super().__init__()
        self.tasks = tasks

    def run(self):
        """执行导出任务的主方法"""
        total = len(self.tasks)
        done = 0
        
        for task in self.tasks:
            try:
                # 为图片添加水印并保存
                compose_watermark_on_image(
                    task['src_path'],
                    task['dst_path'],
                    watermark_img=task['watermark_img'],
                    anchor=task.get('anchor', (0.5, 0.5)),
                    output_format=task.get('output_format', 'png'),
                    jpeg_quality=task.get('jpeg_quality', 90),
                    resize_to=task.get('resize_to', None)
                )
                done += 1
                self.progress.emit(done, total, f"已保存: {task['dst_path']}")
            except Exception as e:
                # 处理错误并发送错误信息
                self.progress.emit(done, total, f"错误 ({os.path.basename(task['src_path'])}): {e}")
        
        # 所有任务完成，发送完成信号
        self.finished_signal.emit()

class WatermarkItem(QGraphicsPixmapItem):
    """
    水印图形项类
    
    用于在图形场景中显示和操作水印图像
    """
    def __init__(self, main_window, *args, **kwargs):
        """
        初始化水印图形项
        
        参数:
            main_window: 主窗口实例，用于更新位置信息
        """
        super().__init__(*args, **kwargs)
        self.main_window = main_window

    def itemChange(self, change, value):
        """
        处理图形项变化事件
        
        当水印位置改变时，更新主窗口中的位置标签
        """
        if change == QGraphicsItem.ItemPositionHasChanged:
            x, y = int(value.x()), int(value.y())
            self.main_window.update_position_label((x, y))
        return super().itemChange(change, value)


class MainWindow(QWidget):
    """
    图片水印工具主窗口类
    
    负责处理用户界面交互、图片预览、水印编辑和导出功能
    包含图片缩略图列表、预览区域和水印参数控制面板
    """
    def __init__(self):
        """
        初始化主窗口
        
        设置窗口标题、大小，初始化模板管理器和数据模型
        创建并配置UI组件，包括缩略图列表、预览区和控制面板
        """
        super().__init__()
        self.setWindowTitle(APP_NAME)  # 设置窗口标题
        self.resize(1100, 700)  # 设置窗口大小
        self.template_manager = TemplateManager()  # 初始化模板管理器

        # 数据模型
        self.image_paths = []   # 图片路径列表
        self.current_index = None  # 当前选中的图片索引
        self.thumb_size = 180  # 缩略图大小

        # 左侧：缩略图列表
        self.list_widget = QListWidget()  # 创建列表控件
        self.list_widget.setIconSize(QSize(self.thumb_size, self.thumb_size))  # 设置图标大小
        self.list_widget.itemClicked.connect(self.on_thumb_clicked)  # 连接点击事件

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
        self.font_path = "resources/华文中宋.ttf"  # 默认字体

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
    
        # # 水印位置显示
        # self.position_label = QLabel("坐标: (0,0)")

        # 其他导出配置
        self.export_btn = QPushButton("导出所选并保存水印")
        self.export_btn.clicked.connect(self.on_export)
        self.output_dir_btn = QPushButton("选择输出文件夹")
        self.output_dir_btn.clicked.connect(self.select_output_dir)
        self.output_dir_label = QLabel("未选择")
        self.format_combo = QComboBox()
        self.format_combo.addItems(["png","jpeg"])
        self.prefix_input = QLineEdit("")
        self.suffix_input = QLineEdit("_wm")

        # 模板管理
        self.template_combo = QComboBox()
        self.template_combo.addItems(self.template_manager.templates.keys())
        self.template_combo.setCurrentText(self.template_manager.last_used)
        self.btn_load_template = QPushButton("加载模板")
        self.btn_save_template = QPushButton("保存当前为模板")
        self.btn_delete_template = QPushButton("删除模板")


        # layout
        left_v = QVBoxLayout()
        left_v.addWidget(import_btn)
        left_v.addWidget(self.list_widget)


        right_v = QVBoxLayout()

        # 模板管理
        right_v.addWidget(QLabel("水印模板"))
        right_v.addWidget(self.template_combo)
        right_v.addWidget(self.btn_load_template)
        right_v.addWidget(self.btn_save_template)
        right_v.addWidget(self.btn_delete_template)

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

        # right_v.addWidget(self.position_label)

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
        # 按钮绑定
        self.btn_load_template.clicked.connect(self.load_selected_template)
        self.btn_save_template.clicked.connect(self.save_current_as_template)
        self.btn_delete_template.clicked.connect(self.delete_selected_template)

        # output dir
        self.output_dir = None

        # enable drag & drop for window
        self.setAcceptDrops(True)

                # load templates (not surfaced in UI now)
        self.templates = self.template_manager.load_templates()

        # 加载上一次模板
        last_template = self.template_manager.last_used
        settings = self.template_manager.load_template(last_template)
        if settings:
            self.apply_template(settings)  # 载入到界面参数

    def save_current_as_template(self):
        """
        将当前水印设置保存为模板
        
        弹出对话框让用户输入模板名称，然后收集当前设置并保存
        """
        name, ok = QInputDialog.getText(self, "保存模板", "请输入模板名称：")
        if not ok or not name:
            return
        settings = self.collect_current_settings()
        self.template_manager.save_template(name, settings)
        self.template_combo.clear()
        self.template_combo.addItems(self.template_manager.templates.keys())
        self.template_combo.setCurrentText(name)
        QMessageBox.information(self, "成功", f"模板 '{name}' 已保存")

    def load_selected_template(self):
        """
        加载选中的水印模板
        
        从下拉框获取模板名称，加载对应设置并应用到界面
        """
        name = self.template_combo.currentText()
        settings = self.template_manager.load_template(name)
        if settings:
            self.apply_template(settings)
            QMessageBox.information(self, "成功", f"已加载模板 '{name}'")
        else:
            QMessageBox.warning(self, "错误", f"未找到模板 '{name}'")

    def delete_selected_template(self):
        """
        删除选中的水印模板
        
        从下拉框获取模板名称，删除对应模板（默认模板不可删除）
        """
        name = self.template_combo.currentText()
        if name == "默认模板":
            QMessageBox.warning(self, "提示", "不能删除默认模板")
            return
        self.template_manager.delete_template(name)
        self.template_combo.clear()
        self.template_combo.addItems(self.template_manager.templates.keys())
        self.template_combo.setCurrentText(self.template_manager.last_used)
        QMessageBox.information(self, "成功", f"模板 '{name}' 已删除")

    def collect_current_settings(self):
        """
        收集当前界面上的水印设置
        
        返回:
            dict: 包含所有水印参数的字典
        """
        return {
            "text": self.text_input.text(),  # 水印文本
            "font_path": self.font_btn.text(),  # 字体路径
            "font_size": self.fontsize_spin.value(),  # 字体大小
            "color": self.font_color.getRgb(),  # 字体颜色
            "position": self.pos_combo.currentText(),  # 位置
            "opacity": self.opacity_slider.value() / 100,  # 透明度
            "bold": self.bold_cb.isChecked(),  # 是否粗体
            "italic": self.italic_cb.isChecked(),  # 是否斜体
            "rotate": self.rotate_spin.value(),  # 旋转角度
            "show_blur": self.show_blur_spin.value(),  # 阴影模糊度
        }
    
    def apply_template(self, settings):
        """将模板应用到界面控件
        
        参数:
            settings: 包含水印参数的字典
        """
        self.text_input.setText(settings.get("text", ""))

        # 字体文件路径
        if hasattr(self, "font_btn"):
            path = settings.get("font_path", "")
            rel_path = os.path.join(SOURCE_DIR, path)
            self.font_btn.setText(path if path else "选择字体文件(.ttf)")
            self.font_path = rel_path  # 保存路径

        self.fontsize_spin.setValue(settings.get("font_size", 36))

        # 颜色
        if hasattr(self, "color_btn"):
            color = settings.get("color", [255, 255, 255, 200])
            # 格式化成 "R,G,B,A"
            color_text = f"{color[0]}, {color[1]}, {color[2]}, {color[3]}"
            self.color_btn.setText(color_text)
            self.font_color = QColor(*color[:3])  # 只用 RGB

        self.pos_combo.setCurrentText(settings.get("position", "右下"))
        self.opacity_slider.setValue(int(settings.get("opacity", 0.8) * 100))

        # 勾选框（粗体 / 斜体）
        if hasattr(self, "bold_cb"):
            self.bold_cb.setChecked(settings.get("bold", False))
        if hasattr(self, "italic_cb"):
            self.italic_cb.setChecked(settings.get("italic", False))

        # 旋转角度
        if hasattr(self, "rotate_spin"):
            self.rotate_spin.setValue(settings.get("rotate", 0))

        # 描边宽度 & 颜色
        if hasattr(self, "show_blur_spin"):
            self.show_blur_spin.setValue(settings.get("show_blur", 4))

        # 更新预览
        self.update_preview_watermark()

    def select_font_file(self):
        """选择字体文件
        
        打开文件对话框让用户选择TTF或OTF字体文件
        """
        path, _ = QFileDialog.getOpenFileName(
            self, "选择字体文件", "", "Font Files (*.ttf *.otf)"
        )
        if path:
            self.font_path = path
            self.font_btn.setText(os.path.basename(path))
            self.update_preview_watermark()

    def choose_color(self):
        """选择字体颜色
        
        打开颜色对话框让用户选择水印文字颜色
        """
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


    # 拖放处理相关方法
    def dragEnterEvent(self, event):
        """处理拖动进入事件
        
        当用户拖动文件到窗口时接受动作
        """
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        """处理文件拖放事件
        
        接收用户拖放的文件并添加到图片列表
        """
        urls = event.mimeData().urls()
        paths = [u.toLocalFile() for u in urls]
        self.add_paths(paths)

    def on_import(self):
        """导入图片按钮点击事件处理
        
        打开文件对话框让用户选择图片文件
        """
        dlg = QFileDialog(self, "选择图片或文件夹")
        dlg.setFileMode(QFileDialog.ExistingFiles)
        dlg.setNameFilters(["Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)"])
        if dlg.exec():
            files = dlg.selectedFiles()
            self.add_paths(files)

    def add_paths(self, paths):
        """添加图片路径到列表
        
        处理文件和文件夹，递归查找所有图片文件
        
        参数:
            paths: 文件或文件夹路径列表
        """
        # 如果是文件夹，遍历处理
        new = []
        for p in paths:
            p = Path(p)
            if p.is_dir():
                for f in p.rglob("*"):
                    if is_image_file(str(f)):
                        new.append(str(f))
            elif p.is_file() and is_image_file(str(p)):
                new.append(str(p))
        # 添加并去重
        for s in new:
            if s not in self.image_paths:
                self.image_paths.append(s)
                self.add_thumbnail_item(s)

    def add_thumbnail_item(self, path):
        """添加缩略图到列表控件
        
        参数:
            path: 图片文件路径
        """
        thumb = generate_thumbnail(path, max_size=self.thumb_size)
        pix = pil_to_qpixmap(thumb)
        item = QListWidgetItem(Path(path).name)
        item.setData(Qt.UserRole, path)
        item.setIcon(pix)
        self.list_widget.addItem(item)

    def on_thumb_clicked(self, item):
        """缩略图点击事件处理
        
        当用户点击左侧缩略图时，显示对应图片的预览
        
        参数:
            item: 被点击的列表项
        """
        path = item.data(Qt.UserRole)
        idx = self.image_paths.index(path)
        self.current_index = idx
        self.show_preview(path)

    def show_preview(self, path):
        """显示图片预览
        
        加载图片并在预览区域显示，同时添加水印图层
        
        参数:
            path: 图片文件路径
        """
        # 清空场景
        self.scene.clear()
        img = generate_thumbnail(path, max_size=1200)
        self.current_preview_image = img  # PIL.Image
        pix = pil_to_qpixmap(img)
        self.base_item = QGraphicsPixmapItem(pix)
        self.base_item.setZValue(0)
        self.scene.addItem(self.base_item)

        # 创建水印图层
        wm_pil = self.make_watermark_image_for_preview()
        wm_pix = pil_to_qpixmap(wm_pil)
        self.wm_item = QGraphicsPixmapItem(wm_pix)
        self.wm_item.setFlags(QGraphicsPixmapItem.ItemIsMovable | QGraphicsPixmapItem.ItemIsSelectable)
        self.wm_item.setZValue(1)
        # 默认位置：右下角
        bw = pix.width(); bh = pix.height()
        wmw = wm_pix.width(); wmh = wm_pix.height()
        self.scene.addItem(self.wm_item)
        self.wm_item.setPos(bw - wmw - 20, bh - wmh - 20)
        self.on_pos_changed(self.pos_combo.currentIndex())

        # 适应视图
        self.view.fitInView(self.scene.itemsBoundingRect(), Qt.KeepAspectRatio)

    def make_watermark_image_for_preview(self):
        """生成预览用的水印图像
        
        根据当前设置创建水印图像
        
        返回:
            PIL.Image: 生成的水印图像
        """
        text = self.text_input.text()
        font_size = self.fontsize_spin.value()
        opacity = self.opacity_slider.value() / 100.0
        color = self.font_color.getRgb()
        bold = self.bold_cb.isChecked()
        italic = self.italic_cb.isChecked()
        shadow_blur = self.show_blur_spin.value() if self.show_blur_spin.value() > 0 else 0

        wm = create_text_watermark_image(
            text=text,
            font_path=self.font_path,  # 可以为None
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
        """更新预览中的水印图像
        
        根据当前设置重新生成水印并更新预览
        """
        if not self.base_item or not self.wm_item:
            return
        wm_pil = self.make_watermark_image_for_preview()
        pix = pil_to_qpixmap(wm_pil)
        self.wm_item.setPixmap(pix)

    def on_pos_changed(self, idx):
        """处理位置选择变化
        
        根据九宫格位置设置水印在图片中的位置
        
        参数:
            idx: 位置索引（0-8对应九宫格位置）
        """
        # 快捷位置：9宫格
        if not self.base_item or not self.wm_item:
            return
        base_rect = self.base_item.pixmap().rect()
        w = base_rect.width(); h = base_rect.height()
        wm_rect = self.wm_item.pixmap().rect()
        positions = {
            0: (10,10),  # 左上
            1: ((w-wm_rect.width())//2, 10),  # 正上
            2: (w-wm_rect.width()-10, 10),  # 右上
            3: (10, (h-wm_rect.height())//2),  # 左中
            4: ((w-wm_rect.width())//2, (h-wm_rect.height())//2),  # 中心
            5: (w-wm_rect.width()-10, (h-wm_rect.height())//2),  # 右中
            6: (10, h-wm_rect.height()-10),  # 左下
            7: ((w-wm_rect.width())//2, h-wm_rect.height()-10),  # 正下
            8: (w-wm_rect.width()-10, h-wm_rect.height()-10),  # 右下
        }
        pos = positions.get(idx, (10,10))
        self.wm_item.setPos(pos[0], pos[1])

    def select_output_dir(self):
        """选择输出文件夹
        
        打开文件夹选择对话框让用户选择水印图片的保存位置
        """
        d = QFileDialog.getExistingDirectory(self, "选择输出文件夹")
        if d:
            self.output_dir = d
            self.output_dir_label.setText(d)

    def on_export(self):
        """导出水印图片
        
        处理导出按钮点击事件，将水印添加到原图并保存
        """
        if self.current_index is None:
            QMessageBox.warning(self, "提示", "请先选择一张图片")
            return
        if not self.output_dir:
            QMessageBox.warning(self, "提示", "请选择输出文件夹")
            return
        src = self.image_paths[self.current_index]
        # 默认禁止导出到原图所在文件夹
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
