"""Generate an editable Sketch document for the VAT Draft Streamlit UI.

The output is a native .sketch ZIP bundle. UI surfaces are represented as
individual rectangle and text layers so they stay editable after Figma import.
"""

from __future__ import annotations

import io
import json
import math
import textwrap
import uuid
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "design"
SKETCH_PATH = OUTPUT_DIR / "VAT_Draft_App_Editable.sketch"
PREVIEW_PATH = OUTPUT_DIR / "VAT_Draft_App_Sketch_Preview.png"

ARTBOARD_W = 1440
ARTBOARD_H = 1024
SIDEBAR_W = 300

COLORS = {
    "page": "#F6F8FB",
    "sidebar": "#F1F5F9",
    "surface": "#FFFFFF",
    "border": "#DBE3EE",
    "text": "#172033",
    "muted": "#64748B",
    "muted2": "#94A3B8",
    "active": "#E2E8F0",
    "primary": "#2563EB",
    "primary_dark": "#1D4ED8",
    "success_bg": "#DCFCE7",
    "success": "#15803D",
    "info_bg": "#DBEAFE",
    "info": "#075985",
    "warning_bg": "#FEF3C7",
    "warning": "#92400E",
    "danger_bg": "#FEE2E2",
    "danger": "#B91C1C",
}

NAMESPACE = uuid.UUID("7631b23a-0200-4881-a52b-9d86ca117572")


def uid(label: str) -> str:
    return str(uuid.uuid5(NAMESPACE, label)).upper()


def color(hex_value: str, alpha: float = 1.0) -> dict:
    value = hex_value.lstrip("#")
    return {
        "_class": "color",
        "alpha": alpha,
        "red": int(value[0:2], 16) / 255,
        "green": int(value[2:4], 16) / 255,
        "blue": int(value[4:6], 16) / 255,
    }


def rect_value(x: float, y: float, width: float, height: float) -> dict:
    return {
        "_class": "rect",
        "constrainProportions": False,
        "height": height,
        "width": width,
        "x": x,
        "y": y,
    }


def export_options() -> dict:
    return {
        "_class": "exportOptions",
        "includedLayerIds": [],
        "layerOptions": 0,
        "shouldTrim": False,
        "exportFormats": [],
    }


def gradient() -> dict:
    return {
        "_class": "gradient",
        "elipseLength": 0,
        "from": "{0.5, 0}",
        "gradientType": 0,
        "to": "{0.5, 1}",
        "stops": [
            {"_class": "gradientStop", "position": 0, "color": color("#FFFFFF")},
            {"_class": "gradientStop", "position": 1, "color": color("#000000")},
        ],
    }


def empty_style(label: str) -> dict:
    return {
        "_class": "style",
        "do_objectID": uid(label + "/style"),
        "endMarkerType": 0,
        "miterLimit": 10,
        "startMarkerType": 0,
        "windingRule": 1,
        "blur": {
            "_class": "blur",
            "isEnabled": False,
            "center": "{0.5, 0.5}",
            "motionAngle": 0,
            "radius": 10,
            "saturation": 1,
            "type": 0,
        },
        "borderOptions": {
            "_class": "borderOptions",
            "isEnabled": True,
            "dashPattern": [],
            "lineCapStyle": 0,
            "lineJoinStyle": 0,
        },
        "borders": [],
        "colorControls": {
            "_class": "colorControls",
            "isEnabled": False,
            "brightness": 0,
            "contrast": 1,
            "hue": 0,
            "saturation": 1,
        },
        "contextSettings": {
            "_class": "graphicsContextSettings",
            "blendMode": 0,
            "opacity": 1,
        },
        "fills": [],
        "innerShadows": [],
        "shadows": [],
    }


def layer_base(cls: str, label: str, x: float, y: float, w: float, h: float) -> dict:
    return {
        "_class": cls,
        "do_objectID": uid(label),
        "booleanOperation": -1,
        "isFixedToViewport": False,
        "isFlippedHorizontal": False,
        "isFlippedVertical": False,
        "isLocked": False,
        "isVisible": True,
        "layerListExpandedType": 0,
        "name": label.split("/")[-1],
        "nameIsFixed": False,
        "resizingConstraint": 63,
        "resizingType": 0,
        "rotation": 0,
        "shouldBreakMaskChain": False,
        "exportOptions": export_options(),
        "frame": rect_value(x, y, w, h),
        "clippingMaskMode": 0,
        "hasClippingMask": False,
    }


def fill_item(hex_value: str) -> dict:
    return {
        "_class": "fill",
        "isEnabled": True,
        "fillType": 0,
        "color": color(hex_value),
        "contextSettings": {"_class": "graphicsContextSettings", "blendMode": 0, "opacity": 1},
        "gradient": gradient(),
        "noiseIndex": 0,
        "noiseIntensity": 0,
        "patternFillType": 1,
        "patternTileScale": 1,
    }


def border_item(hex_value: str, thickness: float = 1) -> dict:
    return {
        "_class": "border",
        "isEnabled": True,
        "fillType": 0,
        "color": color(hex_value),
        "contextSettings": {"_class": "graphicsContextSettings", "blendMode": 0, "opacity": 1},
        "gradient": gradient(),
        "position": 1,
        "thickness": thickness,
    }


