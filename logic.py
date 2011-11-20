import re
import datetime
from urllib import urlencode
from threading import Lock
from multiprocessing.pool import ThreadPool
from collections import defaultdict

from twilio.rest import TwilioRestClient
twilio = TwilioRestClient()


id_lock = Lock()
ids = {'B': 0, 'S': 0, 'O': 0}
def unique_id(prefix):
    with id_lock:
        ids[prefix] += 1
        return '%s%d' % (prefix, ids[prefix])

match_number = [0]
match_lock = Lock()
def get_match_number():
    with match_lock:
        match_number[0] += 1
        return match_number[0]

stock_locks = {}
def stock_lock(stock):
    if stock in stock_locks:
        return stock_locks[stock]
    stock_locks[stock] = Lock()
    return stock_locks[stock]

class OrderBook(object):
    def __init__(self, httpclient):
        self.orders = []
        self.trades = []
        self.pool = ThreadPool(10)
        self.httpclient = httpclient

    def get_all_stocks(self):
        return set(o['symbol'] for o in self.orders)

    def orders_for_stock(self, stock):
        return [o for o in self.orders if o['symbol'] == stock]

    def reset(self):
        self.orders = []
        self.trades = []
        stock_locks.clear()
        match_number[0] = 0
        ids.update({'B': 0, 'S': 0, 'O': 0})

    def to_silanis_json(self):
        orders_len = len(self.orders)
        trades_len = len(self.trades)
        order_index = 0
        trade_index = 0
        snapshot = []
        while order_index < orders_len and trade_index < trades_len:
            o = self.orders[order_index]
            t = self.trades[trade_index]
            if o['timestamp'] <= t['timestamp']:
                snapshot.append(self._remove_keys(o, 'twilio', 'broker', 'parent'))
                order_index += 1
            else:
                snapshot.append(t)
                trade_index += 1
        if order_index >= orders_len:
            snapshot.extend(self.trades[trade_index:trades_len])
        else:
            for o in self.orders[order_index:orders_len]:
                snapshot.append(self._remove_keys(o, 'twilio', 'broker', 'parent'))
        return snapshot

    def _remove_keys(self, d, *args):
        result = defaultdict(str)
        result.update(d)
        for a in args:
            if a in result:
                del result[a]
        return result

    def add_order_async(self, order):
        self.pool.apply_async(self.add_order, args=(order,))

    def add_order(self, order):
        order['state'] = 'U'
        order['timestamp'] = datetime.datetime.now()
        with stock_lock(order['symbol']):
            self.orders.append(order)
            matches = self.matching_orders(order)
            if matches:
                order['state'] = 'F'
                shares_left = order['amount']
                if order['action'] == 'B':
                    for match in self._sorted_sell_orders(matches):
                        if match['state'] == 'F':
                            continue
                        match['state'] = 'F' 
                        if shares_left >= match['amount']:
                            self.trades.append(self._trade_execution(match, order, match['amount'], match['price']))
                            shares_left -= match['amount']
                        else:
                            self.trades.append(self._trade_execution(match, order, shares_left, match['price']))
                            self.orders.append(self._residual_order(match, match['amount'] - shares_left))
                            shares_left = 0
                            break
                elif order['action'] == 'S':
                    for match in self._sorted_buy_orders(matches):
                        if match['state'] == 'F':
                            continue
                        match['state'] = 'F'
                        if shares_left >= match['amount']:
                            self.trades.append(self._trade_execution(order, match, match['amount'], order['price']))
                            shares_left -= match['amount']
                        else:
                            self.trades.append(self._trade_execution(order, match, shares_left, order['price']))
                            self.orders.append(self._residual_order(match, match['amount'] - shares_left))
                            shares_left = 0
                            break
                if shares_left != 0:
                    self.orders.append(self._residual_order(order, shares_left))

    def _timestamp(self, o):
        return o['timestamp'] if not o['parent'] else o['parent']['timestamp']

    def _sorted_sell_orders(self, matches):
        return sorted(matches, key=lambda o: (o['price'], self._timestamp(o)))

    def _sorted_buy_orders(self, matches):
        return sorted(matches, key=lambda o: (-o['price'], self._timestamp(o)))

    def matching_orders(self, order):
        return [old for old in self.orders if self._orders_match(old, order)]

    def _trade_execution(self, seller, buyer, shares, price):
        trade = defaultdict(str)
        trade['timestamp'] = datetime.datetime.now()
        trade['matchNumber'] = get_match_number()
        trade['action'] = 'E'
        trade['amount'] = shares
        trade['symbol'] = seller['symbol']
        trade['sellOrderRef'] = seller['orderRef']
        trade['buyOrderRef'] = buyer['orderRef']
        trade['price'] = price
        self._send_notification(trade['matchNumber'], seller, shares, price)
        self._send_notification(trade['matchNumber'], buyer, shares, price)
        return trade

    def _residual_order(self, parent, shares):
        order = defaultdict(str)
        order.update(parent)
        order['state'] = 'U'
        order['timestamp'] = datetime.datetime.now()
        order['parent'] = parent['parent'] if parent['parent'] else parent
        if order['parent']:
            order['parentOrderRef'] = order['parent']['orderRef']
        order['amount'] = shares
        order['orderRef'] = unique_id('O')
        return order

    def _orders_match(self, old, new):
        pair = {'B': 'S', 'S': 'B'}
        if old['action'] != pair[new['action']]:
            return False
        condition = new['action'] == 'S'
        seller, buyer = (old, new)[condition], (new, old)[condition]
        return (old['state'] == 'U' and old['symbol'] == new['symbol'] and
                seller['price'] <= buyer['price'])

    def _send_notification(self, match_number, order, shares, price):
        params = {
            'MessageType': 'E',
            'OrderReferenceIdentifier': order['orderRef'] if not order['parent'] else order['parent']['orderRef'],
            'ExecutedShares': shares,
            'ExecutionPrice': price,
            'MatchNumber': match_number,
            'To': order['phone']
        }
        self.httpclient.fetch(order['broker'], lambda r: None, method='POST', body=urlencode(params))
        if (order['twilio'] == 'Y'):
            sms_message = 'Your order %s has been executed on for %d shares. Match number is %d. Execution price is %d.%02d per share.' % (params['OrderReferenceIdentifier'], params['ExecutedShares'], params['MatchNumber'], price / 100, price % 100)

            twilio.sms.messages.create(to=order['phone'], 
                from_='19176753626', body=sms_message)

