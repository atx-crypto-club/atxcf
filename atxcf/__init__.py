#!/usr/bin/env python
# -*- coding: utf-8 -*-

# atxcf bot

__title__   = 'atxcf'
__version__ = '0.1'
__author__ = 'Joe Rivera <transfix@sublevels.net>'
__repo__    = 'https://github.com/transfix/atxcf'
__license__ = 'The MIT License (MIT)'

from .PriceSource import (
    PriceSource, PriceSourceError, Bitfinex, Poloniex, CryptoAssetCharts,
    Bittrex, Conversions, AllSources, get_creds
)

from .PriceNetwork import (
    PriceNetwork, PriceNetworkError 
)

from .agent import main as start_agent
from .agent import init as init_agent
from .webapi import main as start_webapi