def shape_style(label: str, fill: str | None, border: str | None, shadow: bool = False) -> dict:
    style = empty_style(label)
    if fill:
        style["fills"] = [fill_item(fill)]
    if border:
        style["borders"] = [border_item(border)]
    if shadow:
        style["shadows"] = [
            {
                "_class": "shadow",
                "isEnabled": True,
                "blurRadius": 18,
                "offsetX": 0,
                "offsetY": 4,
                "spread": 0,
                "color": color("#0F172A", 0.08),
                "contextSettings": {
                    "_class": "graphicsContextSettings",
                    "blendMode": 0,
                    "opacity": 1,
                },
            }
        ]
    return style


def rectangle_layer(label: str, x: float, y: float, w: float, h: float, *, fill: str,
                    border: str | None = None, radius: float = 0, shadow: bool = False) -> dict:
    layer = layer_base("rectangle", label, x, y, w, h)
    layer["style"] = shape_style(label, fill, border, shadow)
    layer.update(
        {
            "edited": False,
            "isClosed": True,
            "pointRadiusBehaviour": 1,
            "points": [
                {"_class": "curvePoint", "cornerRadius": radius, "curveFrom": "{0, 0}", "curveMode": 1,
                 "curveTo": "{0, 0}", "hasCurveFrom": False, "hasCurveTo": False, "point": "{0, 0}"},
                {"_class": "curvePoint", "cornerRadius": radius, "curveFrom": "{1, 0}", "curveMode": 1,
                 "curveTo": "{1, 0}", "hasCurveFrom": False, "hasCurveTo": False, "point": "{1, 0}"},
                {"_class": "curvePoint", "cornerRadius": radius, "curveFrom": "{1, 1}", "curveMode": 1,
                 "curveTo": "{1, 1}", "hasCurveFrom": False, "hasCurveTo": False, "point": "{1, 1}"},
                {"_class": "curvePoint", "cornerRadius": radius, "curveFrom": "{0, 1}", "curveMode": 1,
                 "curveTo": "{0, 1}", "hasCurveFrom": False, "hasCurveTo": False, "point": "{0, 1}"},
            ],
            "fixedRadius": radius,
            "needsConvertionToNewRoundCorners": False,
            "hasConvertedToNewRoundCorners": True,
        }
    )
    return layer


def text_layer(label: str, value: str, x: float, y: float, w: float, h: float, *,
               size: float = 16, weight: str = "regular", hex_value: str = COLORS["text"],
               align: int = 0) -> dict:
    layer = layer_base("text", label, x, y, w, h)
    font_name = "Arial-BoldMT" if weight == "bold" else "ArialMT"
    attrs = {
        "MSAttributedStringFontAttribute": {
            "_class": "fontDescriptor",
            "attributes": {"name": font_name, "size": size},
        },
        "MSAttributedStringColorAttribute": color(hex_value),
        "kerning": 0,
        "textStyleVerticalAlignmentKey": 0,
        "paragraphStyle": {"_class": "paragraphStyle", "alignment": align},
    }
    style = empty_style(label)
    style["textStyle"] = {
        "_class": "textStyle",
        "encodedAttributes": attrs,
        "verticalAlignment": 0,
    }
    layer["style"] = style
    layer.update(
        {
            "attributedString": {
                "_class": "attributedString",
                "string": value,
                "attributes": [
                    {
                        "_class": "stringAttribute",
                        "location": 0,
                        "length": len(value),
                        "attributes": attrs,
                    }
                ],
            },
            "automaticallyDrawOnUnderlyingPath": False,
            "dontSynchroniseWithSymbol": False,
            "glyphBounds": f"{{{{0, 0}}, {{{max(1, int(w))}, {max(1, int(h))}}}}}",
            "lineSpacingBehaviour": 2,
            "textBehaviour": 1,
        }
    )
    return layer


