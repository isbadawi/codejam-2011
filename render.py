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

_snapshot = template.Template("""<table id="snapshot">
<tr>
<td>Time Stamp</td>
<td>Buy Sell or Execute</td>
<td>Order Reference ID</td>
<td>Execution Match Number</td>
<td>Stock Amount</td>
<td>Stock Symbol</td>
<td>Sell Order Reference ID</td>
<td>Buy Order Reference ID</td>
<td>Parent Order Reference ID</td>
<td>Price</td>
<td>State (FILL or UNFILLED)</td>
<td>Client Telephone Number</td>
</tr>
{% for item in items %}
<tr>
<td>{{ item['Timestamp'] }}</td>
<td>{{ item['BS'] }}</td>
<td>{{ item['OrderRefID'] }}</td>
<td>{{ item['MatchNumber'] }}</td>
<td>{{ item['Shares'] }}</td>
<td>{{ item['Stock'] }}</td>
<td>{{ item['SellID'] }}</td>
<td>{{ item['BuyID'] }}</td>
<td>{{ item['Parent'] }}</td>
<td>{{ item['Price'] }}</td>
<td>{{ item['Filled'] }}</td>
<td>{{ item['From'] }}</td>
</tr>
{% end %}
</table>
"""

def render_reject_xml(reason):
    return _reject.generate(reason=reason)

def render_accept_xml(order_id):
    return _accept.generate(order_id=order_id)

def render_snapshot_html(items):
    return _snapshot.generate(items=items)
