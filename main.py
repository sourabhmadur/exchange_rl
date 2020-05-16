from environment.env import Exchange
IPO = {"S1": (10, 2000)}  # price, qty
e = Exchange(2, 100000, IPO)  # 2 agents
# e.place_add_order('T1', "S1", buy_sell='buy', qty=2000, price=10) # 1st agent buying
stock_price = e.stocks['S1']._last_settled_price
print(stock_price)