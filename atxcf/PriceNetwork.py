"""
PriceNetwork module. Maintains a graph representing an asset exchange network to determine
prices of assets relative to each other.
- transfix@sublevels.net - 20160117
"""
import PriceSource
import cache
import settings

from functools import partial
import networkx as nx

import string
import threading
import multiprocessing
import time


class PriceNetworkError(PriceSource.PriceSourceError):
    pass


class PriceNetwork(PriceSource.AllSources):

    def __init__(self, doInitGraph=False):
        super(PriceNetwork, self).__init__()
        self._price_graph = None

        if doInitGraph:
            self.init_graph()
            

    def _do_get_price(self, from_asset, to_asset, value=1.0, get_last=False):
        """
        Returns price of assets from AllSources
        """
        return super(PriceNetwork, self).get_price(from_asset, to_asset, value)


    def _generate_graph(self):
        all_symbols = self.get_symbols()
        
        # Create a graph linking all asset nodes with edges where
        # an exchange exists between them.
        G = nx.Graph()
        G.add_nodes_from(all_symbols)
        bad_markets = []
        good_markets = []

        all_markets = self.get_markets()
        all_market_prices = []
        mc_key = self._class_name() + ".all_market_prices"
        if cache.has_key(mc_key):
            # check if the markets in the cache differ from what we now see.
            # if so, get all market prices again. Otherwise if we're looking at
            # the same set of markets, lets init the graph with what is in the
            # cache so we can skip polling every market.
            all_market_prices, last_all_markets = cache.get_val(mc_key)
            #if last_all_markets != all_markets:
            #all_market_prices = []

        if len(all_market_prices) == 0:
            def get_mkt_price(mkt_pair_str):
                mkt_pair = mkt_pair_str.split("/")
                try:
                    last_price = None
                    if self._has_stored_price(mkt_pair_str):
                        last_price = self._get_stored_price(mkt_pair_str)
                        print "Loading market", mkt_pair[0], mkt_pair[1]
                    else:
                        last_price = self._do_get_price(mkt_pair[0], mkt_pair[1])
                        print "Adding market", mkt_pair[0], mkt_pair[1]
                    return (mkt_pair[0], mkt_pair[1], last_price, "")
                except PriceSource.PriceSourceError as e:
                    return (mkt_pair[0], mkt_pair[1], None, e.message)

            print "Polling known markets..."
            # multiproccessing isn't working... some pickling error
            #pool = multiprocessing.Pool()
            #all_market_prices = pool.map(get_mkt_price, all_markets, 32)
            all_market_prices = map(get_mkt_price, all_markets)
            cache.set_val(mc_key, (all_market_prices, all_markets))

        error_msgs = []
        for from_mkt, to_mkt, last_price, msg in all_market_prices:
            if last_price == None:
                bad_markets.append("{0}/{1}".format(from_mkt, to_mkt))
                error_msgs.append("{0}/{1}: {2}".format(from_mkt, to_mkt, msg))
            else:
                G.add_edge(from_mkt, to_mkt, last_price = last_price)
                good_markets.append((from_mkt, to_mkt, last_price))

        # Markets available
        conv = []
        for item in good_markets:
            conv.append("{0}/{1}".format(item[0], item[1]))
        print "Known markets:", conv
        print "Number of markets:", len(conv)
        print "Number of symbols:", len(all_symbols)

        # There may have been errors retriving market info for some markets listed
        # as available. Let's print them out here.
        print "Dropped markets due to errors getting last price: ", error_msgs
        
        return G


    def _get_price_graph(self):
        with self._lock:
            if self._price_graph == None:
                self.init_graph()
            return self._price_graph


    def init_graph(self):
        """
        (Re-)generates the price network graph and assigns it to the _price_graph
        attrib.
        """
        with self._lock:
            self._price_graph = self._generate_graph()


    def get_symbols(self):
        return super(PriceNetwork, self).get_symbols()


    def get_markets(self):
        return super(PriceNetwork, self).get_markets()


    def set_source(self, sourcename, source):
        init_sources([source])
        init_graph() # TODO: just add new edges


    def get_price(self, from_asset, to_asset, value = 1.0, get_last=False):
        
        # do nothing if they're the same
        if from_asset == to_asset:
            return value

        G = self._get_price_graph()
        try:
            sh_p = nx.shortest_path(G, from_asset, to_asset)
        except:
            return None # TODO: log this
        if not sh_p or len(sh_p) <= 1:
            raise PriceNetworkError("No path from {0} to {1}"
                                    .format(from_asset, to_asset))
        # for each edge in the path, compute the conversion price
        cur_value = float(value)
        try:
            for from_cur, to_cur in zip(sh_p[0:], sh_p[1:]):
                cur_value = self._do_get_price(from_cur, to_cur, cur_value, get_last)
        except:
            return None # TODO: log this
        return cur_value


    def price(self, trade_pair_str, value = 1.0, get_last=False):
        # trade_pair_str is a string with a slash separating two
        # asset symbols, like XBT/USD
        asset_strs = string.split(trade_pair_str,"/",1)
        if len(asset_strs) != 2:
            raise PriceNetworkError("Invalid trade_pair_str %s" % trade_pair_str)
        asset_strs = [cur.strip() for cur in asset_strs]
        return self.get_price(asset_strs[0], asset_strs[1], value, get_last)


_pn = None
def init():
    """
    (Re-)initializes the PriceNetwork singleton.
    """
    global _pn
    _pn = PriceNetwork()
    _pn.init_graph()


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