class Screen:
    def __init__(self, name: str, artboard_id: str, page_x: float, page_y: float):
        self.name = name
        self.artboard_id = artboard_id
        self.page_x = page_x
        self.page_y = page_y
        self.layers: list[dict] = []  # natural paint order: back to front
        self.preview: list[dict] = []
        self.counter = 0

    def label(self, name: str) -> str:
        self.counter += 1
        return f"{self.name}/{self.counter:03d}/{name}"

    def rect(self, x: float, y: float, w: float, h: float, fill: str, *, border: str | None = None,
             radius: float = 0, name: str = "Rectangle", shadow: bool = False) -> None:
        label = self.label(name)
        self.layers.append(rectangle_layer(label, x, y, w, h, fill=fill, border=border, radius=radius, shadow=shadow))
        self.preview.append({"type": "rect", "x": x, "y": y, "w": w, "h": h,
                             "fill": fill, "border": border, "radius": radius})

    def text(self, value: str, x: float, y: float, w: float, h: float, *, size: float = 16,
             weight: str = "regular", fill: str = COLORS["text"], name: str = "Text",
             align: int = 0) -> None:
        label = self.label(name)
        self.layers.append(text_layer(label, value, x, y, w, h, size=size, weight=weight,
                                      hex_value=fill, align=align))
        self.preview.append({"type": "text", "text": value, "x": x, "y": y, "w": w, "h": h,
                             "size": size, "weight": weight, "fill": fill, "align": align})

    def line(self, x: float, y: float, w: float, fill: str = COLORS["border"], name: str = "Divider") -> None:
        self.rect(x, y, w, 1, fill, name=name)

    def button(self, label: str, x: float, y: float, w: float, *, primary: bool = False,
               name: str | None = None) -> None:
        bg = COLORS["primary"] if primary else COLORS["surface"]
        border = None if primary else COLORS["border"]
        fg = "#FFFFFF" if primary else COLORS["text"]
        self.rect(x, y, w, 44, bg, border=border, radius=10, name=(name or label) + " / Background")
        self.text(label, x + 12, y + 12, w - 24, 22, size=14, weight="bold", fill=fg,
                  name=(name or label) + " / Label", align=2)

    def section_title(self, title: str, y: float, subtitle: str | None = None) -> float:
        self.text(title, 380, y, 1000, 38, size=27, weight="bold", name=title)
        if subtitle:
            self.text(subtitle, 380, y + 46, 1000, 38, size=14, fill=COLORS["muted"], name=title + " / Description")
            return y + 94
        return y + 52

    def metric(self, label: str, value: str, x: float, y: float, w: float, *, help_text: str | None = None) -> None:
        self.rect(x, y, w, 112, COLORS["surface"], border=COLORS["border"], radius=14, name=label + " / Card")
        self.text(label, x + 18, y + 18, w - 36, 22, size=14, name=label + " / Label")
        self.text(value, x + 18, y + 50, w - 36, 42, size=30, name=label + " / Value")
        if help_text:
            self.text(help_text, x + 18, y + 89, w - 36, 18, size=11, fill=COLORS["muted"], name=label + " / Help")

    def banner(self, text_value: str, y: float = 176, kind: str = "success") -> None:
        bg_key = {"success": "success_bg", "info": "info_bg", "warning": "warning_bg", "danger": "danger_bg"}[kind]
        fg_key = {"success": "success", "info": "info", "warning": "warning", "danger": "danger"}[kind]
        self.rect(380, y, 1000, 56, COLORS[bg_key], radius=10, name=f"{kind.title()} Banner")
        self.text(text_value, 396, y + 17, 968, 24, size=14, fill=COLORS[fg_key], name=f"{kind.title()} Banner / Text")

    def table(self, x: float, y: float, widths: list[float], headers: list[str], rows: list[list[str]],
              row_h: float = 42, name: str = "Table") -> None:
        total_w = sum(widths)
        total_h = row_h * (len(rows) + 1)
        self.rect(x, y, total_w, total_h, COLORS["surface"], border=COLORS["border"], radius=10, name=name + " / Surface")
        self.rect(x, y, total_w, row_h, "#F8FAFC", radius=10, name=name + " / Header Background")
        cursor = x
        for index, (header, width) in enumerate(zip(headers, widths)):
            if index:
                self.rect(cursor, y, 1, total_h, COLORS["border"], name=name + f" / Column {index} Divider")
            self.text(header, cursor + 12, y + 12, width - 24, 20, size=13, weight="bold", fill=COLORS["muted"], name=name + f" / Header {header}")
            cursor += width
        for row_index, row in enumerate(rows):
            ry = y + row_h * (row_index + 1)
            self.rect(x, ry, total_w, 1, COLORS["border"], name=name + f" / Row {row_index + 1} Divider")
            cursor = x
            for cell_index, (value, width) in enumerate(zip(row, widths)):
                self.text(value, cursor + 12, ry + 12, width - 24, 20, size=13, name=name + f" / R{row_index + 1}C{cell_index + 1}")
                cursor += width

    def sidebar(self, active: str) -> None:
        self.rect(0, 0, SIDEBAR_W, ARTBOARD_H, COLORS["sidebar"], name="Sidebar / Background")
        self.rect(SIDEBAR_W - 1, 0, 1, ARTBOARD_H, COLORS["border"], name="Sidebar / Border")
        self.text("Nháp VAT", 20, 88, 200, 28, size=17, weight="bold", name="Sidebar / Brand")
        self.text("Công cụ nội bộ", 20, 128, 220, 22, size=14, fill=COLORS["muted2"], name="Sidebar / Subtitle")
        items = [
            ("🏠", "Tổng quan"),
            ("🧾", "Xử lý hóa đơn"),
            ("🔎", "Tra cứu nguồn"),
            ("🗂", "Quản lý dữ liệu"),
            ("✓", "Kiểm tra dữ liệu"),
            ("⚙", "Cấu hình"),
        ]
        y = 160
        for icon, item in items:
            if item == active:
                self.rect(20, y, 260, 36, COLORS["active"], radius=10, name=f"Sidebar / Active / {item}")
            self.text(icon, 28, y + 8, 20, 20, size=15, name=f"Sidebar / Icon / {item}")
            self.text(item, 54, y + 8, 210, 20, size=14, weight="bold" if item == active else "regular", name=f"Sidebar / Item / {item}")
            y += 44
        self.line(20, 420, 260, name="Sidebar / Divider")
        self.text("DỮ LIỆU ĐANG DÙNG", 20, 456, 240, 20, size=12, fill=COLORS["muted2"], name="Sidebar / Data Label")
        self.text("Tối ưu nháp VAT.xlsx", 20, 498, 240, 24, size=14, weight="bold", name="Sidebar / File Name")
        self.text("Cập nhật: 28/07/2026 08:14", 20, 538, 250, 20, size=12, fill=COLORS["muted2"], name="Sidebar / Updated At")

    def header(self, icon: str, title: str, subtitle: str) -> None:
        self.text(icon, 388, 68, 50, 52, size=42, name="Header / Icon")
        self.text(title, 448, 72, 860, 56, size=42, weight="bold", name="Header / Title")
        self.text(subtitle, 380, 140, 1000, 26, size=14, fill=COLORS["muted2"], name="Header / Subtitle")

    def artboard(self) -> dict:
        layer = layer_base("artboard", self.name, self.page_x, self.page_y, ARTBOARD_W, ARTBOARD_H)
        layer["do_objectID"] = self.artboard_id
        layer["name"] = self.name
        layer["shouldBreakMaskChain"] = True
        layer["style"] = empty_style(self.name + "/artboard")
        layer.update(
            {
                "hasClickThrough": True,
                "groupLayout": {"_class": "MSImmutableFreeformGroupLayout"},
                "layers": list(reversed(self.layers)),
                "hasBackgroundColor": True,
                "includeBackgroundColorInExport": True,
                "includeInCloudUpload": True,
                "isFlowHome": False,
                "presetDictionary": {},
                "resizesContent": False,
                "backgroundColor": color(COLORS["page"]),
                "horizontalRulerData": {"_class": "rulerData", "base": 0, "guides": []},
                "verticalRulerData": {"_class": "rulerData", "base": 0, "guides": []},
            }
        )
        return layer


