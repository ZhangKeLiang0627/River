# coding:utf-8
import os
import io
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QPixmap

# ============================================================
# 支持的图片格式
SUPPORTED_FORMATS = ['PNG', 'JPG', 'JPEG', 'GIF', 'BMP', 'WEBP']

# 预设文件大小限制选项
SIZE_LIMITS = [
    ('不限制', 0),
    ('< 100 KB', 100 * 1024),
    ('< 200 KB', 200 * 1024),
    ('< 500 KB', 500 * 1024),
    ('< 1 MB', 1024 * 1024),
]


def format_size(size_bytes: int) -> str:
    """格式化显示文件大小"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def _normalize_format(fmt: str) -> str:
    """统一格式名称：JPG/JPEG 统一为 JPEG"""
    return 'JPEG' if fmt.upper() in ('JPG', 'JPEG') else fmt.upper()


def _format_dimensions(w: int, h: int) -> str:
    return f"{w} × {h}"


# ============================================================
# 转换工作线程
class ConvertWorker(QThread):
    """后台执行图片转换的线程"""
    progress_update = Signal(int, int)  # current_index, total_count
    single_finished = Signal(dict)     # 单张图片转换结果
    all_finished = Signal(list)        # 全部完成，返回结果列表

    def __init__(self, file_paths, target_format, quality, size_limit_bytes, parent=None):
        super().__init__(parent)
        self.file_paths = file_paths
        self.target_format = _normalize_format(target_format)
        self.quality = quality
        self.size_limit_bytes = size_limit_bytes
        self._cancelled = False
        self.results = []

    def cancel(self):
        self._cancelled = True

    def run(self):
        self.results = []
        total = len(self.file_paths)

        for i, file_path in enumerate(self.file_paths):
            if self._cancelled:
                break

            try:
                result = self._convert_single(file_path)
                if result:
                    self.results.append(result)
                    self.single_finished.emit(result)
            except Exception as e:
                print(f"[转换错误] {file_path}: {e}")

            self.progress_update.emit(i + 1, total)

        self.all_finished.emit(self.results)

    def _convert_single(self, file_path: str) -> dict:
        """转换单张图片，返回结果字典"""
        img = Image.open(file_path)
        orig_size = os.path.getsize(file_path)
        orig_fmt = _normalize_format(Path(file_path).suffix[1:])
        target_fmt = self.target_format

        # ------ 色彩模式处理 ------
        # JPEG/BMP 不支持 alpha 通道 → 合入白色背景
        if target_fmt in ('JPEG', 'BMP') and img.mode in ('RGBA', 'LA', 'P'):
            if img.mode == 'P':
                img = img.convert('RGBA')
            bg = Image.new('RGB', img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[3] if img.mode == 'RGBA' else None)
            img = bg
        elif target_fmt in ('JPEG', 'BMP') and img.mode not in ('RGB', 'L'):
            img = img.convert('RGB')
        elif target_fmt == 'GIF' and img.mode not in ('P', 'L', 'RGB'):
            img = img.convert('RGB')

        # ------ 文件大小控制 ------
        quality = self.quality
        if self.size_limit_bytes > 0 and target_fmt in ('JPEG', 'WEBP'):
            quality = self._find_quality_for_target(img, target_fmt, self.size_limit_bytes)

        # ------ 保存到内存缓冲 ------
        buf = io.BytesIO()
        save_kwargs = {}

        if target_fmt == 'JPEG':
            if img.mode == 'RGBA':
                bg = Image.new('RGB', img.size, (255, 255, 255))
                bg.paste(img, mask=img.split()[3])
                img = bg
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            save_kwargs = {'quality': quality, 'optimize': True}
            img.save(buf, format='JPEG', **save_kwargs)

        elif target_fmt == 'PNG':
            save_kwargs = {'optimize': True}
            img.save(buf, format='PNG', **save_kwargs)

        elif target_fmt == 'WEBP':
            save_kwargs = {'quality': quality}
            img.save(buf, format='WEBP', **save_kwargs)

        elif target_fmt == 'GIF':
            if img.mode not in ('P', 'L'):
                img = img.quantize(colors=256, method=Image.MEDIANCUT)
            img.save(buf, format='GIF', optimize=True)

        elif target_fmt == 'BMP':
            img.save(buf, format='BMP')

        conv_size = buf.tell()
        buf.seek(0)

        # 生成 QPixmap（在子线程创建后 emit 到主线程）
        pixmap = QPixmap()
        pixmap.loadFromData(buf.getvalue())

        src_w, src_h = img.size

        return {
            'file_path': file_path,
            'file_name': Path(file_path).name,
            'original_size': orig_size,
            'original_format': orig_fmt,
            'converted_data': buf.getvalue(),
            'converted_size': conv_size,
            'target_format': target_fmt,
            'pixmap': pixmap,
            'width': src_w,
            'height': src_h,
        }

    def _find_quality_for_target(self, img, fmt, target_bytes, max_iter=10):
        """二分查找满足文件大小上限的品质值（仅 JPEG / WebP）"""
        lo, hi = 1, 100
        best = hi

        for _ in range(max_iter):
            mid = (lo + hi) // 2
            buf = io.BytesIO()
            save_img = img
            if fmt == 'JPEG':
                if save_img.mode == 'RGBA':
                    bg = Image.new('RGB', save_img.size, (255, 255, 255))
                    bg.paste(save_img, mask=save_img.split()[3])
                    save_img = bg
                elif save_img.mode not in ('RGB', 'L'):
                    save_img = save_img.convert('RGB')
                save_img.save(buf, format='JPEG', quality=mid, optimize=True)
            else:  # WEBP
                save_img.save(buf, format='WEBP', quality=mid)
            size = buf.tell()

            if size <= target_bytes:
                best = mid
                lo = mid + 1
            else:
                hi = mid - 1
            if lo > hi:
                break

        return best
