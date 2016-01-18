"""
PriceNetwork module. Maintains a graph representing an asset exchange network to determine
prices of assets relative to each other.
- transfix@sublevels.net - 20160117
"""

from functools import partial
import networkx as nx
import PriceSource

import string


class PriceNetworkError(RuntimeError):
    pass


class PriceNetwork(object):

    def __init__(self):
        self._sources = PriceSource.AllSources()
        all_symbols = self._sources.get_symbols()
        
        # Create a graph linking all asset nodes with edges where
        # an exchange exists between them.
        G = nx.Graph()
        G.add_nodes_from(all_symbols)

        for base in self._sources.get_base_symbols():
            for counter in all_symbols:
                try:
                    last_price = self._sources.get_price(base, counter)
                    print "Adding edge", base, counter, last_price
                    G.add_edge(base, counter, last_price = last_price)
                except PriceSource.PriceSourceError:
                    pass
        
        self._price_graph = G


    def compute_price(self, from_asset, to_asset, value):
        G = self._price_graph
        sh_p = nx.shortest_path(G, from_asset, to_asset)
        if not sh_p or len(sh_p) <= 1:
            raise PriceNetworkError("No path from {0} to {1}"
                                    .format(from_asset, to_asset))
        # for each edge in the path, compute the conversion price
        cur_value = float(value)
        for from_cur, to_cur in zip(sh_p[0:], sh_p[1:]):
            cur_value = self._sources.get_price(from_cur, to_cur, cur_value)
        return cur_value


    def get_price(self, trade_pair_str, value):
        # trade_pair_str is a string with a slash separating two
        # asset symbols, like XBT/USD
        asset_strs = string.split(trade_pair_str,"/",1)
        if len(asset_strs) != 2:
            raise RuntimeError("Invalid trade_pair_str %s" % trade_pair_str)
        asset_strs = [cur.strip() for cur in asset_strs]
        return self.compute_price(asset_strs[0], asset_strs[1], value)
