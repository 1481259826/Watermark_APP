# -*- coding: utf-8 -*-
"""
图片水印工具主程序
功能:为图片添加文字水印,支持批量处理、模板管理等功能
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
    QFontComboBox, QColorDialog, QCheckBox, QInputDialog, QGraphicsItem,
    QGroupBox, QFrame, QScrollArea, QSplitter
)
from PySide6.QtGui import QPixmap, QImage, Qt, QColor, QFont, QPalette
from PySide6.QtCore import QSize, QPointF, Signal, QObject, QThread

# 本地模块导入
from core.image_io import is_image_file, generate_thumbnail, open_image_fix_orientation
from core.watermark import create_text_watermark_image
from core.exporter import compose_watermark_on_image
from core.template_manager import TemplateManager

# 全局常量
APP_NAME = "WatermarkerPy - 图片水印工具"
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
    
    用于在后台处理图片水印添加任务,避免阻塞UI线程
    
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
            tasks: 任务列表,每个任务为包含图片路径和水印参数的字典
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
        
        # 所有任务完成,发送完成信号
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
            main_window: 主窗口实例,用于更新位置信息
        """
        super().__init__(*args, **kwargs)
        self.main_window = main_window

    def itemChange(self, change, value):
        """
        处理图形项变化事件
        
        当水印位置改变时,更新主窗口中的位置标签
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
        
        设置窗口标题、大小,初始化模板管理器和数据模型
        创建并配置UI组件,包括缩略图列表、预览区和控制面板
        """
        super().__init__()
        self.setWindowTitle(APP_NAME)  # 设置窗口标题
        self.resize(1400, 800)  # 增大窗口尺寸
        self.template_manager = TemplateManager()  # 初始化模板管理器

        # 设置应用样式
        self.setup_styles()

        # 数据模型
        self.image_paths = []   # 图片路径列表
        self.current_index = None  # 当前选中的图片索引
        self.thumb_size = 180  # 缩略图大小

        # 创建主布局
        self.setup_ui()

        # output dir
        self.output_dir = None

        # enable drag & drop for window
        self.setAcceptDrops(True)

        # load templates
        self.templates = self.template_manager.load_templates()

        # 加载上一次模板
        last_template = self.template_manager.last_used
        settings = self.template_manager.load_template(last_template)
        if settings:
            self.apply_template(settings)  # 载入到界面参数

    def setup_styles(self):
        """设置应用程序的全局样式"""
        style = """
            QWidget {
                font-family: "Microsoft YaHei UI", "Segoe UI", Arial;
                font-size: 9pt;
            }
            
            QGroupBox {
                font-weight: bold;
                border: 2px solid #d0d0d0;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 8px;
                background-color: #fafafa;
            }
            
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 4px 10px;
                background-color: white;
                border-radius: 4px;
                color: #2c3e50;
            }
            
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            
            QPushButton:hover {
                background-color: #2980b9;
            }
            
            QPushButton:pressed {
                background-color: #21618c;
            }
            
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
            
            QPushButton#secondaryButton {
                background-color: #95a5a6;
            }
            
            QPushButton#secondaryButton:hover {
                background-color: #7f8c8d;
            }
            
            QPushButton#dangerButton {
                background-color: #e74c3c;
            }
            
            QPushButton#dangerButton:hover {
                background-color: #c0392b;
            }
            
            QPushButton#successButton {
                background-color: #27ae60;
            }
            
            QPushButton#successButton:hover {
                background-color: #229954;
            }
            
            QLineEdit, QSpinBox, QComboBox {
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                padding: 6px;
                background-color: white;
            }
            
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
                border: 2px solid #3498db;
            }
            
            QSlider::groove:horizontal {
                border: 1px solid #bdc3c7;
                height: 6px;
                background: #ecf0f1;
                border-radius: 3px;
            }
            
            QSlider::handle:horizontal {
                background: #3498db;
                border: 1px solid #2980b9;
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }
            
            QSlider::handle:horizontal:hover {
                background: #2980b9;
            }
            
            QListWidget {
                border: 1px solid #bdc3c7;
                border-radius: 6px;
                background-color: white;
                padding: 4px;
            }
            
            QListWidget::item {
                border-radius: 4px;
                padding: 4px;
            }
            
            QListWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
            
            QListWidget::item:hover {
                background-color: #ecf0f1;
            }
            
            QCheckBox {
                spacing: 8px;
            }
            
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 3px;
                border: 2px solid #bdc3c7;
            }
            
            QCheckBox::indicator:checked {
                background-color: #3498db;
                border-color: #2980b9;
            }
            
            QLabel {
                color: #2c3e50;
            }
            
            QGraphicsView {
                border: 2px solid #bdc3c7;
                border-radius: 6px;
                background-color: #ecf0f1;
            }
        """
        self.setStyleSheet(style)

    def setup_ui(self):
        """设置用户界面布局"""
        # 主布局使用分割器
        main_splitter = QSplitter(Qt.Horizontal)
        
        # === 左侧面板 ===
        left_panel = self.create_left_panel()
        
        # === 中央预览区 ===
        center_panel = self.create_center_panel()
        
        # === 右侧控制面板 ===
        right_panel = self.create_right_panel()
        
        # 添加到分割器
        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(center_panel)
        main_splitter.addWidget(right_panel)
        
        # 设置分割比例
        main_splitter.setStretchFactor(0, 2)  # 左侧
        main_splitter.setStretchFactor(1, 5)  # 中央
        main_splitter.setStretchFactor(2, 3)  # 右侧
        
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(main_splitter)
        main_layout.setContentsMargins(10, 10, 10, 10)

    def create_left_panel(self):
        """创建左侧图片列表面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(10)
        
        # 标题
        title = QLabel("📁 图片列表")
        title.setStyleSheet("font-size: 12pt; font-weight: bold; color: #2c3e50;")
        layout.addWidget(title)
        
        # 导入按钮
        import_btn = QPushButton("➕ 导入图片/文件夹")
        import_btn.setObjectName("successButton")
        import_btn.setMinimumHeight(40)
        import_btn.clicked.connect(self.on_import)
        layout.addWidget(import_btn)
        
        # 缩略图列表
        self.list_widget = QListWidget()
        self.list_widget.setIconSize(QSize(self.thumb_size, self.thumb_size))
        self.list_widget.itemClicked.connect(self.on_thumb_clicked)
        layout.addWidget(self.list_widget)
        
        return panel

    def create_center_panel(self):
        """创建中央预览面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(10)
        
        # 标题
        title = QLabel("🖼️ 预览区域")
        title.setStyleSheet("font-size: 12pt; font-weight: bold; color: #2c3e50;")
        layout.addWidget(title)
        
        # 预览视图
        self.view = QGraphicsView()
        self.scene = QGraphicsScene()
        self.view.setScene(self.scene)
        self.base_item = None
        self.wm_item = None
        layout.addWidget(self.view)
        
        # 提示文本
        hint = QLabel("💡 提示: 拖拽文件到窗口可直接导入 | 水印可在预览区拖动调整位置")
        hint.setStyleSheet("color: #7f8c8d; font-size: 8pt; padding: 5px;")
        hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint)
        
        # 外观设置组
        appearance_group = self.create_appearance_group()
        layout.addWidget(appearance_group)
        
        return panel

    def create_right_panel(self):
        """创建右侧控制面板"""
        panel = QWidget()
        scroll = QScrollArea()
        scroll.setWidget(panel)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        layout = QVBoxLayout(panel)
        layout.setSpacing(15)
        
        # 模板管理组
        template_group = self.create_template_group()
        layout.addWidget(template_group)
        
        # 水印文本组
        text_group = self.create_text_group()
        layout.addWidget(text_group)
        
        # 字体设置组
        font_group = self.create_font_group()
        layout.addWidget(font_group)
        
        # # 外观设置组
        # appearance_group = self.create_appearance_group()
        # layout.addWidget(appearance_group)
        
        # 位置设置组
        position_group = self.create_position_group()
        layout.addWidget(position_group)
        
        # 导出设置组
        export_group = self.create_export_group()
        layout.addWidget(export_group)
        
        layout.addStretch()
        
        return scroll

    def create_template_group(self):
        """创建模板管理组"""
        group = QGroupBox("💾 水印模板")
        layout = QVBoxLayout()
        layout.setSpacing(8)
        
        self.template_combo = QComboBox()
        self.template_combo.addItems(self.template_manager.templates.keys())
        self.template_combo.setCurrentText(self.template_manager.last_used)
        layout.addWidget(self.template_combo)
        
        btn_layout = QHBoxLayout()
        
        self.btn_load_template = QPushButton("📂 加载")
        self.btn_load_template.setObjectName("secondaryButton")
        self.btn_load_template.clicked.connect(self.load_selected_template)
        btn_layout.addWidget(self.btn_load_template)
        
        self.btn_save_template = QPushButton("💾 保存")
        self.btn_save_template.clicked.connect(self.save_current_as_template)
        btn_layout.addWidget(self.btn_save_template)
        
        self.btn_delete_template = QPushButton("🗑️ 删除")
        self.btn_delete_template.setObjectName("dangerButton")
        self.btn_delete_template.clicked.connect(self.delete_selected_template)
        btn_layout.addWidget(self.btn_delete_template)
        
        layout.addLayout(btn_layout)
        group.setLayout(layout)
        return group

    def create_text_group(self):
        """创建水印文本组"""
        group = QGroupBox("✏️ 水印内容")
        layout = QVBoxLayout()
        layout.setSpacing(8)
        
        self.text_input = QLineEdit("© 2025 MyBrand")
        self.text_input.setPlaceholderText("输入水印文字...")
        self.text_input.textChanged.connect(self.update_preview_watermark)
        layout.addWidget(self.text_input)
        
        group.setLayout(layout)
        return group

    def create_font_group(self):
        """创建字体设置组"""
        group = QGroupBox("🔤 字体设置")
        layout = QVBoxLayout()
        layout.setSpacing(8)
        
        # 字体文件
        self.font_btn = QPushButton("📁 选择字体文件 (.ttf)")
        self.font_btn.setObjectName("secondaryButton")
        self.font_btn.clicked.connect(self.select_font_file)
        self.font_path = "resources/华文中宋.ttf"
        layout.addWidget(self.font_btn)
        
        # 字号
        font_size_layout = QHBoxLayout()
        font_size_layout.addWidget(QLabel("字号:"))
        self.fontsize_spin = QSpinBox()
        self.fontsize_spin.setRange(8, 512)
        self.fontsize_spin.setValue(64)
        self.fontsize_spin.valueChanged.connect(self.update_preview_watermark)
        font_size_layout.addWidget(self.fontsize_spin)
        layout.addLayout(font_size_layout)
        
        # 粗体/斜体
        style_layout = QHBoxLayout()
        self.bold_cb = QCheckBox("粗体")
        self.bold_cb.stateChanged.connect(self.update_preview_watermark)
        style_layout.addWidget(self.bold_cb)
        
        self.italic_cb = QCheckBox("斜体")
        self.italic_cb.stateChanged.connect(self.update_preview_watermark)
        style_layout.addWidget(self.italic_cb)
        layout.addLayout(style_layout)
        
        group.setLayout(layout)
        return group

    def create_appearance_group(self):
        """创建外观设置组"""
        group = QGroupBox("🎨 外观设置")
        layout = QVBoxLayout()
        layout.setSpacing(12)
        
        # 颜色
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("颜色:"))
        self.font_color = QColor(255, 255, 255)
        self.color_btn = QPushButton("选择颜色")
        self.color_btn.clicked.connect(self.choose_color)
        color_layout.addWidget(self.color_btn)
        layout.addLayout(color_layout)
        
        # 透明度
        opacity_label = QLabel("透明度: 60%")
        layout.addWidget(opacity_label)
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(60)
        self.opacity_slider.valueChanged.connect(
            lambda v: opacity_label.setText(f"透明度: {v}%")
        )
        self.opacity_slider.valueChanged.connect(self.update_preview_watermark)
        layout.addWidget(self.opacity_slider)
        
        # 旋转角度
        rotate_label = QLabel("旋转角度: 0°")
        layout.addWidget(rotate_label)
        self.rotate_spin = QSlider(Qt.Horizontal)
        self.rotate_spin.setRange(0, 360)
        self.rotate_spin.setValue(0)
        self.rotate_spin.valueChanged.connect(
            lambda v: rotate_label.setText(f"旋转角度: {v}°")
        )
        self.rotate_spin.valueChanged.connect(self.update_preview_watermark)
        layout.addWidget(self.rotate_spin)
        
        # 阴影
        shadow_layout = QHBoxLayout()
        shadow_layout.addWidget(QLabel("阴影:"))
        self.show_blur_spin = QSpinBox()
        self.show_blur_spin.setRange(0, 100)
        self.show_blur_spin.setValue(4)
        self.show_blur_spin.valueChanged.connect(self.update_preview_watermark)
        shadow_layout.addWidget(self.show_blur_spin)
        layout.addLayout(shadow_layout)
        
        group.setLayout(layout)
        return group

    def create_position_group(self):
        """创建位置设置组"""
        group = QGroupBox("📍 位置设置")
        layout = QVBoxLayout()
        layout.setSpacing(8)
        
        layout.addWidget(QLabel("九宫格位置:"))
        self.pos_combo = QComboBox()
        self.pos_combo.addItems([
            "左上", "正上", "右上",
            "左中", "中心", "右中",
            "左下", "正下", "右下"
        ])
        self.pos_combo.currentIndexChanged.connect(self.on_pos_changed)
        layout.addWidget(self.pos_combo)
        
        hint = QLabel("💡 也可在预览区直接拖动水印")
        hint.setStyleSheet("color: #7f8c8d; font-size: 8pt;")
        layout.addWidget(hint)
        
        group.setLayout(layout)
        return group

    def create_export_group(self):
        """创建导出设置组"""
        group = QGroupBox("💾 导出设置")
        layout = QVBoxLayout()
        layout.setSpacing(8)
        
        # 输出文件夹
        self.output_dir_btn = QPushButton("📁 选择输出文件夹")
        self.output_dir_btn.setObjectName("secondaryButton")
        self.output_dir_btn.clicked.connect(self.select_output_dir)
        layout.addWidget(self.output_dir_btn)
        
        self.output_dir_label = QLabel("未选择")
        self.output_dir_label.setStyleSheet("color: #7f8c8d; padding: 5px;")
        self.output_dir_label.setWordWrap(True)
        layout.addWidget(self.output_dir_label)
        
        # 格式
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("格式:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["png", "jpeg"])
        format_layout.addWidget(self.format_combo)
        layout.addLayout(format_layout)
        
        # 前缀
        prefix_layout = QHBoxLayout()
        prefix_layout.addWidget(QLabel("前缀:"))
        self.prefix_input = QLineEdit("")
        self.prefix_input.setPlaceholderText("可选")
        prefix_layout.addWidget(self.prefix_input)
        layout.addLayout(prefix_layout)
        
        # 后缀
        suffix_layout = QHBoxLayout()
        suffix_layout.addWidget(QLabel("后缀:"))
        self.suffix_input = QLineEdit("_wm")
        suffix_layout.addWidget(self.suffix_input)
        layout.addLayout(suffix_layout)
        
        # 导出按钮
        self.export_btn = QPushButton("✅ 导出所选并保存水印")
        self.export_btn.setObjectName("successButton")
        self.export_btn.setMinimumHeight(40)
        self.export_btn.clicked.connect(self.on_export)
        layout.addWidget(self.export_btn)
        
        group.setLayout(layout)
        return group

    def update_position_label(self, pos):
        """更新位置标签(保留接口兼容性)"""
        pass

    def save_current_as_template(self):
        """将当前水印设置保存为模板"""
        name, ok = QInputDialog.getText(self, "保存模板", "请输入模板名称:")
        if not ok or not name:
            return
        settings = self.collect_current_settings()
        self.template_manager.save_template(name, settings)
        self.template_combo.clear()
        self.template_combo.addItems(self.template_manager.templates.keys())
        self.template_combo.setCurrentText(name)
        QMessageBox.information(self, "成功", f"模板 '{name}' 已保存")

    def load_selected_template(self):
        """加载选中的水印模板"""
        name = self.template_combo.currentText()
        settings = self.template_manager.load_template(name)
        if settings:
            self.apply_template(settings)
            QMessageBox.information(self, "成功", f"已加载模板 '{name}'")
        else:
            QMessageBox.warning(self, "错误", f"未找到模板 '{name}'")

    def delete_selected_template(self):
        """删除选中的水印模板"""
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
        """收集当前界面上的水印设置"""
        return {
            "text": self.text_input.text(),
            "font_path": self.font_btn.text(),
            "font_size": self.fontsize_spin.value(),
            "color": self.font_color.getRgb(),
            "position": self.pos_combo.currentText(),
            "opacity": self.opacity_slider.value() / 100,
            "bold": self.bold_cb.isChecked(),
            "italic": self.italic_cb.isChecked(),
            "rotate": self.rotate_spin.value(),
            "show_blur": self.show_blur_spin.value(),
        }
    
    def apply_template(self, settings):
        """将模板应用到界面控件"""
        self.text_input.setText(settings.get("text", ""))

        if hasattr(self, "font_btn"):
            path = settings.get("font_path", "")
            rel_path = os.path.join(SOURCE_DIR, path)
            self.font_btn.setText(path if path else "选择字体文件(.ttf)")
            self.font_path = rel_path

        self.fontsize_spin.setValue(settings.get("font_size", 36))

        if hasattr(self, "color_btn"):
            color = settings.get("color", [255, 255, 255, 200])
            color_text = f"{color[0]}, {color[1]}, {color[2]}, {color[3]}"
            self.color_btn.setText(color_text)
            self.font_color = QColor(*color[:3])

        self.pos_combo.setCurrentText(settings.get("position", "右下"))
        self.opacity_slider.setValue(int(settings.get("opacity", 0.8) * 100))

        if hasattr(self, "bold_cb"):
            self.bold_cb.setChecked(settings.get("bold", False))
        if hasattr(self, "italic_cb"):
            self.italic_cb.setChecked(settings.get("italic", False))

        if hasattr(self, "rotate_spin"):
            self.rotate_spin.setValue(settings.get("rotate", 0))

        if hasattr(self, "show_blur_spin"):
            self.show_blur_spin.setValue(settings.get("show_blur", 4))

        self.update_preview_watermark()

    def select_font_file(self):
        """选择字体文件"""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择字体文件", "", "Font Files (*.ttf *.otf)"
        )
        if path:
            self.font_path = path
            self.font_btn.setText(os.path.basename(path))
            self.update_preview_watermark()

    def choose_color(self):
        """选择字体颜色"""
        color = QColorDialog.getColor(self.font_color, self, "选择字体颜色")
        if color.isValid():
            self.font_color = color
            hex_code = color.name().upper()
            self.color_btn.setText(hex_code)
            self.color_btn.setStyleSheet(
                f"background-color: {hex_code}; color: {'white' if color.lightness() < 128 else 'black'}; font-weight: bold; border-radius: 4px; padding: 8px;"
            )
            self.update_preview_watermark()

    def dragEnterEvent(self, event):
        """处理拖动进入事件"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        """处理文件拖放事件"""
        urls = event.mimeData().urls()
        paths = [u.toLocalFile() for u in urls]
        self.add_paths(paths)

    def on_import(self):
        """导入图片按钮点击事件处理"""
        dlg = QFileDialog(self, "选择图片或文件夹")
        dlg.setFileMode(QFileDialog.ExistingFiles)
        dlg.setNameFilters(["Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)"])
        if dlg.exec():
            files = dlg.selectedFiles()
            self.add_paths(files)

    def add_paths(self, paths):
        """添加图片路径到列表"""
        new = []
        for p in paths:
            p = Path(p)
            if p.is_dir():
                for f in p.rglob("*"):
                    if is_image_file(str(f)):
                        new.append(str(f))
            elif p.is_file() and is_image_file(str(p)):
                new.append(str(p))
        
        for s in new:
            if s not in self.image_paths:
                self.image_paths.append(s)
                self.add_thumbnail_item(s)

    def add_thumbnail_item(self, path):
        """添加缩略图到列表控件"""
        thumb = generate_thumbnail(path, max_size=self.thumb_size)
        pix = pil_to_qpixmap(thumb)
        item = QListWidgetItem(Path(path).name)
        item.setData(Qt.UserRole, path)
        item.setIcon(pix)
        self.list_widget.addItem(item)

    def on_thumb_clicked(self, item):
        """缩略图点击事件处理"""
        path = item.data(Qt.UserRole)
        idx = self.image_paths.index(path)
        self.current_index = idx
        self.show_preview(path)

    def show_preview(self, path):
        """显示图片预览"""
        self.scene.clear()
        img = generate_thumbnail(path, max_size=1200)
        self.current_preview_image = img
        pix = pil_to_qpixmap(img)
        self.base_item = QGraphicsPixmapItem(pix)
        self.base_item.setZValue(0)
        self.scene.addItem(self.base_item)

        wm_pil = self.make_watermark_image_for_preview()
        wm_pix = pil_to_qpixmap(wm_pil)
        self.wm_item = QGraphicsPixmapItem(wm_pix)
        self.wm_item.setFlags(QGraphicsPixmapItem.ItemIsMovable | QGraphicsPixmapItem.ItemIsSelectable)
        self.wm_item.setZValue(1)
        bw = pix.width(); bh = pix.height()
        wmw = wm_pix.width(); wmh = wm_pix.height()
        self.scene.addItem(self.wm_item)
        self.wm_item.setPos(bw - wmw - 20, bh - wmh - 20)
        self.on_pos_changed(self.pos_combo.currentIndex())

        self.view.fitInView(self.scene.itemsBoundingRect(), Qt.KeepAspectRatio)

    def make_watermark_image_for_preview(self):
        """生成预览用的水印图像"""
        text = self.text_input.text()
        font_size = self.fontsize_spin.value()
        opacity = self.opacity_slider.value() / 100.0
        color = self.font_color.getRgb()
        bold = self.bold_cb.isChecked()
        italic = self.italic_cb.isChecked()
        shadow_blur = self.show_blur_spin.value() if self.show_blur_spin.value() > 0 else 0

        wm = create_text_watermark_image(
            text=text,
            font_path=self.font_path,
            font_size=font_size,
            color=color,
            opacity=opacity,
            stroke_width=0,
            stroke_fill=(0,0,0,255),
            shadow_blur=shadow_blur,
            bold=bold,
            italic=italic   
        )

        angle = self.rotate_spin.value()
        if angle != 0:
            wm = wm.rotate(angle, expand=True, resample=Image.BICUBIC)
        
        return wm

    def update_preview_watermark(self):
        """更新预览中的水印图像"""
        if not self.base_item or not self.wm_item:
            return
        wm_pil = self.make_watermark_image_for_preview()
        pix = pil_to_qpixmap(wm_pil)
        self.wm_item.setPixmap(pix)

    def on_pos_changed(self, idx):
        """处理位置选择变化"""
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
        """选择输出文件夹"""
        d = QFileDialog.getExistingDirectory(self, "选择输出文件夹")
        if d:
            self.output_dir = d
            self.output_dir_label.setText(d)

    def on_export(self):
        """导出水印图片"""
        if self.current_index is None:
            QMessageBox.warning(self, "提示", "请先选择一张图片")
            return
        if not self.output_dir:
            QMessageBox.warning(self, "提示", "请选择输出文件夹")
            return
        src = self.image_paths[self.current_index]
        src_dir = str(Path(src).parent)
        if os.path.abspath(src_dir) == os.path.abspath(self.output_dir):
            QMessageBox.warning(self, "禁止", "默认禁止导出到原文件夹。请选择其他输出文件夹。")
            return

        orig = open_image_fix_orientation(src)
        iw, ih = orig.size

        base_pix = self.base_item.pixmap()
        preview_w = base_pix.width(); preview_h = base_pix.height()
        wm_pix = self.wm_item.pixmap()
        wm_w = wm_pix.width(); wm_h = wm_pix.height()
        wm_pos = self.wm_item.pos()
        center_x_preview = wm_pos.x() + wm_w/2
        center_y_preview = wm_pos.y() + wm_h/2
        anchor_x = center_x_preview / preview_w
        anchor_y = center_y_preview / preview_h
        anchor = (anchor_x, anchor_y)

        scale_ratio = iw / preview_w
        font_size = int(self.fontsize_spin.value() * scale_ratio)
        if font_size < 8: font_size = 8

        wm_pil_high = create_text_watermark_image(
            text=self.text_input.text(),
            font_path=self.font_path,
            font_size=font_size,
            color=self.font_color.getRgb(),
            opacity=self.opacity_slider.value()/100.0,
            stroke_width=0,
            shadow_blur=self.show_blur_spin.value() if self.show_blur_spin.value() > 0 else 0,
            bold=self.bold_cb.isChecked(),
            italic=self.italic_cb.isChecked()
        )

        angle = self.rotate_spin.value()
        if angle != 0:
            wm_pil_high = wm_pil_high.rotate(angle, expand=True, resample=Image.BICUBIC)

        prefix = self.prefix_input.text() or ""
        suffix = self.suffix_input.text() or ""
        fmt = self.format_combo.currentText()
        src_name = Path(src).stem
        src_ext = ".png" if fmt == "png" else ".jpg"
        dst_name = f"{prefix}{src_name}{suffix}{src_ext}"
        dst_path = os.path.join(self.output_dir, dst_name)
        idx = 1
        base_dst = dst_path
        while os.path.exists(dst_path):
            dst_path = os.path.join(self.output_dir, f"{prefix}{src_name}{suffix}_{idx}{src_ext}")
            idx += 1

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