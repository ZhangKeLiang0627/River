# coding:utf-8
import os
import io
import zipfile
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QPixmap


# ============================================================
# GIF 信息工具
def get_gif_info(file_path: str) -> dict:
    """获取 GIF 基本信息"""
    img = Image.open(file_path)
    info = {
        'file_path': file_path,
        'file_name': Path(file_path).name,
        'file_size': os.path.getsize(file_path),
        'width': img.width,
        'height': img.height,
        'frame_count': getattr(img, 'n_frames', 1),
    }
    # 尝试读取帧持续时间
    try:
        img.seek(0)
        duration = img.info.get('duration', 0)
        info['duration'] = duration
    except Exception:
        info['duration'] = 0
    img.close()
    return info


# ============================================================
# GIF 压缩
def _make_thumbnail(img: Image.Image, max_size: int = 200) -> QPixmap:
    """从 PIL Image 生成 QPixmap 缩略图"""
    thumb = img.copy()
    thumb.thumbnail((max_size, max_size))
    buf = io.BytesIO()
    thumb.save(buf, format='PNG')
    pixmap = QPixmap()
    pixmap.loadFromData(buf.getvalue())
    return pixmap


def compress_gif(input_path: str, colors: int = 256,
                 max_width: int = 0, max_height: int = 0) -> dict:
    """压缩单个 GIF 文件

    Parameters
    ----------
    input_path : str
        源文件路径
    colors : int
        颜色数 (2~256)
    max_width, max_height : int
        最大宽/高限制（0 表示不限制）

    Returns
    -------
    result : dict
        file_name, original_size, compressed_size, frame_count,
        width, height, data, pixmap 等
    """
    orig_size = os.path.getsize(input_path)
    img = Image.open(input_path)
    frames = []
    duration = []

    # 遍历所有帧
    try:
        while True:
            frames.append(img.copy())
            duration.append(img.info.get('duration', 100))
            img.seek(img.tell() + 1)
    except EOFError:
        pass

    # 缩放
    if max_width > 0 or max_height > 0:
        new_frames = []
        for f in frames:
            f.thumbnail((max_width or f.width, max_height or f.height),
                        Image.LANCZOS)
            # 转为 P 模式以保持 GIF 兼容
            if f.mode != 'P':
                f = f.quantize(colors=min(colors, 256))
            new_frames.append(f)
        frames = new_frames

    # 颜色量化
    if colors < 256:
        quantized = []
        for f in frames:
            if f.mode == 'P' and len(f.getpalette()) // 3 <= colors:
                quantized.append(f)
            else:
                quantized.append(f.quantize(colors=colors))
        frames = quantized

    w, h = frames[0].size if frames else (0, 0)
    frame_count = len(frames)

    # 保存到内存
    out_buf = io.BytesIO()
    if frame_count == 1:
        frames[0].save(out_buf, format='GIF', optimize=True)
    else:
        frames[0].save(
            out_buf,
            format='GIF',
            save_all=True,
            append_images=frames[1:],
            optimize=True,
            duration=duration,
            loop=0,
        )
    compressed_size = out_buf.tell()
    out_buf.seek(0)

    # 缩略图
    pixmap = _make_thumbnail(frames[0])

    return {
        'type': 'compress',
        'file_path': input_path,
        'file_name': Path(input_path).name,
        'original_size': orig_size,
        'compressed_size': compressed_size,
        'data': out_buf.getvalue(),
        'width': w,
        'height': h,
        'frame_count': frame_count,
        'pixmap': pixmap,
        'compress_ratio': compressed_size / orig_size if orig_size > 0 else 1,
    }


