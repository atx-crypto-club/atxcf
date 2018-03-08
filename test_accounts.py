"""
Basic demo of how to use this module.
"""

import atxcf
import json

def print_portfolio_info(portfolio, base_asset="USD"):
    info = {
        "name": portfolio,
        "email": atxcf.get_user_email(portfolio),
        "base_asset": base_asset,
        "values": atxcf.get_portfolio_values(portfolio,
                                             base_asset),
        "NAV": atxcf.get_portfolio_nav(portfolio,
                                       base_asset),
        "has_shares": atxcf.has_shares(portfolio),
        "meta": atxcf.get_metadata(portfolio)
    }

    if atxcf.has_shares(portfolio):
        info.update({
            "num_shares": atxcf.get_num_shares_outstanding(portfolio),
            "num_shareholders": atxcf.get_num_shareholders(portfolio),
            "shareholders": atxcf.get_shareholders(portfolio),
            "nav_share_ratio": atxcf.get_portfolio_nav_share_ratio(portfolio,
                                                                   base_asset)
        })

    print json.dumps(info, sort_keys=True, indent=4,
                     separators=(',', ': '))


def print_portfolios():
    for portfolio in atxcf.get_users():
        print_portfolio_info(portfolio)


def print_banner(title):
    print "-"*80
    print title
    print "-"*80


# default domain for user email addresses
atxcf.set_domain("catx.io")


if not atxcf.has_user("catx_00"):
    atxcf.add_user("catx_00") # using create_shares

    
if not atxcf.has_user("catx_01"):
    atxcf.add_user("catx_01") # using grant_shares
    atxcf.set_balance("catx_01", "BTC", 12)
    atxcf.set_balance("catx_01", "LTC", 82)
    atxcf.set_balance("catx_01", "ETH", 132)
    

if not atxcf.has_user("transfix"):
    atxcf.add_user("transfix")
    atxcf.set_balance("transfix", "BTC", 1.0)
    atxcf.set_balance("transfix", "LTC", 4.20)
    atxcf.set_metadata_value("transfix", "data", "blahhh")
    
    
if not atxcf.has_user("sheldon"):
    atxcf.add_user("sheldon")
    atxcf.set_balance("sheldon", "BTC", 0.5)
    atxcf.set_balance("sheldon", "ETH", 14)


print_banner("START")
print_portfolios()

if atxcf.get_balance("transfix", "catx_00") <= 0.0:
    print_banner("create_shares catx_00 transfix")
    atxcf.create_shares("catx_00", "transfix", {"BTC": 0.432, "LTC": 4})
    print_portfolios()
    
if atxcf.get_balance("sheldon", "catx_00") <= 0.0:
    print_banner("create_shares catx_00 sheldon")
    atxcf.create_shares("catx_00", "sheldon", {"BTC": 0.322, "ETH": 4.22})
    print_portfolios()
    
if atxcf.get_balance("transfix", "catx_01") <= 0.0:
    print_banner("grant_shares catx_01 transfix")
    atxcf.grant_shares("catx_01", "transfix", 200)
    print_portfolios()
    
if atxcf.get_balance("sheldon", "catx_01") <= 0.0:
    print_banner("grant_shares catx_01 sheldon")
    atxcf.grant_shares("catx_01", "sheldon", 100)
    print_portfolios()

# limit orders for the book
#atxcf.limit_buy("transfix", "CATX/BTC", 221, 0.0007)
#atxcf.limit_buy("transfix", "CATX/BTC", 445, 0.0008)
#atxcf.limit_buy("sheldon", "CATX/BTC", 335, 0.0007)
#atxcf.limit_buy("sheldon", "CATX/BTC", 124, 0.00065)
#atxcf.limit_sell("transfix", "CATX/BTC", 221, 0.0015)
#atxcf.limit_sell("transfix", "CATX/BTC", 445, 0.0017)
#atxcf.limit_sell("sheldon", "CATX/BTC", 335, 0.002)
#atxcf.limit_sell("sheldon", "CATX/BTC", 124, 0.0019)

#print atxcf.orderbook("CATX/BTC")

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


