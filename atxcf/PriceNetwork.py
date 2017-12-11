"""
PriceNetwork module. Maintains a graph representing an asset exchange network to determine
prices of assets relative to each other.
- transfix@sublevels.net - 20160117
"""
import PriceSource
from PriceSource import PriceSourceError
import cache
import settings
from settings import get_setting, has_creds

from functools import partial
import networkx as nx

import string
import threading
import multiprocessing
import time
import math


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
        self._sources = []
        for source_name in get_setting("options", "price_sources",
                                       default=["Bitfinex", "Bittrex",
                                                "Poloniex", "Conversions"]):
            if hasattr(PriceSource, source_name):
                Source = getattr(PriceSource, source_name)
                if not Source.requires_creds() or has_creds(Source.__name__):
                    self._sources.append(Source())

                    
    def get_sources(self):
        return self._sources


    def add_source(self, source):
        with self._lock:
            self._sources.append(source)
    

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
                for symbol in source.get_symbols():
                    symbols.add(symbol)
        return list(symbols)

    
    def get_base_symbols(self):
        """
        Returns the set of all known symbols across all price sources.
        """
        symbols = set()
        with self._lock:
            for source in self._sources:
                for symbol in source.get_base_symbols():
                    symbols.add(symbol)
        return list(symbols)


    def get_markets(self):
        """
        Returns all markets known by all of the price sources.
        """
        mkts = set()
        with self._lock:
            for source in self._sources:
                for mkt in source.get_markets():
                    mkts.add(mkt)
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
        unit_prices = []
        with self._lock:
            for source in self._sources:
                try:
                    mkt_key = from_asset + "/" + to_asset
                    if cache.has_key(mkt_key):
                        price = cache.get_val(mkt_key)
                    else:
                        price = source.get_price(from_asset, to_asset, 1.0)
                        expire = get_setting("options", "cache_price_expiration", default=60)
                        cache.set_val(mkt_key, float(price), expire=expire)
                    
                    unit_prices.append(float(price))
                except PriceSourceError:
                    pass
                    
        if len(unit_prices) == 0:
            raise PriceSourceError("%s: Couldn't determine price of %s/%s" % (self._class_name(), from_asset, to_asset))

        avg_price = math.fsum(unit_prices)/float(len(unit_prices))
        return avg_price * amount

    
    def get_price(self, from_asset, to_asset, amount=1.0):
        """
        Returns how much of to_asset you would have after exchanging it
        for amount of from_asset based on the last price. Saves prices
        in the cache to help with frequent requests for prices.
        """
        if from_asset == to_asset:
            return amount
                
        G = self._get_price_graph()

        sh_p = None
        try:
            sh_p = nx.shortest_path(G, from_asset, to_asset)
        except:
            return None # TODO: log this
        if not sh_p or len(sh_p) <= 1:
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