# ============================================================
# GIF 提取帧
def extract_gif_frames(input_path: str, output_format: str = 'PNG',
                       frame_interval: int = 1) -> list:
    """提取 GIF 的每一帧

    Parameters
    ----------
    input_path : str
        源文件路径
    output_format : str
        输出图片格式 (PNG / JPEG)
    frame_interval : int
        帧间隔，每隔 N 帧提取一帧

    Returns
    -------
    frames : list[dict]
        每帧的 file_name, pixmap, data, index, original_size 等
    """
    img = Image.open(input_path)
    frames = []
    try:
        idx = 0
        while True:
            img.seek(idx)
            if idx % frame_interval == 0:
                frame = img.copy()

                # JPEG / BMP 需要合入白色背景
                target_fmt = output_format.upper()
                if target_fmt in ('JPEG', 'BMP') and frame.mode in ('RGBA', 'P', 'LA'):
                    if frame.mode == 'P':
                        frame = frame.convert('RGBA')
                    bg = Image.new('RGB', frame.size, (255, 255, 255))
                    bg.paste(frame, mask=frame.split()[3] if frame.mode == 'RGBA' else None)
                    frame = bg
                elif target_fmt in ('JPEG', 'BMP') and frame.mode not in ('RGB', 'L'):
                    frame = frame.convert('RGB')

                buf = io.BytesIO()
                save_kwargs = {}
                if target_fmt == 'JPEG':
                    save_kwargs = {'quality': 95, 'optimize': True}
                elif target_fmt == 'PNG':
                    save_kwargs = {'optimize': True}
                frame.save(buf, format=target_fmt, **save_kwargs)
                buf.seek(0)

                pixmap = QPixmap()
                pixmap.loadFromData(buf.getvalue())

                frame_info = {
                    'type': 'extract',
                    'source_file': input_path,
                    'file_name': f"{Path(input_path).stem}_frame{idx:04d}.{output_format.lower()}",
                    'index': idx,
                    'data': buf.getvalue(),
                    'width': frame.width,
                    'height': frame.height,
                    'pixmap': pixmap,
                    'original_size': 0,
                }
                frames.append(frame_info)
                buf.close()

            idx += 1
    except EOFError:
        pass
    finally:
        img.close()

    return frames


# ============================================================
# 工作线程：GIF 压缩
class GifCompressWorker(QThread):
    """批量压缩 GIF 的工作线程"""
    progress_update = Signal(int, int)
    single_finished = Signal(dict)
    all_finished = Signal(list)

    def __init__(self, file_paths, colors=256,
                 max_width=0, max_height=0, parent=None):
        super().__init__(parent)
        self.file_paths = file_paths
        self.colors = colors
        self.max_width = max_width
        self.max_height = max_height
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
                result = compress_gif(
                    path, colors=self.colors,
                    max_width=self.max_width, max_height=self.max_height)
                self.results.append(result)
                self.single_finished.emit(result)
            except Exception as e:
                print(f"[GIF 压缩错误] {path}: {e}")
            self.progress_update.emit(i + 1, total)
        self.all_finished.emit(self.results)


# 工作线程：GIF 提取帧
class GifExtractWorker(QThread):
    """提取 GIF 帧的工作线程"""
    progress_update = Signal(int, int)
    single_finished = Signal(dict)
    all_finished = Signal(list)

    def __init__(self, file_paths, output_format='PNG',
                 frame_interval=1, parent=None):
        super().__init__(parent)
        self.file_paths = file_paths
        self.output_format = output_format
        self.frame_interval = frame_interval
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
                frames = extract_gif_frames(
                    path, output_format=self.output_format,
                    frame_interval=self.frame_interval)
                for f in frames:
                    self.results.append(f)
                    self.single_finished.emit(f)
            except Exception as e:
                print(f"[GIF 提取帧错误] {path}: {e}")
            self.progress_update.emit(i + 1, total)
        self.all_finished.emit(self.results)


# ============================================================
# 导出工具
def save_gif_result(result: dict, save_path: str):
    """将单张压缩/提取结果写入文件"""
    with open(save_path, 'wb') as f:
        f.write(result['data'])


def save_gif_results_all(results: list, folder: str, prefix: str) -> list:
    """批量保存结果到目录"""
    if not results:
        return []
    saved = []
    for i, r in enumerate(results, 1):
        ext = 'gif' if r.get('type') == 'compress' else 'png'
        name = f"{prefix}{i:03d}.{ext}"
        path = os.path.join(folder, name)
        save_gif_result(r, path)
        saved.append(path)
    return saved


def save_gif_results_zip(results: list, save_path: str, prefix: str) -> str:
    """将所有结果打包为 ZIP"""
    if not results:
        return ''
    with zipfile.ZipFile(save_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for i, r in enumerate(results, 1):
            ext = 'gif' if r.get('type') == 'compress' else 'png'
            name = f"{prefix}{i:03d}.{ext}"
            zf.writestr(name, r['data'])
    return save_path