def add_overview(screen: Screen) -> None:
    screen.sidebar("Tổng quan")
    screen.header("🏠", "Tổng quan", "Theo dõi dữ liệu đang dùng và đi nhanh đến công việc cần thực hiện.")
    screen.banner("Dữ liệu sẵn sàng · Tối ưu nháp VAT.xlsx · 5,726 dòng Gộp VAT · 2,186 dòng Khớp mã")
    screen.text("Chỉ số dữ liệu", 380, 265, 600, 38, size=27, weight="bold", name="Section / Chỉ số dữ liệu")
    for label, value, x in [
        ("Số dòng Gộp VAT", "5,726", 380),
        ("Số dòng Khớp mã", "2,186", 635),
        ("Thời gian cập nhật", "28/07/2026", 890),
        ("Trạng thái dữ liệu", "Sẵn sàng", 1145),
    ]:
        screen.metric(label, value, x, 315, 235)
    screen.text("Thao tác nhanh", 380, 465, 600, 38, size=27, weight="bold", name="Section / Thao tác nhanh")
    screen.text("Chọn công việc cần làm. Dữ liệu và kết quả đang nhập được giữ theo session hiện tại.", 380, 510, 1000, 24, size=14, fill=COLORS["muted2"], name="Section / Thao tác nhanh / Description")
    actions = [
        ("Xử lý hóa đơn", "Dán dữ liệu, kiểm tra và xuất kết quả\nphân bổ.", "🧾  Mở xử lý hóa đơn"),
        ("Tra cứu nguồn", "Tra nhiều mã sản phẩm và xem nguồn\ncòn tồn dương.", "🔎  Mở tra cứu nguồn"),
        ("Kiểm tra dữ liệu", "Xem các chỉ báo cần xử lý hoặc rà\nsoát.", "✓  Mở kiểm tra dữ liệu"),
    ]
    for index, (title, description, action) in enumerate(actions):
        x = 380 + index * 335
        screen.rect(x, 548, 310, 170, COLORS["surface"], border=COLORS["border"], radius=14, name=f"Quick Action / {title} / Card")
        screen.text(title, x + 18, 570, 275, 24, size=15, weight="bold", name=f"Quick Action / {title} / Title")
        screen.text(description, x + 18, 612, 275, 42, size=13, fill=COLORS["muted2"], name=f"Quick Action / {title} / Description")
        screen.text(action, x + 18, 675, 275, 22, size=13, name=f"Quick Action / {title} / Link")
    screen.text("Tóm tắt cảnh báo dữ liệu", 380, 760, 700, 38, size=27, weight="bold", name="Section / Alerts")
    alerts = [("Mã VAT trống", "1,082"), ("Tồn không dương", "3,870"), ("Tồn không hợp lệ", "0"), ("Mã SP nhiều Mã VAT", "4")]
    for index, (label, value) in enumerate(alerts):
        screen.metric(label, value, 380 + index * 255, 815, 235)


def add_invoice(screen: Screen) -> None:
    screen.sidebar("Xử lý hóa đơn")
    screen.header("🧾", "Xử lý hóa đơn", "Nhập dữ liệu từ Excel, rà soát lỗi và tạo kết quả phân bổ trong một quy trình rõ ràng.")
    screen.banner("Dữ liệu sẵn sàng · Tối ưu nháp VAT.xlsx · 5,726 dòng Gộp VAT · 2,186 dòng Khớp mã")
    screen.section_title("1. Nhập dữ liệu", 265, "Sao chép 4 cột từ Excel theo thứ tự Mã SP, Tên SP, SL, Giá bán rồi dán vào vùng bên dưới.")
    screen.rect(380, 350, 1000, 255, COLORS["surface"], border=COLORS["border"], radius=14, name="Paste Data / Card")
    screen.text("Khu vực dán dữ liệu", 398, 372, 400, 22, size=14, name="Paste Data / Label")
    screen.rect(398, 405, 964, 126, "#FFFFFF", border="#E5E7EB", radius=10, name="Paste Data / Textarea")
    screen.text("Mã SP\tTên SP\tSL\tGiá bán", 414, 421, 500, 22, size=13, fill=COLORS["muted2"], name="Paste Data / Placeholder")
    screen.button("📥  Đọc dữ liệu", 398, 548, 150, primary=True)
    screen.button("🗑  Xóa toàn bộ", 568, 548, 150)
    screen.section_title("2. Kiểm tra và chỉnh sửa", 650, "Có thể sửa trực tiếp từng ô hoặc thêm dòng. Các giá trị vẫn được kiểm tra theo quy tắc hiện tại.")
    screen.table(380, 735, [190, 410, 130, 230], ["Mã SP", "Tên SP", "SL", "Giá bán"],
                 [["SP001", "Tên sản phẩm mẫu", "10", "125,000"], ["SP002", "Tên sản phẩm mẫu 2", "5", "80,000"]], name="Invoice Editor")
    screen.button("✓  Kiểm tra dữ liệu", 380, 885, 180)


