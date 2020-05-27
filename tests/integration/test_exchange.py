import unittest

from environment.env import Exchange


class TestExchange(unittest.TestCase):
    
    
    def test_stock_price_after_IPO(self):
        """
        Test that after the initial IPO, stock price is none
        """

        IPO = {"S1": (10, 2000)}  # price, qty
        e = Exchange(2, 100000, IPO)  # 2 agents
        stock_price = e.stocks['S1']._last_settled_price

        self.assertEqual(stock_price, None)

    def test_stock_price_after_initial_fund_transfer(self):
        """
        Test that after the initial IPO, buying the stocks doesnt change stock price
        """

        IPO = {"S1": (10, 2000)}  # price, qty
        e = Exchange(2, 100000, IPO)  # 2 agents
        e.place_add_order('T1', "S1", buy_sell='buy', qty=2000, price=10) # 1st agent buying
        stock_price = e.stocks['S1']._last_settled_price

        self.assertEqual(stock_price, 10)
    
    

if __name__ == '__main__':
    unittest.main()


