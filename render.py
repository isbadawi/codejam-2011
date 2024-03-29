from tornado import template

_reject = template.Template("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
<Exchange><Reject Reason="{{ reason }}"/></Exchange>
</Response>
""")

_accept = template.Template("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
<Exchange><Accept OrderRefId="{{ order_id }}"/></Exchange>
</Response>
""")

_loader = template.Loader('templates')

_snapshot = _loader.load('snapshot.html')

_homepage = _loader.load('home.html')

def render_reject_xml(reason):
    return _reject.generate(reason=reason)

def render_accept_xml(order_id):
    return _accept.generate(order_id=order_id)

def render_snapshot_html(stocks, items):
    return _snapshot.generate(stocks=stocks, items=items)

def render_home_page(stocks, prices=None, volume=None, symbol=None):
    return _homepage.generate(stocks=stocks, prices=prices, volume=volume, symbol=symbol)
