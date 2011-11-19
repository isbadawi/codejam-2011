import re
import datetime
from multiprocessing.pool import ThreadPool
from collections import OrderedDict

class OrderBook(object):
    def __init__(self):
        self.orders = []
        self.pool = ThreadPool(10)

    def add_order_async(self, order):
        self.pool.apply_async(self.add_order, args=(order,))

    def add_order(self, order):
        timestamp = datetime.datetime.now()
        matches = self.matching_orders(order)
        if not matches:
            order['Filled'] = 'U'
            self.orders.append(order)

    def matching_orders(self, order):
        return [old for old in orders if self._orders_match(old, order)]

    def _orders_match(self, old, new):
        pair = {'B': 'S', 'S': 'B'}
        if old['BS'] != pair[new['BS']]:
            return False
        condition = new['BS'] == 'S'
        seller, buyer = (old, new)[condition], (new, old)[condition]
        return (old['Filled'] = 'U' and old['Stock'] == new['Stock'] and
                seller['Price'] <= buyer['Price'])



phone_pattern = re.compile(r'\+[0-9]{1,15}$')

def validate_order(args):
    """
    Given HTTP POST parameters, return a dict with the order parameters if
    the order is valid, else return a string with the error code.
    """
    order = {}

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
    order['Broker'] = 'http://%s:%s/%s' % (address, port, endpoint)

    return order

ids = {'B': 0, 'S': 0}
def unique_id(order):
    ids[order['BS']] += 1
    return '%s%d' % (order['BS'], ids[order['BS']])
