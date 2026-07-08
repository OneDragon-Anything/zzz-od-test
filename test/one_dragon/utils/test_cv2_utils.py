"""``cv2_utils.read_image`` / ``save_image`` 单元测试。

重点:中文(非 ASCII)路径读写兼容(用 ``np.fromfile``/``imencode+tofile`` 替代
``cv2.imread``/``imwrite``,后者在 Windows 走 C stdlib、中文路径会失败)。
"""

import numpy as np

from one_dragon.utils import cv2_utils


def _sample_rgb(h: int = 10, w: int = 12) -> np.ndarray:
    """构造一张每像素值不同的 RGB 测试图(便于检测往返是否保真)。"""
    img = np.zeros((h, w, 3), dtype=np.uint8)
    for y in range(h):
        for x in range(w):
            img[y, x] = [(x * 20) % 256, (y * 20) % 256, ((x + y) * 10) % 256]
    return img


def test_read_save_ascii_png(tmp_path) -> None:
    """ASCII 路径 PNG 往返:向后兼容(imdecode/fromfile 对 ASCII 同样工作)。"""
    img = _sample_rgb()
    path = tmp_path / 'ascii.png'
    cv2_utils.save_image(img, str(path))
    assert path.exists()
    back = cv2_utils.read_image(str(path))
    assert back is not None
    assert back.shape == img.shape
    assert np.array_equal(back, img)


def test_read_save_chinese_png(tmp_path) -> None:
    """中文路径 PNG 往返:内容一致(验证 cv2.imread/imwrite 中文路径失败被修)。"""
    img = _sample_rgb()
    path = tmp_path / '中文.png'
    cv2_utils.save_image(img, str(path))
    assert path.exists()
    back = cv2_utils.read_image(str(path))
    assert back is not None
    assert back.shape == img.shape
    assert np.array_equal(back, img)


def test_read_save_chinese_webp(tmp_path) -> None:
    """中文路径 WEBP 往返:shape/dtype 一致 + 近无损(q=100 实为高质量有损,非逐像素相等)。"""
    img = _sample_rgb()
    path = tmp_path / '中文.webp'
    cv2_utils.save_image(img, str(path))
    assert path.exists()
    back = cv2_utils.read_image(str(path))
    assert back is not None
    assert back.shape == img.shape
    assert back.dtype == img.dtype
    # q=100 是高质量有损(非逐像素相等;真无损要 q=101)——只验整体近似(均值接近),证往返非乱码
    assert abs(float(back.mean()) - float(img.mean())) < 5


def test_read_corrupted_returns_none(tmp_path) -> None:
    """损坏文件 → read_image 返 None(新 guard,替代旧 imread-None → image.ndim 崩溃)。"""
    path = tmp_path / '坏图.png'
    path.write_bytes(b'not an image')
    assert cv2_utils.read_image(str(path)) is None


def test_read_save_chinese_grayscale(tmp_path) -> None:
    """灰度图(ndim 2)中文路径往返,保持单通道(ndim==2 直通分支)。"""
    img = np.arange(120, dtype=np.uint8).reshape(10, 12)
    path = tmp_path / '灰度.png'
    cv2_utils.save_image(img, str(path))  # ndim 2 → 不做 RGB2BGR,直接 imencode
    back = cv2_utils.read_image(str(path))
    assert back is not None
    assert back.ndim == 2
    assert np.array_equal(back, img)
