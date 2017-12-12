import atxcf

atxcf.add_user("FUND", "info@catx.io")
atxcf.add_user("transfix", "transfix@sublevels.net")
atxcf.add_user("sheldon", "sheldon@sublevels.net")

atxcf.set_metadata("transfix", {"data": "blahhhhhh"})

# initialize balances
atxcf.set_balance("transfix", "BTC", "1.0")
atxcf.set_balance("sheldon", "BTC", "0.5")

# exchange
atxcf.exchange(("FUND", "CATX", 1000), ("transfix", "BTC", 1))
atxcf.exchange(("FUND", "CATX", 500), ("sheldon", "BTC", 0.5))

# limit orders for the book
atxcf.limit_buy("transfix", "CATX/BTC", 221, 0.0007)
atxcf.limit_buy("transfix", "CATX/BTC", 445, 0.0008)
atxcf.limit_buy("sheldon", "CATX/BTC", 335, 0.0007)
atxcf.limit_buy("sheldon", "CATX/BTC", 124, 0.00065)
atxcf.limit_sell("transfix", "CATX/BTC", 221, 0.0015)
atxcf.limit_sell("transfix", "CATX/BTC", 445, 0.0017)
atxcf.limit_sell("sheldon", "CATX/BTC", 335, 0.002)
atxcf.limit_sell("sheldon", "CATX/BTC", 124, 0.0019)

print atxcf.orderbook("CATX/BTC")

# print atxcf.spread("CATX/BTC")

#print atxcf.get_orders("transfix", "CATX/BTC")
#print atxcf.get_orders("sheldon", "CATX/BTC")

# limit orders that resolve
# atxcf.limit_buy("transfix", "CATX/BTC", 20, 0.00195)
# atxcf.limit_sell("sheldon", "CATX/BTC", 4, 0.0007)

# print atxcf.orderbook("CATX/BTC")

# Print how much CATX can be had for 0.3 BTC according
# to the order book.
# print atxcf.ask_depth("CATX/BTC", 0.3)

# Print the total ask depth
# print atxcf.ask_depth("CATX/BTC")

# Print how much BTC can be had for 10 CATX according
# to the order book.
# print atxcf.bid_depth("CATX/BTC", 10)

# Print the total bid depth.
# print atxcf.bid_depth("CATX/BTC")

# market orders
# atxcf.market_buy("transfix", "CATX/BTC", 24)
# atxcf.market_sell("sheldon", "CATX/BTC", 15)


