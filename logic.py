import re
import datetime
from urllib import urlencode
from threading import Lock
from multiprocessing.pool import ThreadPool
from collections import defaultdict

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

class OrderBook(object):
    def __init__(self, httpclient):
        self.orders = []
        self.pool = ThreadPool(10)
        self.httpclient = httpclient

    def add_order_async(self, order):
        self.pool.apply_async(self.add_order, args=(order,))

    def add_order(self, order):
        order['Timestamp'] = datetime.datetime.now()
        matches = self.matching_orders(order)
        if not matches:
            order['Filled'] = 'U'
            self.orders.append(order)
        else:
            shares_left = order['Shares']
            if order['BS'] == 'B':
                for match in self._sorted_sell_orders(matches):
                    match['Filled'] = 'F' 
                    if shares_left >= match['Shares']:
                        self.orders.append(self._trade_execution(match, order, match['Shares'], match['Price']))
                        shares_left -= match['Shares']
                    else:
                        self.orders.append(self._trade_execution(match, order, shares_left, match['Price']))
                        self.add_order(self._residual_order(match, match['Shares'] - shares_left))
                        shares_left = 0
                        break
            elif order['BS'] == 'S':
                for match in self._sorted_buy_orders(matches):
                    match['Filled'] = 'F'
                    if shares_left >= match['Shares']:
                        self.orders.append(self._trade_execution(order, match, match['Shares'], match['Price']))
                        shares_left -= match['Shares']
                    else:
                        self.orders.append(self._trade_execution(order, match, shares_left, match['Price']))
                        self.add_order(self._residual_order(match, match['Shares'] - shares_left))
                        shares_left = 0
                        break
            if shares_left != 0:
                self.add_order(self._residual_order(order, shares_left))
            order['Filled'] = 'F' if shares_left != order['Shares'] else 'U'
            self.orders.append(order)    

    def _timestamp(self, o):
        return o['Timestamp'] if not o['Parent'] else o['Parent']['Timestamp']

    def _sorted_sell_orders(self, matches):
        return sorted(matches, key=lambda o: (o['Price'], self._timestamp(o)))

    def _sorted_buy_orders(self, matches):
        return sorted(matches, key=lambda o: (-o['Price'], self._timestamp(o)))

    def matching_orders(self, order):
        return [old for old in self.orders if self._orders_match(old, order)]

    def _trade_execution(self, seller, buyer, shares, price):
        trade = defaultdict(str)
        trade['Timestamp'] = datetime.datetime.now()
        trade['MatchNumber'] = get_match_number()
        trade['BS'] = 'E'
        trade['Shares'] = shares
        trade['Stock'] = seller['Stock']
        trade['SellerID'] = seller['OrderRefID']
        trade['BuyerID'] = buyer['OrderRefID']
        trade['Price'] = price
        self._send_notification(trade['MatchNumber'], seller, shares, price)
        self._send_notification(trade['MatchNumber'], buyer, shares, price)
        return trade

    def _residual_order(self, parent, shares):
        order = defaultdict(str)
        order.update(parent)
        order['Timestamp'] = datetime.datetime.now()
        order['Parent'] = parent['Parent'] if parent['Parent'] else parent
        order['Shares'] = shares
        order['OrderRefID'] = unique_id('O')
        return order

    def _orders_match(self, old, new):
        pair = {'B': 'S', 'S': 'B'}
        if old['BS'] != pair[new['BS']]:
            return False
        condition = new['BS'] == 'S'
        seller, buyer = (old, new)[condition], (new, old)[condition]
        return (old['Filled'] == 'U' and old['Stock'] == new['Stock'] and
                seller['Price'] <= buyer['Price'])

    def _send_notification(self, match_number, order, shares, price):
        params = {
            'MessageType': 'E',
            'OrderReferenceIdentifier': order['OrderRefID'] if not order['Parent'] else order['Parent']['OrderRefID'],
            'ExecutedShares': shares,
            'ExecutionPrice': price,
            'MatchNumber': match_number,
            'To': order['From']
        }
        self.httpclient.fetch(order['Broker'], lambda r: None, method='POST', body=urlencode(params))

    def _log_response(self, response):
        print response.code
        print response.headers
        print response.body

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
#    order['MessageType'] = message_type

    phone_number = args.get_argument('From', None)
    if phone_number is None or phone_pattern.match(phone_number) is None:
        return 'F'
    order['From'] = phone_number

    bs = args.get_argument('BS', None)
    if bs is None or bs not in ('B', 'S'):
        return 'I'
    order['BS'] = bs

    shares = args.get_argument('Shares', None)
    if shares is None:
        return 'Z'
    try:
        shares = int(shares)
    except ValueError:
        return 'Z'
    if not (0 < shares < 1000000):
        return 'Z'
    order['Shares'] = shares

    stock = args.get_argument('Stock', None)
    if stock is None or not stock.isalnum() or not (3 <= len(stock) <= 8):
        return 'S'
    order['Stock'] = stock

    price = args.get_argument('Price', None)
    if price is None:
        return 'X'
    try:
        price = int(price)
    except ValueError:
        return 'X'
    if not (1 <= price <= 100000):
        return 'X'
    order['Price'] = price

    twilio = args.get_argument('Twilio', None)
    if twilio is None or twilio not in ('Y', 'N'):
        return 'T'
    order['Twilio'] = twilio

    address = args.get_argument('BrokerAddress', None)
    if address is None:
        return 'A'
#    order['BrokerAddress'] = address

    port = args.get_argument('BrokerPort', None)
    if port is None:
        return 'P'
    try:
        int(port)
    except ValueError:
        return 'P'
#    order['BrokerPort'] = port

    endpoint = args.get_argument('BrokerEndpoint', None)
    if endpoint is None:
        return 'E'
#    order['BrokerEndpoint'] = endpoint
    order['Broker'] = ('http://%s:%s/%s' % (address, port, endpoint)).encode('ascii', 'ignore')

    return order