def add_lookup(screen: Screen) -> None:
    screen.sidebar("Tra cứu nguồn")
    screen.header("🔎", "Tra cứu nguồn", "Tra nhiều sản phẩm cùng lúc và xem các nguồn còn tồn nháp dương theo thứ tự hiện có.")
    screen.banner("Dữ liệu sẵn sàng · Tối ưu nháp VAT.xlsx · 5,726 dòng Gộp VAT · 2,186 dòng Khớp mã")
    screen.section_title("1. Nhập danh sách cần tra", 265, "Dán các cột cách nhau bằng phím Tab. Chỉ cần Mã SP hoặc Tên SP; SL và Giá bán là tùy chọn.")
    screen.rect(380, 350, 1000, 235, COLORS["surface"], border=COLORS["border"], radius=14, name="Lookup Input / Card")
    screen.text("Dán dữ liệu (các cột cách nhau bằng phím Tab)", 398, 372, 560, 22, size=14, name="Lookup Input / Label")
    screen.rect(398, 405, 964, 102, "#FFFFFF", border="#E5E7EB", radius=10, name="Lookup Input / Textarea")
    screen.button("📥  Đọc dữ liệu", 398, 524, 150)
    screen.button("🗑  Xóa toàn bộ", 568, 524, 150)
    screen.section_title("2. Rà soát và tra cứu", 628, "Có thể chỉnh sửa trực tiếp bảng trước khi chạy tra cứu.")
    screen.table(380, 710, [190, 410, 130, 230], ["Mã SP", "Tên SP", "SL", "Giá bán"],
                 [["SP001", "Tên sản phẩm cần tra", "10", "125,000"], ["SP010", "Sản phẩm thứ hai", "3", "92,000"]], name="Lookup Editor")
    screen.button("🔎  Tra cứu nguồn", 380, 860, 180, primary=True)
    screen.rect(580, 860, 390, 44, COLORS["success_bg"], radius=10, name="Lookup Hint / Background")
    screen.text("Ưu tiên nguồn đủ tồn và có tần suất xuất hiện cao.", 596, 872, 360, 20, size=13, fill=COLORS["success"], name="Lookup Hint / Text")


def add_manage(screen: Screen) -> None:
    screen.sidebar("Quản lý dữ liệu")
    screen.header("🗂", "Quản lý dữ liệu", "Theo dõi file đang dùng, kiểm tra phiên bản mới trước khi xác nhận và khôi phục khi cần.")
    screen.text("1. Dữ liệu hiện tại", 380, 190, 760, 38, size=27, weight="bold", name="Section / Current Data")
    screen.banner("Dữ liệu sẵn sàng · Tối ưu nháp VAT.xlsx · 5,726 dòng Gộp VAT · 2,186 dòng Khớp mã", y=238)
    screen.rect(380, 312, 1000, 245, COLORS["surface"], border=COLORS["border"], radius=14, name="Current Data / Card")
    screen.text("📄", 400, 342, 38, 40, size=28, name="Current Data / File Icon")
    screen.text("Tối ưu nháp VAT.xlsx", 448, 344, 700, 36, size=27, weight="bold", name="Current Data / File Name")
    screen.text("Cập nhật lúc 28/07/2026 08:14 · Người tải lên: Không xác định", 398, 392, 720, 22, size=13, fill=COLORS["muted2"], name="Current Data / Metadata")
    for label, value, x in [("Dòng Gộp VAT", "5,726", 398), ("Dòng Khớp mã", "2,186", 728), ("Trạng thái kiểm tra", "Hợp lệ", 1058)]:
        screen.metric(label, value, x, 432, 304)
    screen.section_title("2. Upload phiên bản mới", 610, "File chỉ trở thành dữ liệu hiện tại sau khi kiểm tra hợp lệ và bạn bấm xác nhận.")
    screen.rect(380, 700, 1000, 150, COLORS["surface"], border=COLORS["border"], radius=14, name="Upload / Dropzone")
    screen.text("⬆", 398, 740, 42, 42, size=30, fill=COLORS["primary"], name="Upload / Icon")
    screen.text("Kéo thả hoặc chọn file .xlsx", 450, 738, 550, 28, size=17, weight="bold", name="Upload / Title")
    screen.text("Giới hạn 200MB · chỉ nhận tệp Excel", 450, 773, 550, 22, size=13, fill=COLORS["muted2"], name="Upload / Help")
    screen.button("Chọn file", 1190, 746, 150)
    screen.text("3. Lịch sử phiên bản", 380, 900, 760, 38, size=27, weight="bold", name="Section / Version History")


