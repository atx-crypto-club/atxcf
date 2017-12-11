import accounts
import cmd


def get_portfolio(name):
    portfolio = {}
    for asset in accounts.get_assets(name):
        if asset != name:
            portfolio[asset] = accounts.get_balance(name, asset)
    return portfolio


def get_portfolio_values(name, base_asset):
    port = get_portfolio(name)
    values = {}
    for asset, balance in port.iteritems():
        if asset != name:
            price = cmd.get_price(balance, asset, base_asset)
            values[asset] = (balance, price)
    return values


def get_portfolio_nav(name, base_asset):
    values = get_portfolio_values(name, base_asset)
    total = 0.0
    for asset, value in values.iteritems():
        if asset != name:
            total += value[1]
    return total

