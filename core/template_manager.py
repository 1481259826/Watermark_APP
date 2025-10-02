# core/templates.py
import json
import os

TEMPLATE_FILE = "watermark_templates.json"

class TemplateManager:
    def __init__(self):
        self.templates = {}
        self.last_used = None
        self.load_templates()

    def load_templates(self):
        """加载模板文件"""
        if os.path.exists(TEMPLATE_FILE):
            with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.templates = data.get("templates", {})
                self.last_used = data.get("last_used")
        else:
            # 初始化一个默认模板
            self.templates = {
                "默认模板": {
                    "text": "版权所有",
                    "font_path": "resources/华文中宋.ttf",
                    "font_size": 40,
                    "color": [255, 255, 255, 200],
                    "position": "bottom_right",
                    "opacity": 0.8,
                    "bold": False,
                    "italic": False,
                    "rotate": 0,
                    "show_blur": 2,
                    "stroke_fill": [0, 0, 0, 255]
                }
            }
            self.last_used = "默认模板"
            self.save_templates()

    def save_templates(self):
        """保存模板文件"""
        with open(TEMPLATE_FILE, "w", encoding="utf-8") as f:
            json.dump(
                {"templates": self.templates, "last_used": self.last_used},
                f, indent=4, ensure_ascii=False
            )

    def save_template(self, name, settings):
        """保存当前设置为模板"""
        self.templates[name] = settings
        self.last_used = name
        self.save_templates()

    def load_template(self, name):
        """加载指定模板"""
        if name in self.templates:
            self.last_used = name
            self.save_templates()
            return self.templates[name]
        return None

    def delete_template(self, name):
        """删除模板"""
        if name in self.templates:
            del self.templates[name]
            # 如果删的是当前模板，回退到默认
            if self.last_used == name:
                self.last_used = "默认模板"
            self.save_templates()