def add_check(screen: Screen) -> None:
    screen.sidebar("Kiểm tra dữ liệu")
    screen.header("✓", "Kiểm tra dữ liệu", "Theo dõi lỗi, cảnh báo và các trường hợp cần rà soát tên. Trang này không gọi AI.")
    screen.banner("Dữ liệu sẵn sàng · Tối ưu nháp VAT.xlsx · 5,726 dòng Gộp VAT · 2,186 dòng Khớp mã")
    screen.section_title("Phân loại chỉ báo", 265, "Các số liệu bên dưới chỉ tổng hợp những trường đã được workbook hiện tại tính sẵn.")
    for label, value, x in [("Nghiêm trọng", "0", 380), ("Cần xử lý", "1,086", 720), ("Cần rà soát", "3,870", 1060)]:
        screen.metric(label, value, x, 350, 320)
    screen.text("Chi tiết theo sheet", 380, 505, 760, 38, size=27, weight="bold", name="Section / Sheet Details")
    cards = [("Gộp VAT", "5,726", [("Mã VAT trống", "1,082"), ("Tồn sai kiểu", "0"), ("Tồn ≤ 0", "3,870")]),
             ("Khớp mã", "2,186", [("Mã SP trống", "0"), ("Mã VAT trống", "0"), ("Nhiều Mã VAT", "4")])]
    for index, (title, total, details) in enumerate(cards):
        x = 380 + index * 510
        screen.rect(x, 560, 490, 270, COLORS["surface"], border=COLORS["border"], radius=14, name=f"{title} / Card")
        screen.text(title, x + 18, 582, 200, 24, size=16, weight="bold", name=f"{title} / Title")
        screen.text("Tổng số dòng", x + 18, 620, 200, 20, size=13, name=f"{title} / Total Label")
        screen.text(total, x + 18, 650, 220, 42, size=30, name=f"{title} / Total Value")
        for d_index, (label, value) in enumerate(details):
            dx = x + 18 + d_index * 152
            screen.text(label, dx, 720, 140, 18, size=11, fill=COLORS["muted"], name=f"{title} / {label} / Label")
            screen.text(value, dx, 748, 140, 30, size=21, name=f"{title} / {label} / Value")
    screen.section_title("Rà soát tên sản phẩm", 870, "Tính điểm deterministic và xuất danh sách để kiểm tra thủ công bên ngoài app.")
    screen.button("⚙  Tính bảng kiểm tra tên", 380, 960, 230)


def add_config(screen: Screen) -> None:
    screen.sidebar("Cấu hình")
    screen.header("⚙", "Cấu hình", "Giải thích các quy tắc đang được ứng dụng sử dụng. Trang này chỉ đọc và không ghi file cấu hình.")
    screen.banner("Cấu hình hiện được đọc từ config/settings.yaml. Muốn thay đổi cần sửa file trên máy chủ và khởi động lại ứng dụng.", y=176, kind="info")
    screen.rect(380, 262, 1000, 620, COLORS["surface"], border=COLORS["border"], radius=12, name="Name Matching / Accordion")
    screen.text("⌄", 398, 282, 24, 24, size=18, name="Name Matching / Chevron")
    screen.text("So khớp tên sản phẩm", 432, 282, 420, 24, size=15, weight="bold", name="Name Matching / Title")
    screen.line(380, 322, 1000, name="Name Matching / Header Divider")
    screen.text("Điểm so khớp được tính deterministic từ bốn nguồn tên, sau đó cộng hoặc trừ các hệ số token.", 398, 345, 950, 24, size=13, fill=COLORS["muted2"], name="Name Matching / Description")
    rows = [
        ["Tên SP người dùng nhập", "0.45", "Trọng số của tên trong hóa đơn."],
        ["Tên SP trong Khớp mã", "0.25", "Trọng số của tên từ bảng mapping."],
        ["TÊN VAT KIOT", "0.20", "Trọng số tên VAT từ dữ liệu tồn."],
        ["Tên trước VAT đã làm sạch", "0.10", "Tên đã bỏ phần giá và hậu tố VAT."],
        ["Thưởng token số/kích thước", "8.00", "Cộng điểm khi token số hoặc kích thước trùng."],
        ["Thưởng kích thước trùng", "6.00", "Hệ số thưởng kích thước theo cấu hình."],
        ["Phạt token số mâu thuẫn", "25.00", "Trừ điểm khi hai tên có số không tương thích."],
        ["Phạt khác biến thể", "15.00", "Trừ điểm cho khác biệt biến thể rõ ràng."],
        ["Ngưỡng cần kiểm tra thủ công", "55.00", "Điểm thấp hơn ngưỡng sẽ được đánh dấu rà soát."],
    ]
    screen.table(398, 388, [400, 110, 452], ["Tham số", "Giá trị", "Ý nghĩa"], rows, row_h=43, name="Name Matching / Table")
    screen.rect(380, 910, 320, 52, COLORS["surface"], border=COLORS["border"], radius=10, name="Priority Sources / Accordion")
    screen.text("›  Ưu tiên nguồn", 398, 926, 270, 22, size=14, weight="bold", name="Priority Sources / Label")
    screen.rect(720, 910, 320, 52, COLORS["surface"], border=COLORS["border"], radius=10, name="Quantity Rules / Accordion")
    screen.text("›  Quy tắc số lượng và tồn kho", 738, 926, 280, 22, size=14, weight="bold", name="Quantity Rules / Label")


