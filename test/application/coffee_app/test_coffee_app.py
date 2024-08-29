import test
from zzz_od.application.coffee.coffee_app import CoffeeApp


class TestCoffeeApp(test.ZzzTestBase):

    def __init__(self, *args, **kwargs):
        test.ZzzTestBase.__init__(self, *args, **kwargs)

    def test_without_benefit_confirm(self):
        """
        无增益效果的咖啡的确认
        """
        self.mock_screenshot('without_benefit_confirm.png')
        op = CoffeeApp(self.ctx)
        result = op.without_benefit_confirm()
        self.assertTrue(result.is_success)