phone_pattern = re.compile(r'\+[0-9]{1,15}$')

def validate_order(args):
    """
    Given HTTP POST parameters, return a dict with the order parameters if
    the order is valid, else return a string with the error code.
    """
    order = defaultdict(str)

    message_type = args.get_argument('MessageType', None)
    if message_type is None or message_type != 'O':
        return 'M'

    phone_number = args.get_argument('From', None)
    if phone_number is None or phone_pattern.match(phone_number) is None:
        return 'F'
    order['phone'] = phone_number

    bs = args.get_argument('BS', None)
    if bs is None or bs not in ('B', 'S'):
        return 'I'
    order['action'] = bs

    shares = args.get_argument('Shares', None)
    if shares is None:
        return 'Z'
    try:
        shares = int(shares)
    except ValueError:
        return 'Z'
    if not (0 < shares < 1000000):
        return 'Z'
    order['amount'] = shares

    stock = args.get_argument('Stock', None)
    if stock is None or not stock.isalnum() or not (3 <= len(stock) <= 8):
        return 'S'
    order['symbol'] = stock

    price = args.get_argument('Price', None)
    if price is None:
        return 'X'
    try:
        price = int(price)
    except ValueError:
        return 'X'
    if not (1 <= price <= 100000):
        return 'X'
    order['price'] = price

    twilio = args.get_argument('Twilio', None)
    if twilio is None or twilio not in ('Y', 'N'):
        return 'T'
    order['twilio'] = twilio

    address = args.get_argument('BrokerAddress', None)
    if address is None:
        return 'A'

    port = args.get_argument('BrokerPort', None)
    if port is None:
        return 'P'
    try:
        int(port)
    except ValueError:
        return 'P'

    endpoint = args.get_argument('BrokerEndpoint', None)
    if endpoint is None:
        return 'E'
    order['broker'] = ('http://%s:%s/%s' % (address, port, endpoint)).encode('ascii', 'ignore')

    return order

