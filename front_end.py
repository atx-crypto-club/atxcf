from poloniex import poloniex
from bitfinex import Client

import requests
from pyquery import PyQuery as pq

from flask import Flask

import re

def get_coinomat1_nxt_price():
    req_url = 'http://www.cryptoassetcharts.info/assets/show/242/7474435909229872610-coinomat1'
    response = requests.get(req_url)
    doc = pq(response.content)
    line = doc('div.col-md-4')
    m = re.search('([-+]?([0-9]+(\.[0-9]+)?|\.[0-9]+))\W+NXT', str(line))
    return float(m.group(1))

def get_coinomat1_xbt_price():
    pol = poloniex('poloniex_cred.json')
    pol_ticker = pol.returnTicker()
    nxtxbt_price = float(pol_ticker['BTC_NXT']['last'])
    return nxtxbt_price * get_coinomat1_nxt_price()


app = Flask(__name__)

@app.route('/')
def index():
    return '~~ atxcf-bot ~~'

@app.route('/prices')
def prices():
    pol = poloniex('poloniex_cred.json')
    pol_ticker = pol.returnTicker()

    bfx_cli = Client()
    
    price_d = {
        'XBT/USD': float(bfx_cli.ticker('btcusd')['last_price']),
        'FCT/XBT': float(pol_ticker['BTC_FCT']['last']),
        'XRP/XBT': float(pol_ticker['BTC_XRP']['last']),
        'NXT/XBT': float(pol_ticker['BTC_NXT']['last']),
        'MMNXT/XBT': float(pol_ticker['BTC_MMNXT']['last']),
        'DASH/XBT': float(pol_ticker['BTC_DASH']['last']),
        'COINOMAT1/XBT': get_coinomat1_xbt_price(),
        'LTC/XBT': float(pol_ticker['BTC_LTC']['last']),
        }
    output = "<p>"
    for key, val in price_d.iteritems():
        if isinstance(val, str):
            output += "{0}: {1}<br />".format(key, val)
        else:
            output += "{0}: {1:.8f}<br />".format(key, val)

    # debugging polo ticker output
    #output += "</p>";
    #output += "<p>"
    #output += str(pol_ticker)
    #output += "</p>"

    return output


@app.route('/holdings')
def holdings():
    output = "<p>"
    
    output += "<p>"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=1337)
