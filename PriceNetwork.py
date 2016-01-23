"""
PriceNetwork module. Maintains a graph representing an asset exchange network to determine
prices of assets relative to each other.
- transfix@sublevels.net - 20160117
"""

from functools import partial
import networkx as nx
import PriceSource

import string


class PriceNetworkError(PriceSource.PriceSourceError):
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
        all_markets = self.get_markets()
        bad_markets = []
        for mkt_pair_str in all_markets:
            mkt_pair = mkt_pair_str.split("/")
            try:
                last_price = super(PriceNetwork, self).get_price(mkt_pair[0], mkt_pair[1])
            except PriceSource.PriceSourceError:
                bad_markets.append(mkt_pair_str)
            print "Adding edge", mkt_pair[0], mkt_pair[1], last_price
            G.add_edge(mkt_pair[0], mkt_pair[1], last_price = last_price)

        # Conversions available
        conv = []
        for item in G.edges_iter():
            conv.append("{0}/{1}".format(item[0], item[1]))
        print "Known markets:", conv
        print "Number of markets:", len(conv)
        print "Number of symbols:", len(all_symbols)

        # There may have been errors retriving market info for some markets listed
        # as available. Let's print them out here.
        bd_mkts = []
        for mkt in bad_markets:
            bd_mkts.append(mkt)
        print "Dropped markets due to errors getting last price: ", bd_mkts
        
        self._price_graph = G


    def set_source(self, sourcename, source):
        self._sources[sourcename] = source
        self._generate_graph() # TODO: just add new edges


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
