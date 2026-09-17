"""Render exported CAD triangles with a software depth buffer, in millimeters."""
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
SCENE = json.loads((ROOT / "preview/scene.json").read_text())
BG = (239, 242, 243)
INK = (37, 43, 47)
MUTED = (91, 103, 110)
FONT_PATH = "C:/Windows/Fonts/msyh.ttc"


def font(size):
    return ImageFont.truetype(FONT_PATH, size)


def render(size, camera, mode="assembly", active=None, scale=None, center=None):
    width, height = size
    eye = np.array(camera, dtype=float)
    eye /= np.linalg.norm(eye)
    right = np.cross([0., 1., 0.], eye)
    right /= np.linalg.norm(right)
    up = np.cross(eye, right)
    basis = np.stack([right, up, eye])
    pieces = []
    for obj in SCENE:
        name = obj["name"]
        if mode == "front" and (name.startswith("pcb") or name == "screw"):
            continue
        if mode == "inside" and name in ("01_rear_cover", "screw"):
            continue
        vertices = np.array(obj["vertices"], dtype=float)
        if mode == "exploded":
            offset = 0
            if name == "01_rear_cover":
                offset = -18
            elif name.startswith("pcb"):
                offset = -9
            elif name == "02_front_housing":
                offset = 14
            elif name == "03_signal_hood":
                offset = 26
            elif name == "04_diffuser":
                offset = 6
            elif name == "screw":
                offset = -24
            vertices[:, 2] += offset
        color = obj["color"]
        if name == "04_diffuser" and active:
            color = active
        projected = vertices @ basis.T
        pieces.append((vertices, projected, np.array(obj["faces"]), np.array(color)))
    points = np.concatenate([p[1] for p in pieces])
    low, high = points.min(axis=0), points.max(axis=0)
    if center is None:
        center = (low + high) / 2
    if scale is None:
        scale = min((width - 50) / (high[0] - low[0]),
                    (height - 50) / (high[1] - low[1]))
    pixels = np.full((height, width, 3), BG, dtype=np.uint8)
    depth = np.full((height, width), -np.inf)
    light = np.array([-0.35, 0.70, 0.9])
    light /= np.linalg.norm(light)
    for vertices, projected, faces, color in pieces:
        view = projected.copy()
        view[:, 0] = (view[:, 0] - center[0]) * scale + width / 2
        view[:, 1] = height / 2 - (view[:, 1] - center[1]) * scale
        for tri in faces:
            a, b, c = view[tri]
            p, q, r = vertices[tri]
            normal = np.cross(q - p, r - p)
            length = np.linalg.norm(normal)
            if length < 1e-10:
                continue
            normal /= length
            x0 = max(0, int(np.floor(min(a[0], b[0], c[0]))))
            x1 = min(width - 1, int(np.ceil(max(a[0], b[0], c[0]))))
            y0 = max(0, int(np.floor(min(a[1], b[1], c[1]))))
            y1 = min(height - 1, int(np.ceil(max(a[1], b[1], c[1]))))
            if x1 < x0 or y1 < y0:
                continue
            denominator = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
            if abs(denominator) < 1e-8:
                continue
            yy, xx = np.mgrid[y0:y1 + 1, x0:x1 + 1]
            xx, yy = xx + 0.5, yy + 0.5
            wa = ((b[1] - c[1]) * (xx - c[0]) + (c[0] - b[0]) * (yy - c[1])) / denominator
            wb = ((c[1] - a[1]) * (xx - c[0]) + (a[0] - c[0]) * (yy - c[1])) / denominator
            wc = 1 - wa - wb
            zz = wa * a[2] + wb * b[2] + wc * c[2]
            zregion = depth[y0:y1 + 1, x0:x1 + 1]
            mask = (wa >= -1e-7) & (wb >= -1e-7) & (wc >= -1e-7) & (zz > zregion)
            if not mask.any():
                continue
            illumination = 0.53 + 0.47 * max(0, float(normal @ light))
            shade = np.clip(color * illumination * 255, 0, 255).astype(np.uint8)
            pixels[y0:y1 + 1, x0:x1 + 1][mask] = shade
            zregion[mask] = zz[mask]
    return Image.fromarray(pixels)


def text(draw, xy, message, size=24, color=INK):
    draw.text(xy, message, font=font(size), fill=color)


