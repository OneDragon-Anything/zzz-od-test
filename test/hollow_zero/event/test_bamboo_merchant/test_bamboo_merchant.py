import test
from zzz_od.hollow_zero.event.bamboo_merchant import BambooMerchant


class TestChooseSimUniNum(test.ZzzTestBase):

    def __init__(self, *args, **kwargs):
        test.ZzzTestBase.__init__(self, *args, **kwargs)

    def test_discount(self):
        """
        有折扣的时候 价格都是0
        """
        screen = self.get_test_image('0.png')
        op = BambooMerchant(self.ctx)
        ocr_result_map = op._ocr_price_area(screen)
        self.assertEqual(1, len(ocr_result_map))
        self.assertTrue('0' in ocr_result_map)

    def test_2_price(self):
        """
        显示2个价格
        """
        screen = self.get_test_image('2_price.png')
        op = BambooMerchant(self.ctx)
        ocr_result_map = op._ocr_price_area(screen)
        print(ocr_result_map)
        self.assertEqual(2, len(ocr_result_map))

    def test_no_price(self):
        """
        没有价格
        """
        screen = self.get_test_image('no_price.png')
        op = BambooMerchant(self.ctx)
        ocr_result_map = op._ocr_price_area(screen)
        self.assertEqual(0, len(ocr_result_map))
