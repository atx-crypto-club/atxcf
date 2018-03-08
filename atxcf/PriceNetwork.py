"""
PriceNetwork module. Maintains a graph representing an asset exchange network to determine
prices of assets relative to each other.
- transfix@sublevels.net - 20160117
"""
import PriceSource
from PriceSource import PriceSourceError
import cache
import settings

from core import _log_error
from settings import get_setting, set_setting, has_creds

from functools import partial
import networkx as nx

import string
import threading
import multiprocessing
import time
import math

import requests.exceptions

class PriceNetworkError(PriceSource.PriceSourceError):
    pass


class PriceNetwork(PriceSource.PriceSource):

    def __init__(self):
        super(PriceNetwork, self).__init__()
        self._lock = threading.RLock()
        self._sources = []
        self.init_sources()

        self._price_graph = None


    def init_sources(self):
        with self._lock:
            self._sources = []
            for source_name in get_setting("options", "price_sources",
                                           default=["Bitfinex", "Bittrex",
                                                    "Poloniex", "Conversions",
                                                    "CoinExchange", "Coinigy"]):
                if hasattr(PriceSource, source_name):
                    Source = getattr(PriceSource, source_name)
                    if not Source.requires_creds() or has_creds(Source.__name__):
                        self._sources.append(Source())

                    
    def get_sources(self):
        return self._sources


    def add_source(self, source):
        G = self._get_price_graph()
        with self._lock:
            G.add_nodes_from(source.get_symbols())
            self._sources.append(source)
            for mkt in source.get_markets():
                from_mkt, to_mkt = mkt.split("/")
                G.add_edge(from_mkt, to_mkt)
    

    def _get_price_graph(self):
        markets = self.get_markets()
        with self._lock:
          if not self._price_graph:
              G = nx.Graph()
              G.add_nodes_from(self.get_symbols())
              for mkt in markets:
                  from_mkt, to_mkt = mkt.split("/")
                  G.add_edge(from_mkt, to_mkt)
              self._price_graph = G
        return self._price_graph
    

    def get_symbols(self):
        """
        Returns the set of all known symbols across all price sources.
        """
        symbols = set()
        with self._lock:
            for source in self.get_sources():
                try:
                    for symbol in source.get_symbols():
                        symbols.add(symbol)
                except Exception as e:
                    _log_error(['PriceNetwork.get_symbols',
                                source._class_name(), str(e)])
        return list(symbols)

    
    def get_base_symbols(self):
        """
        Returns the set of all known symbols across all price sources.
        """
        symbols = set()
        with self._lock:
            for source in self._sources:
                try:
                    for symbol in source.get_base_symbols():
                        symbols.add(symbol)
                except Exception as e:
                    _log_error(['PriceNetwork.get_base_symbols',
                                source._class_name(), str(e)])
        return list(symbols)


    def get_markets(self):
        """
        Returns all markets known by all of the price sources.
        """
        mkts = set()
        with self._lock:
            for source in self._sources:
                try:
                    for mkt in source.get_markets():
                        mkts.add(mkt)
                except Exception as e:
                    _log_error(['PriceNetwork.get_markets',
                                source._class_name(), str(e)])
        return list(mkts)


    def get_market_sources(self):
        """
        Returns all market sources with their respective markets
        """
        mkt_srcs = {}
        with self._lock:
            for source in self._sources:
                mkt_srcs.update({source._class_name(): source.get_markets()})
        return mkt_srcs

    
    def _do_get_price(self, from_asset, to_asset, amount=1.0):
        """
        Helper function for get_price.
        """
        mkt_key = from_asset + "/" + to_asset
        inv_mkt_key = to_asset + "/" + from_asset            

        do_cache = False
        unit_prices = []
        # return from the cache if it is already available
        if cache.has_key(mkt_key):
            unit_prices.append(cache.get_val(mkt_key))
        else:
            do_cache = True
            with self._lock:
                for source in self._sources:
                    try:
                        mkts = source.get_markets()
                        if mkt_key in mkts or inv_mkt_key in mkts:
                                price = source.get_price(from_asset, to_asset, 1.0)
                                unit_prices.append(float(price))
                    except PriceSourceError as e:
                        _log_error(['PriceNetwork._do_get_price',
                                    source._class_name(), str(e)])
                    except requests.exceptions.ConnectionError as e:
                        _log_error(['PriceNetwork._do_get_price',
                                    source._class_name(), str(e)])
                    
        if len(unit_prices) == 0:
            raise PriceNetworkError("%s: Couldn't determine price of %s/%s" % (self._class_name(),
                                                                               from_asset,
                                                                               to_asset))

        avg_price = math.fsum(unit_prices)/float(len(unit_prices))

        # Make sure to copy it to the cache so future retrievals
        # within 60 seconds are quick.
        if do_cache:
            expire = get_setting("options", "cache_price_expiration", default=60)
            cache.set_val(mkt_key, float(avg_price), expire=expire)

        return avg_price * amount


    def get_shortest_path(self, from_asset, to_asset):
        """
        Returns the shortest path known from_asset to_asset.
        """
        if from_asset == to_asset:
            return (from_asset,)

        G = self._get_price_graph()

        # Sometimes the sources may add new markets after the
         # price network is initialized. So lets add them here.
        do_add_edge = False
        if not from_asset in G and from_asset in self.get_symbols():
            G.add_node(from_asset)
            do_add_edge = True
        if not to_asset in G and to_asset in self.get_symbols():
            do_add_edge = True
            G.add_node(to_asset)
        mkt = from_asset + "/" + to_asset
        if do_add_edge and mkt in self.get_markets():
            G.add_edge(from_asset, to_asset)

        sh_p = None
        try:
            sh_p = nx.shortest_path(G, from_asset, to_asset)
        except Exception as e:
            _log_error(['PriceNetwork.get_price',
                        self._class_name(), str(e)])
        return sh_p


    def get_price(self, from_asset, to_asset, amount=1.0):
        """
        Returns how much of to_asset you would have after exchanging it
        for amount of from_asset based on the last price. Saves prices
        in the cache to help with frequent requests for prices.
        """
        if from_asset == to_asset or amount == 0.0:
            return amount

        sh_p = self.get_shortest_path(from_asset, to_asset)
        if not sh_p:
            raise PriceNetworkError("No path from {0} to {1}"
                                    .format(from_asset, to_asset))
        # for each edge in the path, compute the conversion price
        cur_value = float(amount)
        for from_cur, to_cur in zip(sh_p[0:], sh_p[1:]):
            cur_value = self._do_get_price(from_cur, to_cur, cur_value)

        return cur_value

    
    def price(self, trade_pair_str, value = 1.0):
        # trade_pair_str is a string with a slash separating two
        # asset symbols, like XBT/USD
        asset_strs = string.split(trade_pair_str,"/",1)
        if len(asset_strs) != 2:
            raise PriceNetworkError("Invalid trade_pair_str %s" % trade_pair_str)
        asset_strs = [cur.strip() for cur in asset_strs]
        return self.get_price(asset_strs[0], asset_strs[1], value)


