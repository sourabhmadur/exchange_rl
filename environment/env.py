
import time
import pprint
import random
import bisect


class Agent(object):
    def __init__(self, ID, initial_funds, stocks):
        self.ID = ID
        self.total_funds = initial_funds        # total funds are the cash at hand available with the agent
        self.effective_funds = initial_funds
        self.portfolio = {k: [v, 0, 0] for k, v in stocks.items()}
        self.order_no = 1

    def get_portfolio(self):
        return {k: v[1:] for k, v in self.portfolio.items()}

    def get_value(self, stock):
        current_price = self.portfolio[stock][0].get_price()
        if current_price is not None:
            return self.portfolio[stock][0].get_price() * self.portfolio[stock][1]
    
    def get_total_portfolio_value(self):
        value_from_stocks=0
        for stock in self.portfolio.keys():
            value_from_stocks+=self.get_value(stock)
        return self.total_funds+value_from_stocks

    def make_add_order(self, stock, buy_sell='buy', qty=1, price=None):
        if price == None:
            price = self.portfolio[stock][0].get_price()  # use the market price if price not provided

        if price != None:
            return {'order_id': 'T' + str(self.ID) + '_' + str(self.order_no), 'timestamp': time.clock(), 'type': 'add',
                    'quantity': qty, 'side': buy_sell, 'price': price}
        else:
            print("Error: Price is None")

    def place_order(self, stock, order):
        if order['side'] == 'buy':
            if self.effective_funds >= order['price'] * order['quantity']:
                self.effective_funds -= order['price'] * order['quantity']
                self.order_no += 1
                return self.portfolio[stock][0].process_order(order)
            else:
                print("Not enough effective funds to place order")
        elif order['side'] == 'sell':
            if self.portfolio[stock][2] >= order['quantity']:
                self.portfolio[stock][2] -= order['quantity']
                self.order_no += 1
                return self.portfolio[stock][0].process_order(order)
            else:
                print("Not enough effective qty to place order. Available effective qty = ", self.portfolio[stock][2])



class Exchange(object):

    def __init__(self, num_agents, initial_money, IPO):
        self.stocks = {"S" + str(i): Orderbook() for i in range(1, len(IPO) + 1)}
        self.agents = {"T" + str(i): Agent(i, initial_money, self.stocks) for i in range(1, num_agents + 1)}

        self.agents["T-1"] = Agent(-1, 0, self.stocks)

        # initializing the IPO agent's portfolio with stocks
        for stock in self.stocks.keys():
            self.agents["T-1"].portfolio[stock][1] = IPO[stock][1]
            self.agents["T-1"].portfolio[stock][2] = IPO[stock][1]
            self.place_add_order("T-1", stock, buy_sell='sell', qty=IPO[stock][1], price=IPO[stock][0])

        # print(self.get_agents_status())

    def get_agents_status(self):
        d = {}
        for agent, data in self.agents.items():
            d[agent] = (data.total_funds, data.effective_funds, data.get_portfolio())

        return d

    def get_total_funds(self, agent):
        return self.agents[agent].total_funds

    def get_effective_funds(self, agent):
        return self.agents[agent].effective_funds

    def get_portfolio(self, agent):
        return self.agents[agent].get_portfolio()

    def place_add_order(self, agent, stock, buy_sell='buy', qty=1, price=None):
        if qty<=0 or price<=0:
            return None
        o = self.agents[agent].make_add_order(stock, buy_sell, qty, price)
        trades = self.agents[agent].place_order(stock, o)
        # print(trades)

        if trades != None:
            for trade in trades:
                io = self.stocks[stock].order_history[trade['incoming_order_id']]
                ro = self.stocks[stock].order_history[trade['resting_order_id']]
                io_t = io['order_id'].split('_')[0]
                ro_t = ro['order_id'].split('_')[0]

                self.do_bookkeeping(io_t, stock, trade, io)
                self.do_bookkeeping(ro_t, stock, trade, ro)

        return trades

    def place_delta_add_order(self, agent, new_portfolio):
        if new_portfolio==e.get_portfolio(agent):
            return
        current_portfolio = e.get_portfolio(agent)
        assert (len(new_portfolio) == len(current_portfolio))

        for stock, qty in current_portfolio.items():
            diff = new_portfolio[stock] - qty[1]
            if diff > 0:  # need to place buy orders
                self.place_add_order(agent, stock, buy_sell='buy', qty=diff)
            elif diff < 0:  # need to place sell orders
                self.place_add_order(agent, stock, buy_sell='sell', qty=-diff)

    def do_bookkeeping(self, agent, stock, trade, orignal_order):
        if orignal_order['side'] == 'buy' and orignal_order['type'] == 'add':
            self.agents[agent].effective_funds += trade['quantity'] * orignal_order['price']
            self.agents[agent].effective_funds -= trade['quantity'] * trade['price']
            self.agents[agent].total_funds -= trade['quantity'] * trade['price']
            self.agents[agent].portfolio[stock][1] += trade['quantity']
            self.agents[agent].portfolio[stock][2] += trade['quantity']
        elif orignal_order['side'] == 'sell' and orignal_order['type'] == 'add':
            self.agents[agent].effective_funds += trade['quantity'] * trade['price']
            self.agents[agent].total_funds += trade['quantity'] * trade['price']
            self.agents[agent].portfolio[stock][1] -= trade['quantity']

    def get_order_book(self, stock):
        return (self.stocks[stock]._bid_book, self.stocks[stock]._ask_book)



