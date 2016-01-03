"""
atxcf prices module
- transfix@sublevels.net
"""

import requests
import re
from pyquery import PyQuery as pq
from bitfinex import Client
from poloniex import poloniex

POLONIEX_CREDENTIALS = "poloniex_cred.json"

def get_price_in_xbt(cur = "NXT", creds = POLONIEX_CREDENTIALS):
    """
    Returns price in XBT for asset specified by cur. The validity of
    the asset string depends on the Poloniex API.
    """
    pol = poloniex(creds)
    pol_ticker = pol.returnTicker()
    return float(pol_ticker["BTC_%s" % (cur, )]["last"])


def get_coinomat1_nxt():
    """
    Returns the coinomat1 price in terms of NXT. Basically
    scraping from the web here.
    """
    req_url = 'http://www.cryptoassetcharts.info/assets/show/242/7474435909229872610-coinomat1'
    response = requests.get(req_url)
    doc = pq(response.content)
    line = doc('div.col-md-4')
    m = re.search('([-+]?([0-9]+(\.[0-9]+)?|\.[0-9]+))\W+NXT', str(line))
    return float(m.group(1))


def get_coinomat1_xbt(creds = POLONIEX_CREDENTIALS):
    """
    Returns the coinomat1 price in terms of XBT.
    """
    nxtxbt_price = get_price_in_xbt("NXT", creds)
    return nxtxbt_price * get_coinomat1_nxt()


def get_xbt_usd():
    """
    Returns the XBT price in terms of USD.
    """
    bfx_cli = Client()
    return float(bfx_cli.ticker("btcusd")["last_price"])


def get_ticker():
    """
    Returns poloniex ticker dict.
    """
    pol = poloniex(POLONIEX_CREDENTIALS)
    pol_ticker = pol.returnTicker()
    return pol_ticker


def get_fund_asset_prices():
    pol_ticker = get_ticker()
    bfx_cli = Client()
    
    price_d = {
        'XBT/USD': float(bfx_cli.ticker('btcusd')['last_price']),
        'FCT/XBT': float(pol_ticker['BTC_FCT']['last']),
        'XRP/XBT': float(pol_ticker['BTC_XRP']['last']),
        'NXT/XBT': float(pol_ticker['BTC_NXT']['last']),
        'MMNXT/XBT': float(pol_ticker['BTC_MMNXT']['last']),
        'DASH/XBT': float(pol_ticker['BTC_DASH']['last']),
        'COINOMAT1/XBT': get_coinomat1_xbt(),
        'LTC/XBT': float(pol_ticker['BTC_LTC']['last']),
    }
    return price_d


def main():
    print get_fund_asset_prices()


if __name__ == "__main__":
    main()