_pn = None
def init():
    """
    (Re-)initializes the PriceNetwork singleton.
    """
    global _pn
    _pn = PriceNetwork()


def _get_price_network():
    """
    Returns a singleton instance of a PriceNetwork.
    """
    global _pn
    if not _pn:
        init()
    return _pn


def instance():
    """
    Deprecates _get_price_network.
    """
    return _get_price_network()


def add_source(source):
    """
    Adds a source to the price network.
    """
    instance().add_source(source)

    
def _do_get_price(value, trade_pair_str):    
    asset_strs = string.split(trade_pair_str,"/",1)
    if len(asset_strs) != 2:
        raise CmdError("Invalid trade pair %s" % trade_pair_str)
    asset_strs = [cur.strip() for cur in asset_strs]

    pn = instance()
    price = pn.get_price(asset_strs[0], asset_strs[1], value)
    if not price:
        price = float('NaN')
        
    return price


def get_price(*args, **kwargs):
    """
    Returns price dependings on args:
    - 1 == len(args) -> from/to pair string (aka trade_pair_str)
    - 2 == len(args) -> (value, trade_pair_str)
    - 3 == len(args) -> (value, from_asset, to_asset)
    """
    value = 1.0
    trade_pair_str = ""
    if len(args) == 1:
        # treat args as a from/to pair with amount == 1
        value = 1.0
        trade_pair_str = args[0]
    elif len(args) == 2:
        # treat args as a pair of (value, trade_pair_str)
        value = float(args[0])
        trade_pair_str = args[1]
    elif len(args) == 3:
        # treat args as a triple of (value, from_asset, to_asset)
        value = float(args[0])
        from_asset = args[1].strip()
        to_asset = args[2].strip()
        trade_pair_str = "%s/%s" % (from_asset, to_asset)
    else:
        raise CmdError("Invalid argument list for command get_price: %s" % str(args))
    return _do_get_price(value, trade_pair_str)


def get_prices(balances, base_asset):
    """
    Given a dict of balances, returns another dict with the
    prices of each asset in terms of the base_asset.
    """
    values = {}
    for asset, balance in balances.iteritems():
        if balance == 0.0:
            continue
        price = get_price(balance, asset, base_asset)
        if price != 0.0:
            values[asset] = (balance, price)
    return values


def get_nav(balances, base_asset):
    """
    Gven a dict of balances, returns the net asset value
    of the whole collection in terms of the base_asset.
    """
    prices = get_prices(balances, base_asset)
    nav = 0.0
    for asset, item in prices.iteritems():
        nav += item[1]
    return nav


def get_symbols():
    """
    Returns all asset symbols known by the bot.
    """
    return sorted(instance().get_symbols())


def get_base_symbols():
    """
    Returns all symbols used for pricing.
    """
    return sorted(instance().get_base_symbols())


def get_markets():
    """
    Returns all markets known by the bot.
    """
    return sorted(instance().get_markets())


def get_market_sources():
    """
    Returns the name of all market sources used for pricing
    """
    return [source for source in instance().get_market_sources()]


def get_all_prices(mkts=None):
    """
    Returns prices for each market listed in mkts. If mkts is
    none, returns prices of all known markets.
    """
    prices = {}
    if not mkts:
        mkts = get_markets()
    for mkt in mkts:
        try:
            price = get_price(mkt)
            prices[mkt] = price
        except PriceSourceError as e:
            _log_error(['get_all_prices', '', str(e)])
    return prices
