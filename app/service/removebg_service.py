# coding:utf-8
import os
import io
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image
from PySide6.QtCore import QThread, Signal


# ============================================================
# 核心背景去除算法
def _sample_corner_colors(img: Image.Image, sample_size: int = 5) -> list:
    """从图片四角采样背景颜色"""
    w, h = img.size
    corners = [
        (0, 0),  (w - sample_size, 0),
        (0, h - sample_size), (w - sample_size, h - sample_size),
    ]
    colors = []
    for cx, cy in corners:
        region = img.crop((cx, cy, cx + sample_size, cy + sample_size))
        pixels = list(region.getdata())
        colors.extend(pixels)
    return colors


def _build_mask(img: Image.Image, bg_colors: list,
                tolerance: float = 40, feather: int = 3) -> Image.Image:
    """根据背景颜色集合构建透明度蒙版"""
    if img.mode != 'RGBA':
        img = img.convert('RGBA')

    pixels = np.array(img, dtype=np.float32)
    rgb = pixels[:, :, :3]

    bg_arr = np.array([c[:3] for c in bg_colors], dtype=np.float32)
    diff = rgb[:, :, np.newaxis, :] - bg_arr[np.newaxis, np.newaxis, :, :]
    dist = np.sqrt(np.sum(diff ** 2, axis=-1))
    min_dist = np.min(dist, axis=-1)

    alpha = np.clip((min_dist - tolerance * 0.3) / (tolerance * 0.7), 0, 1)
    alpha = (alpha * 255).astype(np.uint8)

    if feather > 0:
        from PIL import ImageFilter
        alpha_img = Image.fromarray(alpha, mode='L')
        for _ in range(feather):
            alpha_img = alpha_img.filter(ImageFilter.SMOOTH)
        alpha = np.array(alpha_img, dtype=np.uint8)

    pixels[:, :, 3] = alpha
    result = Image.fromarray(pixels.astype(np.uint8), mode='RGBA')
    return result


def remove_background(input_path: str, tolerance: int = 40) -> dict:
    """去除图片背景

    策略：从四角采样背景颜色 → 颜色距离计算 → alpha 蒙版
    返回的 dict 中只包含 PNG 字节数据，不含 QPixmap（由主线程生成）。

    Returns
    -------
    result : dict
        file_path, file_name, original_size,
        orig_data (PNG bytes), result_data (PNG with transparency),
        width, height, tolerance
    """
    img = Image.open(input_path).convert('RGBA')
    orig_size = os.path.getsize(input_path)

    # 采样四角颜色
    bg_colors = _sample_corner_colors(img)

    if len(bg_colors) > 10:
        bg_arr = np.array(bg_colors, dtype=np.float32)
        median_r = np.median(bg_arr[:, 0])
        median_g = np.median(bg_arr[:, 1])
        median_b = np.median(bg_arr[:, 2])
        filtered = []
        for c in bg_colors:
            d = abs(c[0] - median_r) + abs(c[1] - median_g) + abs(c[2] - median_b)
            if d < 100:
                filtered.append(c)
        if filtered:
            bg_colors = filtered

    result_img = _build_mask(img, bg_colors, tolerance=tolerance, feather=2)

    # 原图缩略图 (PNG bytes)
    thumb = img.copy()
    thumb.thumbnail((200, 200))
    buf = io.BytesIO()
    thumb.save(buf, format='PNG')
    orig_thumb_data = buf.getvalue()

    # 结果缩略图 (PNG bytes)
    res_thumb = result_img.copy()
    res_thumb.thumbnail((200, 200))
    buf2 = io.BytesIO()
    res_thumb.save(buf2, format='PNG')
    res_thumb_data = buf2.getvalue()

    # 完整结果
    out_buf = io.BytesIO()
    result_img.save(out_buf, format='PNG', optimize=True)
    out_buf.seek(0)

    w, h = result_img.size
    img.close()

    return {
        'file_path': input_path,
        'file_name': Path(input_path).name,
        'orig_data': orig_thumb_data,          # PNG bytes, 主线程转 QPixmap
        'result_thumb_data': res_thumb_data,    # PNG bytes, 主线程转 QPixmap
        'data': out_buf.getvalue(),             # 完整结果 PNG bytes
        'width': w,
        'height': h,
        'original_size': orig_size,
        'tolerance': tolerance,
    }


# ============================================================
# 工作线程
class RemoveBgWorker(QThread):
    """批量背景去除的工作线程"""
    progress_update = Signal(int, int)
    single_finished = Signal(dict)
    all_finished = Signal(list)

    def __init__(self, file_paths, tolerance=40, parent=None):
        super().__init__(parent)
        self.file_paths = file_paths
        self.tolerance = tolerance
        self._cancelled = False
        self.results = []

    def cancel(self):
        self._cancelled = True

    def run(self):
        self.results = []
        total = len(self.file_paths)
        for i, path in enumerate(self.file_paths):
            if self._cancelled:
                break
            try:
                result = remove_background(path, tolerance=self.tolerance)
                self.results.append(result)
                self.single_finished.emit(result)
            except Exception as e:
                print(f"[抠图错误] {path}: {e}")
            self.progress_update.emit(i + 1, total)
        self.all_finished.emit(self.results)


# ============================================================
# 导出工具
def save_removebg_result(result: dict, save_path: str):
    with open(save_path, 'wb') as f:
        f.write(result['data'])


def save_removebg_all(results: list, folder: str, prefix: str) -> list:
    if not results:
        return []
    saved = []
    for i, r in enumerate(results, 1):
        name = f"{prefix}{i:03d}.png"
        path = os.path.join(folder, name)
        save_removebg_result(r, path)
        saved.append(path)
    return saved


def save_removebg_zip(results: list, save_path: str, prefix: str) -> str:
    if not results:
        return ''
    with zipfile.ZipFile(save_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for i, r in enumerate(results, 1):
            name = f"{prefix}{i:03d}.png"
            zf.writestr(name, r['data'])
    return save_path
