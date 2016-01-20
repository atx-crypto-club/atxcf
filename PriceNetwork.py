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


class PriceNetwork(PriceSource.AllSources):

    def __init__(self):
        super(PriceNetwork, self).__init__()
        self._generate_graph()


    def _generate_graph(self):
        all_symbols = self.get_symbols()
        
        # Create a graph linking all asset nodes with edges where
        # an exchange exists between them.
        G = nx.Graph()
        G.add_nodes_from(all_symbols)

        for base in self.get_base_symbols():
            for counter in all_symbols:
                try:
                    last_price = super(PriceNetwork, self).get_price(base, counter)
                    print "Adding edge", base, counter, last_price
                    G.add_edge(base, counter, last_price = last_price)
                except:
                    pass

        # conversions available
        conv = []
        for item in G.edges_iter():
            conv.append("{0}/{1}".format(item[0], item[1]))
        print "Available conversions: ", conv
        
        self._price_graph = G


    def get_price(self, from_asset, to_asset, value = 1.0):
        G = self._price_graph
        sh_p = nx.shortest_path(G, from_asset, to_asset)
        if not sh_p or len(sh_p) <= 1:
            raise PriceNetworkError("No path from {0} to {1}"
                                    .format(from_asset, to_asset))
        # for each edge in the path, compute the conversion price
        cur_value = float(value)
        for from_cur, to_cur in zip(sh_p[0:], sh_p[1:]):
            cur_value = super(PriceNetwork, self).get_price(from_cur, to_cur, cur_value)
        return cur_value


    def price(self, trade_pair_str, value = 1.0):
        # trade_pair_str is a string with a slash separating two
        # asset symbols, like XBT/USD
        asset_strs = string.split(trade_pair_str,"/",1)
        if len(asset_strs) != 2:
            raise RuntimeError("Invalid trade_pair_str %s" % trade_pair_str)
        asset_strs = [cur.strip() for cur in asset_strs]
        return self.get_price(asset_strs[0], asset_strs[1], value)
