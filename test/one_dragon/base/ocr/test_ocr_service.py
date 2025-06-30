import time

import cv2
import numpy as np

import test
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.matcher.ocr.ocr_service import OcrService
from one_dragon.base.matcher.ocr.onnx_ocr_matcher import OnnxOcrMatcher


class TestOcrService(test.ZzzTestBase):

    def __init__(self, *args, **kwargs):
        test.ZzzTestBase.__init__(self, *args, **kwargs)

        # 初始化OCR
        ocr_matcher = OnnxOcrMatcher()
        print("正在初始化OCR模型...")
        if not ocr_matcher.init_model(download_by_github=True):
            self.fail("OCR模型初始化失败，跳过测试")
        self.ocr_service =  OcrService(ocr_matcher)

    def test_basic_functionality(self):
        """测试基本功能"""
        print("=== 测试基本功能 ===")

        # 创建测试图片
        test_image = create_test_image()

        # 测试全图OCR
        print("执行全图OCR...")
        start_time = time.time()
        full_result = self.ocr_service.get_ocr_result_list(test_image)
        first_ocr_time = time.time() - start_time
        print(f"首次OCR耗时: {first_ocr_time:.3f}秒")
        print(f"识别到的文本: {[i.data for i in full_result]}")

        # 测试缓存命中
        print("再次执行全图OCR（应该命中缓存）...")
        start_time = time.time()
        cached_result = self.ocr_service.get_ocr_result_list(test_image)
        cached_ocr_time = time.time() - start_time
        print(f"缓存OCR耗时: {cached_ocr_time:.3f}秒")

        # 验证结果一致性
        self.assertTrue([i.data for i in full_result] == [i.data for i in cached_result], "缓存结果与原始结果不一致")

    def test_area_ocr(self):
        """测试区域OCR"""
        print("\n=== 测试区域OCR ===")

        # 创建测试图片
        test_image = create_test_image()

        # 定义测试区域
        left_area = Rect(0, 0, 400, 400)  # 左侧菜单区域
        right_area = Rect(450, 50, 700, 250)  # 右侧状态区域

        # 测试左侧区域OCR
        print("测试左侧区域OCR...")
        left_result = self.ocr_service.get_ocr_result_list(test_image, rect=left_area)
        print(f"左侧区域识别到的文本: {[i.data for i in left_result]}")

        # 测试右侧区域OCR
        print("测试右侧区域OCR...")
        right_result = self.ocr_service.get_ocr_result_list(test_image, rect=right_area)
        print(f"右侧区域识别到的文本: {[i.data for i in right_result]}")

        # 测试文本查找
        print("测试文本查找功能...")
        found_start = self.ocr_service.find_text_in_area(test_image, left_area, "Start Game")
        found_level = self.ocr_service.find_text_in_area(test_image, right_area, "Level")
        found_nonexistent = self.ocr_service.find_text_in_area(test_image, left_area, "NonExistent")

        print(f"在左侧区域找到'Start Game': {found_start}")
        print(f"在右侧区域找到'Level': {found_level}")
        print(f"在左侧区域找到'NonExistent': {found_nonexistent}")

        self.assertTrue(found_start, "应该能找到'Start Game'文本")
        self.assertTrue(found_level, "应该能找到'Level'文本")
        self.assertFalse(found_nonexistent, "不应该找到'NonExistent'文本")

    def test_color_range_filtering(self):
        """测试颜色范围过滤"""
        print("\n=== 测试颜色范围过滤 ===")

        # 创建测试图片
        test_image = create_test_image()

        # 测试不同颜色范围
        black_range = [[0, 0, 0], [50, 50, 50]]  # 黑色文本
        red_range = [[200, 0, 0], [255, 50, 50]]  # 红色文本

        full_area = Rect(0, 0, test_image.shape[1], test_image.shape[0])

        # 无颜色过滤
        no_filter_result = self.ocr_service.get_ocr_result_list(test_image, rect=full_area)
        print(f"无颜色过滤识别到: {len(no_filter_result)} 个文本")
        self.assertTrue(len(no_filter_result) > 0)

        # 黑色文本过滤
        black_filter_result = self.ocr_service.get_ocr_result_list(test_image, rect=full_area, color_range=black_range)
        print(f"黑色过滤识别到: {len(black_filter_result)} 个文本")
        self.assertTrue(len(black_filter_result) > 0)

        # 红色文本过滤
        red_filter_result = self.ocr_service.get_ocr_result_list(test_image, rect=full_area, color_range=red_range)
        print(f"红色过滤识别到: {len(red_filter_result)} 个文本")
        self.assertTrue(len(red_filter_result) > 0)


def create_test_image() -> np.ndarray:
    """创建测试图片"""
    # 创建一个白色背景的图片
    img = np.ones((700, 800, 3), dtype=np.uint8) * 255

    # 添加一些文本区域（模拟游戏界面）
    cv2.putText(img, "Start Game", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 3)
    cv2.putText(img, "Settings", (50, 200), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 3)
    cv2.putText(img, "Exit", (50, 300), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 3)
    cv2.putText(img, "Level 1", (500, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 0, 0), 2)
    cv2.putText(img, "Score: 1000", (500, 150), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    cv2.putText(img, "Health: 100%", (500, 200), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

    return img