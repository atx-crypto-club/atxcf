"""
atxcf prices module
- transfix@sublevels.net
"""

import requests
import re
import string
import argparse
from pyquery import PyQuery as pq
from bitfinex import Client
from poloniex import poloniex
import networkx as nx


POLONIEX_CREDENTIALS = "poloniex_cred.json"


def get_ticker(creds = POLONIEX_CREDENTIALS):
    """
    Returns poloniex ticker dict.
    """
    pol = poloniex(creds)
    pol_ticker = pol.returnTicker()
    return pol_ticker


def get_price_in_xbt(cur = "NXT", creds = POLONIEX_CREDENTIALS):
    """
    Returns price in XBT for asset specified by cur. The validity of
    the asset string depends on the Poloniex API.
    """
    pol_ticker = get_ticker(creds)
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


def get_price_graph():
    pol_ticker = get_ticker()
    bfx_cli = Client()
    
    G = nx.DiGraph()
    G.add_nodes_from(["XBT","USD","FCT","XRP",
                      "NXT","MMNXT","DASH",
                      "COINOMAT1", "LTC"])
    G.add_edges_from([("USD","XBT",{"value":float(bfx_cli.ticker('btcusd')['last_price'])}),
                      ("XBT","FCT",{"value":float(pol_ticker['BTC_FCT']['last'])}),
                      ("XBT","XRP",{"value":float(pol_ticker['BTC_XRP']['last'])}),
                      ("XBT","NXT",{"value":float(pol_ticker['BTC_NXT']['last'])}),
                      ("XBT","MMNXT",{"value":float(pol_ticker['BTC_MMNXT']['last'])}),
                      ("XBT","DASH",{"value":float(pol_ticker['BTC_DASH']['last'])}),
                      ("NXT","COINOMAT1",{"value":get_coinomat1_nxt()}),
                      ("XBT","LTC",{"value":float(pol_ticker['BTC_LTC']['last'])})])

    # compute inverse for opposite direction price computation
    for from_node, to_node in G.edges():
        G.add_edge(to_node, from_node, value = 1.0 / G.edge[from_node][to_node]["value"])

    return G


def compute_price(value, from_asset, to_asset):
    cur_value = float(value)
    G = get_price_graph()
    sh_p = nx.shortest_path(G, from_asset, to_asset)
    if not sh_p or len(sh_p) <= 1:
        raise RuntimeError("No path from {0} to {1}"
                           .format(from_asset, to_asset))
    # for each edge in the path, compute the conversion price
    for from_cur, to_cur in zip(sh_p[0:], sh_p[1:]):
        cur_value /= G.edge[from_cur][to_cur]["value"]
    return cur_value


def get_price(value, trade_pair_str):
    # trade_pair_str is a string with a slash separating two
    # asset symbols, like XBT/USD
    asset_strs = string.split(trade_pair_str,"/",1)
    if len(asset_strs) != 2:
        raise RuntimeError("Invalid trade_pair_str %s" % trade_pair_str)
    asset_strs = [cur.strip() for cur in asset_strs]
    return compute_price(value, asset_strs[0], asset_strs[1])
    

def main():
    parser = argparse.ArgumentParser(
        description="Lookup values of various assets.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("trade_pair_str", type=str,
                        help="Trade pair in the form of bid/ask, aka"
                        "XBT/USD")
    parser.add_argument("--amount", type=float,
                        help="Amount of asking asset for equivalent bid.",
                        default=1.0)
    args = parser.parse_args()
    price = get_price(args.amount, args.trade_pair_str)
    r_msg = "{0} {1}: {2}".format(args.amount, args.trade_pair_str, price)
    print r_msg


if __name__ == "__main__":
    main()
