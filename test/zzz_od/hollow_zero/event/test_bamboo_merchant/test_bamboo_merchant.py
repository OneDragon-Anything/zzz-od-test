from test.conftest import TestContext

from zzz_od.hollow_zero.event.bamboo_merchant import BambooMerchant


class TestChooseSimUniNum:

    def test_discount(self, test_context: TestContext):
        """
        有折扣的时候 价格都是0
        """
        screen = test_context.get_test_image('0.png')
        op = BambooMerchant(test_context)
        ocr_result_map = op._ocr_price_area(screen)
        assert 1 == len(ocr_result_map)
        assert '0' in ocr_result_map

    def test_2_price(self, test_context: TestContext):
        """
        显示2个价格
        """
        screen = test_context.get_test_image('2_price.png')
        op = BambooMerchant(test_context)
        ocr_result_map = op._ocr_price_area(screen)
        print(ocr_result_map)
        assert 2 == len(ocr_result_map)

    def test_no_price(self, test_context: TestContext):
        """
        没有价格
        """
        screen = test_context.get_test_image('no_price.png')
        op = BambooMerchant(test_context)
        ocr_result_map = op._ocr_price_area(screen)
        assert 0 == len(ocr_result_map)
