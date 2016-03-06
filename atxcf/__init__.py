#!/usr/bin/env python
# -*- coding: utf-8 -*-

# such atxcf bot
# MMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMM
# MMMMMMMMMMMMMMMMMMMMMMMN0OKMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMM
# MMMMMMMMMMMMMMMMMMMMMMW0kxd0MMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMWNNNWMMMMMMMMMMM
# MMMMMMMMMMMMMMMMMMMMMMN0OxooKMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMN0xxdodXMMMMMMMMMM
# MMMMMMMMMMMMMMMMMMMMMMN0kxoooOWMMMMMMMMMMMMMMMMMMMMMMMMMMNOkdoolccdWMMMMMMMMM
# MMMMMMMMMMMMMMMMMMMMMMNOkxooookWMMMMMMMMMMMMMMMMMMMMMMMN0kddddolc:cOMMMMMMMMM
# MMMMMMMMMMMMMMMMMMMMMMNOkxollodxKWMMMMMMMMMMMMMMMMMMMN0kdodoolllcc:dMMMMMMMMM
# MMMMMMMMMMMMMMMMMMMMMMKxdddddxxxxk00KKXNNNNNWWWMMMMN0xdlloolccccclclWMMMMMMMM
# MMMMMMMMMMMMMMMMMMMMMNkxxkkkkkkkkkxxxxxkkkxxxxxxxxxddl:colc::;;:clllWMMMMMMMM
# MMMMMMMMMMMMMMMMMMMNKOOOOOOkkkxxxddxxxxkkkkkkxxxdlllc:cooc;,..':llclWMMMMMMMM
# MMMMMMMMMMMMMMMWNKOO000000OOkkxdddddxxxxxxxxxxxxxxl:::lool:'..,clllxMMMMMMMMM
# MMMMMMMMMMMMWNK0000OOO00000Okxdodxxxxxxxxxxxxxxxxxxxocclc,...,:ooooXMMMMMMMMM
# MMMMMMMMMMWX000000OOO000000Okxoddxxxkkkkxxxxxxxxxxxxkxoc'..';coolcdMMMMMMMMMM
# MMMMMMMMMN0000000OOOOOkO0OOkddoddxkOOOOOkxxdddxxxxxxkkkxdl:llooccoxWMMMMMMMMM
# MMMMMMMMN0000K00kc,..;dkOkxxddddxkOOOOOOkkxxdddxxxxxkkkkkkxdooolclo0MMMMMMMMM
# MMMMMMMMK0KXNNX0dl,'.':kkkkkkxkkkkOOkkkdxxxxxxddxxxxkkkkOOOkxdoc::lx0WMMMMMMM
# MMMMMMMWKKNNNXK0ol''.;xkOOOkOOOkxxxdl;;;..'cddxxxxxkkkkkkkkkkxdo:;cdxXMMMMMMM
# MMMMMMMXXNNNNK0OxoloxOOOOOOOOOkxol;..dl.... 'ldxxkkkkkkkkkkkkxxdocldx0MMMMMMM
# MMMMMMWXNNNNXKOOO000OO00000OOOOxol,.'l,.. .;lxkkkOOOOkkkkkkkkkxxddddxkWMMMMMM
# MMMMMMNXNNXXXXKKK0000OOO000OOOkkxxxdlllccodkOOOO0K0000OOOOOOOkkkxxdxxxKMMMMMM
# MMMMMNXXXXXXKOxollloodkOO000OOOkkkkkkxxkkkkkOOO000K00OOO000OOOOOkxxxxkONMMMMM
# MMMMWKXXXXX0'........';o000000OOOkO0OOOkkOOOOO000KKK000000000OOOkkkxkkk0MMMMM
# MMMMXKXKKXXO,...     ..:O0K0000OOOO000000000O000000000000000OOOOkkxxkkkkXMMMM
# MMMWKXXKXK0d,.....   .'lkOO0OOOOOOO00000000000000000000OOOOOOkkkxddxxkkkONMMM
# MMMW0KKK00ko:'.......,lokkkOOOOOkO00000O000000000000OOOOkkkkkkkxxddxxxkkk0MMM
# MMMWKXXKKOxl;,'.....,:lddxxkkkkkkkOOOOOOOOOOOOOOOOOOkkkkkkkkkkxxddddxxxxkOXMM
# MMMMKKXXK0ko:,....'',;lodxxkxxkkxxxkkkkkkOOkkkkOOOkkkOOOOOOOkkxddddxxddxkk0WM
# MMMMNKXKKK0Oc,........'codxxxdollclxxkkkkkkkOOOOkkkOO000OOOOOkkxddxxdddxxkOXM
# MMMMWXKKKK00koc,'.........,''.'';:oxkkkkkkOOOOOOOOOOOOOOOOOkkxdddddddddxxkkOW
# MMMMMWKKKKK00Oxoc:ccccc:;;cccllloxkkkkkkkkkOOOOOOOOOOOOOkkkkxxdddddoooddxxkkK
# MMMMMMNKKKK0OOOOxdddddxxddxdxxxkkkkkkkkkkkkkkOOOOOOOOOkkkkxxdddddddoooodxxxkO
# MMMMMMMXKK000000OOOOOkkkkkkkkkkkxkxxxxkkkkkkkOOOOOOOkkkxxxxdddddooooooddddxkO
# MMMMMMWK0000000OOOOOOkkkkkkkkxkxxxxxxkkkkOOOOOOOOOkOkkkkxxxdddoollloooddddxkk
# MMMMMMNK0O00000OOOOOOOOkkkkkkxxkkxxkxkkOOOOOOOOOkkkkkkkkkxxddoollloodddxxxkkO
# MMMMMMXK00OOOOOOOOOOkkkkkkkkxkkxkkxxxxkOOOOOOOkkkkkkkkkkxxxddooooodxxxxkkkOOO
# MMMMMWKK000OOOOOOOOOOkkkkkkxkkxxxxxxxxxkxxxkkxxkkkkkkkkkkxxdddddddxxkkkkOOkO0
# MMMMMNKK00000OOOkkkkkkkkkkkxxxxxxxxxxxxxddxxkkkkkkkxkkkkxxxxdxxkkkkOOOOOOOOO0
# MMMMMNKKK00000OOOOkkxddddxxddddddddddddxxkkkkkkkOkkkkkkkkxxkkOOOOOOOOOOOOOOO0
# MMMMMNKKKKK000OOOOOkxxdddddddddodddxxxxkkkOOkkkOkkkOkkkkkkkOOO0OO000000OOOOOO

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