class Orderbook(object):
    """
    Orderbook tracks, processes and matches orders.

    Orderbook is a set of linked lists and dictionaries containing trades, bids and asks.
    One dictionary contains a history of all orders;
    two other dictionaries contain priced bid and ask orders with linked lists for access;
    one dictionary contains trades matched with orders on the book.
    Orderbook also provides methods for storing and retrieving orders and maintaining a
    history of the book.
    Public attributes: order_history, confirm_modify_collector, confirm_trade_collector,
    trade_book and traded.
    Public methods: add_order_to_book(), process_order(), order_history_to_h5(), trade_book_to_h5(),
    sip_to_h5() and report_top_of_book()
    """

    def __init__(self):
        '''
        Initialize the Orderbook with a set of empty lists and dicts and other defaults

        order_history is a list of all incoming orders (dicts) in the order received
        _bid_book_prices and _ask_book_prices are linked (sorted) lists of bid and ask prices
        which serve as pointers to:
        _bid_book and _ask_book: dicts of current order book state and OrderedDicts of orders
        the OrderedDicts maintain time priority for each order at a given price.
        confirm_modify_collector and confirm_trade_collector are lists that carry information (dicts) from the
        order processor and/or matching engine to the traders
        trade_book is a list if trades in sequence
        _order_index identifies the sequence of orders in event time
        '''
        self.order_history = dict()
        self._bid_book = {}
        self._bid_book_prices = []
        self._ask_book = {}
        self._ask_book_prices = []
        self.confirm_modify_collector = []
        self.confirm_trade_collector = []
        self._sip_collector = []
        self.trade_book = []
        self._order_index = 0
        self.traded = False
        self._last_settled_price = None

    def _add_order_to_history(self, order):
        '''Add an order (dict) to order_history'''
        hist_order = {'order_id': order['order_id'], 'timestamp': order['timestamp'], 'type': order['type'],
                      'quantity': order['quantity'], 'side': order['side'], 'price': order['price']}
        self._order_index += 1
        hist_order['exid'] = self._order_index
        self.order_history[order['order_id']] = hist_order

    def add_order_to_book(self, order):
        '''
        Use insort to maintain on ordered list of prices which serve as pointers
        to the orders.
        '''
        book_order = {'order_id': order['order_id'], 'timestamp': order['timestamp'], 'type': order['type'],
                      'quantity': order['quantity'], 'side': order['side'], 'price': order['price']}
        if order['side'] == 'buy':
            book_prices = self._bid_book_prices
            book = self._bid_book
        else:
            book_prices = self._ask_book_prices
            book = self._ask_book
        if order['price'] in book_prices:
            book[order['price']]['num_orders'] += 1
            book[order['price']]['size'] += order['quantity']
            book[order['price']]['order_ids'].append(order['order_id'])
            book[order['price']]['orders'][order['order_id']] = book_order
        else:
            bisect.insort(book_prices, order['price'])
            book[order['price']] = {'num_orders': 1, 'size': order['quantity'], 'order_ids': [order['order_id']],
                                    'orders': {order['order_id']: book_order}}

    def _remove_order(self, order_side, order_price, order_id):
        '''Pop the order_id; if  order_id exists, updates the book.'''
        if order_side == 'buy':
            book_prices = self._bid_book_prices
            book = self._bid_book
        else:
            book_prices = self._ask_book_prices
            book = self._ask_book
        is_order = book[order_price]['orders'].pop(order_id, None)
        if is_order:
            book[order_price]['num_orders'] -= 1
            book[order_price]['size'] -= is_order['quantity']
            book[order_price]['order_ids'].remove(is_order['order_id'])
            if book[order_price]['num_orders'] == 0:
                book_prices.remove(order_price)

    def _modify_order(self, order_side, order_quantity, order_id, order_price):
        '''Modify order quantity; if quantity is 0, removes the order.'''
        book = self._bid_book if order_side == 'buy' else self._ask_book
        if order_quantity < book[order_price]['orders'][order_id]['quantity']:
            book[order_price]['size'] -= order_quantity
            book[order_price]['orders'][order_id]['quantity'] -= order_quantity
        else:
            self._remove_order(order_side, order_price, order_id)

    def _add_trade_to_book(self, resting_order_id, resting_timestamp, incoming_order_id, timestamp, price, quantity,
                           side):
        '''Add trades (dicts) to the trade_book list.'''
        trade = {'resting_order_id': resting_order_id, 'resting_timestamp': resting_timestamp,
                 'incoming_order_id': incoming_order_id, 'timestamp': timestamp, 'price': price,
                 'quantity': quantity, 'side': side}
        self.trade_book.append(trade)
        return trade

    def _confirm_trade(self, timestamp, order_side, order_quantity, order_id, order_price):
        '''Add trade confirmation to confirm_trade_collector list.'''
        trader = order_id.partition('_')[0]
        self.confirm_trade_collector.append({'timestamp': timestamp, 'trader': trader, 'order_id': order_id,
                                             'quantity': order_quantity, 'side': order_side, 'price': order_price})

    def _confirm_modify(self, timestamp, order_side, order_quantity, order_id):
        '''Add modify confirmation to confirm_modify_collector list.'''
        trader = order_id.partition('_')[0]
        self.confirm_modify_collector.append({'timestamp': timestamp, 'trader': trader, 'order_id': order_id,
                                              'quantity': order_quantity, 'side': order_side})

    def process_order(self, order):
        '''Check for a trade (match); if so call _match_trade, otherwise modify book(s).'''
        self.confirm_modify_collector.clear()
        self.traded = False
        self._add_order_to_history(order)
        if order['type'] == 'add':
            if order['side'] == 'buy':
                if len(self._ask_book_prices) > 0:
                    if order['price'] >= self._ask_book_prices[0]:
                        return self._match_trade(order)
                    else:
                        self.add_order_to_book(order)
                else:
                    self.add_order_to_book(order)
            else:  # order['side'] == 'sell'
                if len(self._bid_book_prices) > 0:
                    if order['price'] <= self._bid_book_prices[-1]:
                        return self._match_trade(order)
                    else:
                        self.add_order_to_book(order)
                else:
                    self.add_order_to_book(order)
        else:
            book_prices = self._bid_book_prices if order['side'] == 'buy' else self._ask_book_prices
            if order['price'] in book_prices:
                book = self._bid_book if order['side'] == 'buy' else self._ask_book
                if order['order_id'] in book[order['price']]['orders']:
                    self._confirm_modify(order['timestamp'], order['side'], order['quantity'], order['order_id'])
                    if order['type'] == 'cancel':
                        self._remove_order(order['side'], order['price'], order['order_id'])
                    else:  # order['type'] == 'modify'
                        self._modify_order(order['side'], order['quantity'], order['order_id'], order['price'])

    def _match_trade(self, order):
        '''Match orders to generate trades, update books.'''
        matched_trades = []
        self.traded = True
        self.confirm_trade_collector.clear()
        if order['side'] == 'buy':
            book_prices = self._ask_book_prices
            book = self._ask_book
            remainder = order['quantity']
            while remainder > 0:
                if book_prices:
                    price = book_prices[0]
                    if order['price'] >= price:
                        book_order_id = book[price]['order_ids'][0]
                        book_order = book[price]['orders'][book_order_id]
                        self._last_settled_price = book_order['price']
                        if remainder >= book_order['quantity']:
                            self._confirm_trade(order['timestamp'], book_order['side'], book_order['quantity'],
                                                book_order['order_id'], book_order['price'])
                            t = self._add_trade_to_book(book_order['order_id'], book_order['timestamp'],
                                                        order['order_id'], order['timestamp'], book_order['price'],
                                                        book_order['quantity'], order['side'])
                            matched_trades.append(t)
                            self._remove_order(book_order['side'], book_order['price'], book_order['order_id'])
                            remainder -= book_order['quantity']
                        else:
                            self._confirm_trade(order['timestamp'], book_order['side'], remainder,
                                                book_order['order_id'], book_order['price'])
                            t = self._add_trade_to_book(book_order['order_id'], book_order['timestamp'],
                                                        order['order_id'], order['timestamp'], book_order['price'],
                                                        remainder, order['side'])
                            matched_trades.append(t)
                            self._modify_order(book_order['side'], remainder, book_order['order_id'],
                                               book_order['price'])
                            break
                    else:
                        order['quantity'] = remainder
                        self.add_order_to_book(order)
                        break
                else:
                    print('Ask Market Collapse with order {0}'.format(order))
                    break
        else:  # order['side'] =='sell'
            book_prices = self._bid_book_prices
            book = self._bid_book
            remainder = order['quantity']
            while remainder > 0:
                if book_prices:
                    price = book_prices[-1]
                    if order['price'] <= price:
                        book_order_id = book[price]['order_ids'][0]
                        book_order = book[price]['orders'][book_order_id]
                        self._last_settled_price = book_order['price']
                        if remainder >= book_order['quantity']:
                            self._confirm_trade(order['timestamp'], book_order['side'], book_order['quantity'],
                                                book_order['order_id'], book_order['price'])
                            t = self._add_trade_to_book(book_order['order_id'], book_order['timestamp'],
                                                        order['order_id'], order['timestamp'], book_order['price'],
                                                        book_order['quantity'], order['side'])
                            matched_trades.append(t)
                            self._remove_order(book_order['side'], book_order['price'], book_order['order_id'])
                            remainder -= book_order['quantity']
                        else:
                            self._confirm_trade(order['timestamp'], book_order['side'], remainder,
                                                book_order['order_id'], book_order['price'])
                            t = self._add_trade_to_book(book_order['order_id'], book_order['timestamp'],
                                                        order['order_id'], order['timestamp'], book_order['price'],
                                                        remainder, order['side'])
                            matched_trades.append(t)
                            self._modify_order(book_order['side'], remainder, book_order['order_id'],
                                               book_order['price'])
                            break
                    else:
                        order['quantity'] = remainder
                        self.add_order_to_book(order)
                        break
                else:
                    print('Bid Market Collapse with order {0}'.format(order))
                    break

        return matched_trades

    def order_history_to_h5(self, filename):
        '''Append order history to an h5 file, clear the order_history'''
        temp_df = pd.DataFrame(self.order_history)
        temp_df.to_hdf(filename, 'orders', append=True, format='table', complevel=5, complib='blosc',
                       min_itemsize={'order_id': 12})
        self.order_history.clear()

    def trade_book_to_h5(self, filename):
        '''Append trade_book to an h5 file, clear the trade_book'''
        temp_df = pd.DataFrame(self.trade_book)
        temp_df.to_hdf(filename, 'trades', append=True, format='table', complevel=5, complib='blosc',
                       min_itemsize={'resting_order_id': 12, 'incoming_order_id': 12})
        self.trade_book.clear()

    def sip_to_h5(self, filename):
        '''Append _sip_collector to an h5 file, clear the _sip_collector'''
        temp_df = pd.DataFrame(self._sip_collector)
        temp_df.to_hdf(filename, 'tob', append=True, format='table', complevel=5, complib='blosc')
        self._sip_collector.clear()

    def report_top_of_book(self, now_time):
        '''Update the top-of-book prices and sizes'''
        best_bid_price = self._bid_book_prices[-1]
        best_bid_size = self._bid_book[best_bid_price]['size']
        best_ask_price = self._ask_book_prices[0]
        best_ask_size = self._ask_book[best_ask_price]['size']
        tob = {'timestamp': now_time, 'best_bid': best_bid_price, 'best_ask': best_ask_price, 'bid_size': best_bid_size,
               'ask_size': best_ask_size}
        self._sip_collector.append(tob)
        return tob

    def describe(self):
        pp = pprint.PrettyPrinter(indent=1)
        print("Order History")
        pp.pprint(self.order_history)
        print("\nBid Book")
        pp.pprint(self._bid_book)
        print("\nBid Book Prices")
        pp.pprint(self._bid_book_prices)
        print("\nAsk Book")
        pp.pprint(self._ask_book)
        print("\nAsk Book Prices")
        pp.pprint(self._ask_book_prices)
        print("\nConfirm Modify Collector")
        pp.pprint(self.confirm_modify_collector)
        print("\nConfirm Trade Collector")
        pp.pprint(self.confirm_trade_collector)
        print("\nSip Collector")
        print(self._sip_collector)
        print("\nTrade Book")
        pp.pprint(self.trade_book)
        print("\nOrder Index")
        pp.pprint(self._order_index)
        print("\nTraded")
        pp.pprint(self.traded)

    def get_price(self):
        return self._last_settled_price


