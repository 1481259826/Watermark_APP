# Photo Watermark 图片水印工具

一个简单易用的图片水印添加工具，支持批量处理、自定义水印文本、字体、颜色、透明度、位置等功能。

![图片水印工具](https://github.com/1481259826/Watermark_APP/raw/main/images/screenshot.png)

## 功能特点

- 📝 **自定义文本水印**：支持自定义水印文本内容
- 🎨 **丰富的样式选项**：
  - 自定义字体（支持TTF/OTF字体文件）
  - 调整字体大小、颜色
  - 设置粗体、斜体
  - 添加文字阴影效果
  - 调整透明度
  - 旋转角度
- 📍 **灵活的位置控制**：
  - 九宫格快速定位
  - 自由拖拽调整位置
- 📁 **批量处理**：支持批量导入图片并添加水印
- 💾 **模板管理**：保存和加载水印设置模板，方便重复使用
- 🖼️ **实时预览**：即时预览水印效果

## 下载和安装

### Windows 安全警告说明
由于本程序未进行代码签名,Windows 可能会显示安全警告。这是正常现象。

**如何运行:**
1. 下载 .exe 文件
2. 右键点击文件 → 属性
3. 勾选底部的"解除锁定" → 点击"应用"
4. 如果运行时仍有提示,点击"更多信息" → "仍要运行"

**安全性:** 
- 本项目开源,所有代码可在仓库中查看
- 可以自行从源代码打包(见下方说明)
- VirusTotal 扫描结果: [链接](https://www.virustotal.com/gui/file/03116102f239322890399092339999233202422439202595422649249522424/detection)

## 安装说明

### 环境要求

- Python 3.11+
- 依赖库：Pillow, PySide6

### 安装步骤

1. 克隆仓库到本地：

```bash
git clone https://github.com/yourusername/Photo_Watermark2.git
cd Photo_Watermark2
```

2. 安装依赖：

```bash
pip install -r requirements.txt
```

## 使用说明

1. 运行主程序：

```bash
python main.py
```

2. 导入图片：
   - 点击"导入图片/文件夹"按钮
   - 或直接拖拽图片/文件夹到程序窗口

3. 设置水印：
   - 输入水印文本
   - 选择字体、大小、颜色等
   - 调整位置（使用九宫格或直接拖拽）

4. 导出图片：
   - 选择输出文件夹
   - 点击"导出所选并保存水印"按钮

## 模板功能

您可以保存当前的水印设置为模板，方便下次使用：

1. 设置好水印参数后，点击"保存当前为模板"
2. 输入模板名称
3. 下次使用时，从下拉列表选择模板，点击"加载模板"

## 项目结构

```
Photo_Watermark2/
├── core/                # 核心功能模块
│   ├── batch_worker.py  # 批处理工作器
│   ├── exporter.py      # 图片导出功能
│   ├── image_io.py      # 图片读写操作
│   ├── template_manager.py # 模板管理
│   └── watermark.py     # 水印生成
├── resources/           # 资源文件（字体等）
├── utils/               # 工具函数
├── main.py              # 主程序入口
└── requirements.txt     # 依赖库列表
```

## 许可证

本项目采用 MIT 许可证 - 详情请参阅 [LICENSE](LICENSE) 文件

## 联系方式

如有问题或建议，请通过以下方式联系：

- 项目地址：[https://github.com/1481259826/Watermark_APP](https://github.com/1481259826/Watermark_APP)
- 电子邮件：1481259826@qq.com
