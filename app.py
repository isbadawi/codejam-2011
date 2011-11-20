import json
import itertools
import tornado.ioloop
import tornado.web
from tornado.httpclient import AsyncHTTPClient
import gviz_api

from logic import validate_order, unique_id, OrderBook
from render import render_reject_xml, render_accept_xml, render_snapshot_html, render_home_page


SILANIS_URL = 'http://ec2-184-73-166-185.compute-1.amazonaws.com/aws/rest/services/codejam/processes'
SILANIS_AUTH = 'Y29kZWphbTpzZWNyZXQ='
AsyncHTTPClient.configure('tornado.curl_httpclient.CurlAsyncHTTPClient')
httpclient = AsyncHTTPClient()
order_book = OrderBook(httpclient)
class TradeHandler(tornado.web.RequestHandler):
    def set_default_headers(self):
        self.set_header('Content-Type', 'text/xml; charset=UTF-8')

    def post(self):
        order = validate_order(self)
        if isinstance(order, str):
            self.finish(render_reject_xml(order))
        else:
            refid = unique_id(order['action'])
            order['orderRef'] = refid
            order_book.add_order_async(order)
            self.finish(render_accept_xml(refid))

class GUIHandler(tornado.web.RequestHandler):
    def get(self):
        self.finish(render_home_page(order_book.get_all_stocks()))

    def post(self):
        stock = self.get_argument('stock')
        orders = order_book.orders_for_stock(stock)
        prices = self._load_price_json(orders)
        volume = self._load_volume_json(orders)
        self.finish(render_home_page(order_book.get_all_stocks(), prices, volume, stock))
       
    def _load_price_json(self, orders):
        description = {
            'time': ('string', 'Time'),
            'price': ('number', 'Price'),
        }
        raw_data = [{
            'time': o['timestamp'].strftime('%H:%M:%S'),
            'price': o['price']/100.0 + (o['price']%100)/100.0
        } for o in orders]
        binned_data = [] 
        for time, orders in itertools.groupby(raw_data, lambda o: o['time']):
            order_list = list(orders)
            binned_data.append({'time': time, 'price': sum(o['price'] for o in order_list)/len(order_list)})
        price_table = gviz_api.DataTable(description)
        price_table.LoadData(binned_data)
        return price_table.ToJSon(columns_order=('time', 'price'))        

    def _load_volume_json(self, orders):
        description = {
            'time': ('string', 'Time'),
            'volume': ('number', 'Volume'),
        }
        raw_data = [{
            'time': o['timestamp'].strftime('%H:%M:%S'),
            'volume': o['amount']
        } for o in orders]
        binned_data = [] 
        for time, orders in itertools.groupby(raw_data, lambda o: o['time']):
            order_list = list(orders)
            binned_data.append({'time': time, 'volume': int(1.0*sum(o['volume'] for o in order_list)/len(order_list))})
        volume_table = gviz_api.DataTable(description)
        volume_table.LoadData(binned_data)
        return volume_table.ToJSon(columns_order=('time', 'volume'))
        

class ResetHandler(tornado.web.RequestHandler):
    def post(self):
        order_book.reset()
        self.redirect('/exchange/home')

class SnapshotHandler(tornado.web.RequestHandler):
    snapshot = ''
    num = 0
    def get(self):
        SnapshotHandler.snapshot = order_book.to_silanis_json()
        self.finish(render_snapshot_html(SnapshotHandler.snapshot))

    def post(self):
        message = {
            'name': 'ESE Snapshot Upload',
            'description': 'Trading snapshot %d' % SnapshotHandler.num,
            'owner': {
                'name': 'Pinky and the Brain',
                'email': 'isbadawi@gmail.com',
            },
            'signer': {
                'name': 'Ismail Badawi',
                'email': 'ismail.badawi@mail.mcgill.ca',
            },
            'transactions': SnapshotHandler.snapshot
        }
        message = json.dumps(message, default=lambda o: o.isoformat())
        SnapshotHandler.num += 1
        headers = {
            'Authorization': 'Basic %s' % SILANIS_AUTH,
            'Content-type': 'application/json'
        }
        httpclient.fetch(SILANIS_URL, lambda r: None, method='POST', headers=headers, body=message)
        self.redirect('/exchange/home')

application = tornado.web.Application([
    (r'/exchange/endpoint', TradeHandler),
    (r'/exchange/home', GUIHandler),
    (r'/exchange/reset', ResetHandler),
    (r'/exchange/snapshot', SnapshotHandler),
    (r'/exchange/static/(.*)', tornado.web.StaticFileHandler, {'path': 'static'})
])

if __name__ == '__main__':
    application.listen(3487)
    tornado.ioloop.IOLoop.instance().start()