def arrow(draw, start, end, label, label_xy):
    draw.line([start, end], fill=MUTED, width=2)
    a = np.array(start, dtype=float)
    b = np.array(end, dtype=float)
    direction = (b - a) / np.linalg.norm(b - a)
    cross = np.array([-direction[1], direction[0]])
    for point, direction_sign in ((a, 1), (b, -1)):
        tail = point + direction * direction_sign * 10
        draw.polygon([tuple(point), tuple(tail + cross * 4), tuple(tail - cross * 4)], fill=MUTED)
    text(draw, label_xy, label, 22, MUTED)


def overview():
    image = Image.new("RGB", (1800, 1200), BG)
    draw = ImageDraw.Draw(image)
    text(draw, (64, 42), "SL25 / 单灯交通信号灯外壳", 42)
    text(draw, (66, 108), "Rev A · 30 × 30 × 25 mm · 与现有 RGB PCB 配套", 25, MUTED)
    image.paste(render((900, 780), [0.8, 0.5, 1.7], active=[0.25, 0.86, 0.48]), (14, 190))
    image.paste(render((770, 820), [-1.05, 0.25, 1.25], "exploded"), (986, 180))
    draw = ImageDraw.Draw(image)
    draw.line((940, 206, 940, 985), fill=(204, 212, 215), width=2)
    text(draw, (76, 1010), "装配外观", 29)
    text(draw, (76, 1060), "单个灯窗切换红 / 黄 / 绿；底部 USB-C", 23, MUTED)
    text(draw, (1010, 1010), "拆分结构", 29)
    text(draw, (1010, 1060), "后盖 · PCB · 柔光片 · 前壳 · 遮光帽", 23, MUTED)
    text(draw, (76, 1140), "颜色为外观示意；实物透光、混色和打印配合需打样确认。", 20, MUTED)
    image.save(ROOT / "preview/assembly.png")


def drawing():
    image = Image.new("RGB", (1800, 1200), BG)
    draw = ImageDraw.Draw(image)
    text(draw, (65, 40), "SL25 / 外形与装配尺寸", 40)
    text(draw, (67, 106), "单位 mm；STL 已分别转到建议打印朝向", 24, MUTED)
    image.paste(render((610, 610), [0, 0, 1], "front", scale=16,
                       center=[15, 15, 0]), (30, 175))
    image.paste(render((620, 610), [1, 0.001, 0.001], scale=16), (690, 175))
    image.paste(render((430, 550), [-0.45, 0.15, -1.6], "inside"), (1330, 230))
    draw = ImageDraw.Draw(image)
    arrow(draw, (95, 820), (575, 820), "30", (314, 830))
    arrow(draw, (660, 240), (660, 720), "30", (668, 465))
    arrow(draw, (800, 820), (1200, 820), "25（含遮光帽）", (904, 832))
    text(draw, (220, 180), "正面 / 灯窗 Ø7.8", 23)
    text(draw, (902, 180), "右侧面", 23)
    text(draw, (1410, 180), "移除后盖", 23)
    rows = [
        ("USB-C 开口", "13.0 × 6.8；推荐线头外壳 ≤12 × 6"),
        ("打印主体", "前壳壁厚 1.5，正面 2.0；后盖底厚 1.6"),
        ("灯窗与柔光片", "柔光片 Ø9.6 × 1.0；灯珠预留高度 12.5，混光间距 1.3"),
        ("连接与定位", "2 × M2×10 沉头螺丝；定位配合单边 0.20；柔光片与遮光帽胶接"),
    ]
    for index, (label, detail) in enumerate(rows):
        y = 930 + index * 51
        text(draw, (80, y), label, 24)
        text(draw, (355, y), detail, 24, MUTED)
    image.save(ROOT / "preview/dimensions.png")


def states():
    image = Image.new("RGB", (1440, 580), BG)
    draw = ImageDraw.Draw(image)
    text(draw, (40, 22), "同一灯窗的三种颜色示意", 31)
    for index, (label, color) in enumerate([
            ("红", [0.95, 0.19, 0.17]), ("黄", [0.97, 0.73, 0.10]),
            ("绿", [0.24, 0.86, 0.47])]):
        image.paste(render((460, 435), [0.4, 0.15, 1.7], active=color), (index * 480 + 10, 75))
        text(ImageDraw.Draw(image), (index * 480 + 223, 523), label, 28)
    image.save(ROOT / "preview/color_states.png")


if __name__ == "__main__":
    overview()
    drawing()
    states()
    render((1100, 850), [0.45, -1.1, 1.0]).save(ROOT / "preview/usb_underside.png")
    print("Rendered assembly, dimensions, and color states from CAD meshes.")
