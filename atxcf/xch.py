import csv
import time

import accounts
from settings import (
    get_settings_option, get_settings, set_settings, set_option
)


def get_exchange_logfile_name():
    """
    Returns the exchange logfile name from the options.
    """
    return get_settings_option("exchange_log", "exchange.csv")


def exchange(swap_a, swap_b):
    """
    Exchanges an amount of an asset specified in swap_a,
    with that of the asset specified in swap_b.

    Both arguments are tuples of the form (user, asset, amount).
    """
    cur_time = time.time()
    accounts.transfer(swap_a[0], swap_b[0], swap_a[1], swap_a[2], cur_time, False)
    accounts.transfer(swap_b[0], swap_a[0], swap_b[1], swap_b[2], cur_time, False)

    # append to exchange log csv
    asset_pair = swap_a[1] + "/" + swap_b[1]
    rate = swap_b[2] / swap_a[2]
    fields=[cur_time, swap_a[0], swap_b[0], asset_pair, swap_a[2], swap_b[2], float(rate)]
    with open(get_exchange_logfile_name(), 'ab') as f:
        writer = csv.writer(f)
        writer.writerow(fields)

    accounts.sync_account_settings()