def add_ui_kit(screen: Screen) -> None:
    screen.rect(0, 0, ARTBOARD_W, ARTBOARD_H, "#FFFFFF", name="UI Kit / Background")
    screen.text("VAT Draft App · UI Kit", 80, 68, 900, 54, size=38, weight="bold", name="UI Kit / Title")
    screen.text("Các token và component cơ bản để tiếp tục chỉnh sửa trong Figma.", 80, 126, 900, 26, size=15, fill=COLORS["muted"], name="UI Kit / Subtitle")
    screen.text("Màu sắc", 80, 205, 400, 34, size=26, weight="bold", name="UI Kit / Colors / Title")
    swatches = [("Page", "page"), ("Sidebar", "sidebar"), ("Surface", "surface"), ("Border", "border"), ("Primary", "primary"), ("Success", "success"), ("Info", "info"), ("Danger", "danger")]
    for index, (label, key) in enumerate(swatches):
        x = 80 + (index % 4) * 200
        y = 260 + (index // 4) * 118
        screen.rect(x, y, 64, 64, COLORS[key], border=COLORS["border"] if key in {"page", "sidebar", "surface"} else None, radius=12, name=f"UI Kit / Color / {label}")
        screen.text(label, x + 78, y + 8, 108, 22, size=14, weight="bold", name=f"UI Kit / Color / {label} / Name")
        screen.text(COLORS[key], x + 78, y + 35, 108, 20, size=12, fill=COLORS["muted"], name=f"UI Kit / Color / {label} / Value")
    screen.text("Kiểu chữ", 80, 515, 400, 34, size=26, weight="bold", name="UI Kit / Typography / Title")
    screen.text("Tiêu đề trang · 42px Bold", 80, 565, 600, 52, size=42, weight="bold", name="UI Kit / Typography / H1")
    screen.text("Tiêu đề section · 27px Bold", 80, 635, 600, 38, size=27, weight="bold", name="UI Kit / Typography / H2")
    screen.text("Nội dung mặc định · 14px Regular", 80, 690, 600, 24, size=14, name="UI Kit / Typography / Body")
    screen.text("Nội dung phụ · 13px Regular", 80, 725, 600, 22, size=13, fill=COLORS["muted"], name="UI Kit / Typography / Caption")
    screen.text("Nút bấm", 850, 205, 400, 34, size=26, weight="bold", name="UI Kit / Buttons / Title")
    screen.button("Nút chính", 850, 265, 150, primary=True, name="UI Kit / Primary Button")
    screen.button("Nút phụ", 1020, 265, 150, name="UI Kit / Secondary Button")
    screen.text("Thông báo", 850, 355, 400, 34, size=26, weight="bold", name="UI Kit / Banners / Title")
    for index, (kind, label) in enumerate([("success", "Dữ liệu sẵn sàng"), ("info", "Thông tin cấu hình"), ("warning", "Cần kiểm tra"), ("danger", "Có lỗi dữ liệu")]):
        y = 410 + index * 70
        bg = COLORS[kind + "_bg"]
        fg = COLORS[kind]
        screen.rect(850, y, 470, 52, bg, radius=10, name=f"UI Kit / Banner / {kind}")
        screen.text(label, 868, y + 16, 430, 22, size=14, fill=fg, name=f"UI Kit / Banner / {kind} / Label")
    screen.text("Card chỉ số", 850, 720, 400, 34, size=26, weight="bold", name="UI Kit / Metrics / Title")
    screen.metric("Số dòng Gộp VAT", "5,726", 850, 770, 260)


def build_screens() -> list[Screen]:
    specs = [
        ("01 · Tổng quan", 0, 0, add_overview),
        ("02 · Xử lý hóa đơn", 1540, 0, add_invoice),
        ("03 · Tra cứu nguồn", 0, 1120, add_lookup),
        ("04 · Quản lý dữ liệu", 1540, 1120, add_manage),
        ("05 · Kiểm tra dữ liệu", 0, 2240, add_check),
        ("06 · Cấu hình", 1540, 2240, add_config),
        ("07 · UI Kit", 0, 3360, add_ui_kit),
    ]
    screens: list[Screen] = []
    for name, page_x, page_y, builder in specs:
        screen = Screen(name, uid(name + "/artboard-id"), page_x, page_y)
        builder(screen)
        screens.append(screen)
    return screens


def page_json(page_id: str, screens: list[Screen]) -> dict:
    page = layer_base("page", "VAT Draft App / Page", 0, 0, 0, 0)
    page["do_objectID"] = page_id
    page["name"] = "VAT Draft App"
    page["style"] = empty_style("VAT Draft App / Page")
    page.update(
        {
            "hasClickThrough": True,
            "groupLayout": {"_class": "MSImmutableFreeformGroupLayout"},
            "layers": [screen.artboard() for screen in screens],
            "includeInCloudUpload": True,
            "horizontalRulerData": {"_class": "rulerData", "base": 0, "guides": []},
            "verticalRulerData": {"_class": "rulerData", "base": 0, "guides": []},
        }
    )
    return page


def document_json(page_id: str) -> dict:
    return {
        "_class": "document",
        "do_objectID": uid("VAT Draft App / Document"),
        "colorSpace": 0,
        "currentPageIndex": 0,
        "assets": {
            "_class": "assetCollection",
            "do_objectID": uid("VAT Draft App / Assets"),
            "images": [],
            "colorAssets": [],
            "exportPresets": [],
            "gradientAssets": [],
            "imageCollection": {"_class": "imageCollection", "images": {}},
            "colors": [],
            "gradients": [],
        },
        "foreignLayerStyles": [],
        "foreignSymbols": [],
        "foreignTextStyles": [],
        "layerStyles": {"_class": "sharedStyleContainer", "objects": []},
        "layerSymbols": {"_class": "symbolContainer", "objects": []},
        "layerTextStyles": {"_class": "sharedTextStyleContainer", "objects": []},
        "pages": [{"_class": "MSJSONFileReference", "_ref_class": "MSImmutablePage", "_ref": f"pages/{page_id}"}],
    }


def meta_json(page_id: str, screens: list[Screen]) -> dict:
    artboards = {screen.artboard_id: {"name": screen.name} for screen in screens}
    commit = "6896e2bfdb0a2a03f745e4054a8c5fc58565f9f1"
    return {
        "commit": commit,
        "pagesAndArtboards": {page_id: {"name": "VAT Draft App", "artboards": artboards}},
        "version": 123,
        "fonts": [],
        "compatibilityVersion": 99,
        "app": "com.bohemiancoding.sketch3",
        "autosaved": 0,
        "variant": "NONAPPSTORE",
        "created": {
            "commit": commit,
            "appVersion": "63.1",
            "build": 92452,
            "app": "com.bohemiancoding.sketch3",
            "compatibilityVersion": 99,
            "version": 123,
            "variant": "NONAPPSTORE",
        },
        "saveHistory": ["NONAPPSTORE.92452"],
        "appVersion": "63.1",
        "build": 92452,
    }


def font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def render_screen(screen: Screen, scale: float = 0.5) -> Image.Image:
    image = Image.new("RGB", (int(ARTBOARD_W * scale), int(ARTBOARD_H * scale)), COLORS["page"])
    draw = ImageDraw.Draw(image)
    for item in screen.preview:
        if item["type"] == "rect":
            xy = [int(item["x"] * scale), int(item["y"] * scale),
                  int((item["x"] + item["w"]) * scale), int((item["y"] + item["h"]) * scale)]
            radius = int(item["radius"] * scale)
            draw.rounded_rectangle(xy, radius=radius, fill=item["fill"],
                                   outline=item["border"], width=max(1, int(scale)) if item["border"] else 1)
        elif item["type"] == "text":
            px = max(8, int(item["size"] * scale))
            fnt = font(px, item["weight"] == "bold")
            max_chars = max(3, int(item["w"] / max(6, item["size"] * 0.56)))
            lines = []
            for source_line in item["text"].splitlines() or [""]:
                lines.extend(textwrap.wrap(source_line, width=max_chars, replace_whitespace=False) or [""])
            value = "\n".join(lines)
            x = int(item["x"] * scale)
            if item["align"] == 2:
                bbox = draw.multiline_textbbox((0, 0), value, font=fnt, spacing=2)
                x += max(0, int(item["w"] * scale - (bbox[2] - bbox[0])) // 2)
            draw.multiline_text((x, int(item["y"] * scale)), value, fill=item["fill"], font=fnt, spacing=2)
    return image


def render_contact_sheet(screens: list[Screen]) -> tuple[bytes, bytes]:
    thumbs = [render_screen(screen, 0.32) for screen in screens]
    tile_w, tile_h = thumbs[0].size
    cols = 2
    rows = math.ceil(len(thumbs) / cols)
    margin = 24
    label_h = 34
    sheet = Image.new("RGB", (cols * tile_w + (cols + 1) * margin,
                              rows * (tile_h + label_h) + (rows + 1) * margin), "#E2E8F0")
    draw = ImageDraw.Draw(sheet)
    for index, (screen, thumb) in enumerate(zip(screens, thumbs)):
        col = index % cols
        row = index // cols
        x = margin + col * (tile_w + margin)
        y = margin + row * (tile_h + label_h + margin)
        sheet.paste(thumb, (x, y + label_h))
        draw.text((x, y + 5), screen.name, fill=COLORS["text"], font=font(18, True))
    output = io.BytesIO()
    sheet.save(output, format="PNG", optimize=True)
    preview = io.BytesIO()
    thumbs[0].save(preview, format="PNG", optimize=True)
    return output.getvalue(), preview.getvalue()


def write_sketch() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    screens = build_screens()
    page_id = uid("VAT Draft App / Page ID")
    page = page_json(page_id, screens)
    document = document_json(page_id)
    meta = meta_json(page_id, screens)
    user = {
        "document": {"pageListHeight": 85, "pageListCollapsed": 0},
        page_id: {"scrollOrigin": "{-80, -80}", "zoomValue": 0.2},
    }
    contact_sheet, overview_preview = render_contact_sheet(screens)
    PREVIEW_PATH.write_bytes(contact_sheet)
    with zipfile.ZipFile(SKETCH_PATH, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("document.json", json.dumps(document, ensure_ascii=False, separators=(",", ":")))
        archive.writestr("meta.json", json.dumps(meta, ensure_ascii=False, separators=(",", ":")))
        archive.writestr("user.json", json.dumps(user, ensure_ascii=False, separators=(",", ":")))
        archive.writestr(f"pages/{page_id}.json", json.dumps(page, ensure_ascii=False, separators=(",", ":")))
        archive.writestr("previews/preview.png", overview_preview)
        archive.writestr("previews/thumbnail.png", overview_preview)
    print(f"Created {SKETCH_PATH}")
    print(f"Created {PREVIEW_PATH}")
    print(f"Artboards: {len(screens)}")
    print(f"Editable layers: {sum(len(screen.layers) for screen in screens)}")


if __name__ == "__main__":
    write_sketch()
