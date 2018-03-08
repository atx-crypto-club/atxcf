from accounts import get_assets, get_balance
from PriceNetwork import get_prices, get_nav


def get_portfolio(name):
    """
    Returns a dict with the specified user's portfolio.
    """
    portfolio = {}
    for asset in get_assets(name):
        if asset != name:
            balance = get_balance(name, asset)
            if balance != 0.0:
                portfolio[asset] = balance
    return portfolio


def get_portfolio_values(name, base_asset):
    """
    Returns a dict with the prices of the assets in the
    named user's portfolio in terms of the base_asset.
    """
    port = get_portfolio(name)
    return get_prices(port, base_asset)


def get_portfolio_nav(name, base_asset):
    """
    Returns the specified portfolio's net asset value in
    terms of the base_asset.
    """
    return get_nav(get_portfolio(name), base_asset)

