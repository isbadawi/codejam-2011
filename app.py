import json
import threading
import tornado.ioloop
import tornado.web
from tornado.httpclient import AsyncHTTPClient
import gviz_api

from logic import validate_order, unique_id, OrderBook
from render import render_reject_xml, render_accept_xml, render_snapshot_html, render_home_page


SILANIS_URL = 'http://ec2-184-73-166-185.compute-1.amazonaws.com/aws/rest/services/codejam/processes'
SILANIS_AUTH = 'Y29kZWphbTpzZWNyZXQ='
#AsyncHTTPClient.configure('tornado.curl_httpclient.CurlAsyncHTTPClient')
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
        bins = self._bin_data(raw_data, 'price')
        price_table = gviz_api.DataTable(description)
        price_table.LoadData(bins)
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
        bins = self._bin_data(raw_data, 'volume')
        volume_table = gviz_api.DataTable(description)
        volume_table.LoadData(bins)
        return volume_table.ToJSon(columns_order=('time', 'volume'))

    def _bin_data(self, data, valuekey, bins=20):
        if (len(data) < bins):
            return data
        step = len(data)/bins
        binned_data = [data[i:i+step] for i in range(0, len(data), step)]
        binned_data = [{
            'time': d[len(d)/2]['time'],
            valuekey: 1.0*sum(o[valuekey] for o in d)/len(d)
        } for d in binned_data]
        return binned_data

class ResetHandler(tornado.web.RequestHandler):
    def post(self):
        order_book.reset()
        self.redirect('/exchange/home')

class SnapshotHandler(tornado.web.RequestHandler):
    snapshot = ''
    num = 1
    @tornado.web.asynchronous
    def get(self):
        threading.Thread(target=self._compute_snapshot).start()

    def finish_get(self, html):
        self.finish(html)

    def _compute_snapshot(self):
        SnapshotHandler.snapshot = order_book.to_silanis_json()
        html = render_snapshot_html(order_book.get_all_stocks(), SnapshotHandler.snapshot)
        tornado.ioloop.IOLoop.instance().add_callback(lambda: self.finish_get(html))

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

    def _log_response(self, response):
        print response.code
        print response.headers
        print response.body

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
