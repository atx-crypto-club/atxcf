import peewee
import settings
import datetime
import string


class PriceDBError(RuntimeError):
    pass


def using_mysql():
    """
    Returns True if settings says to use mysql, else returns False.
    """
    if not settings.has_option("using_mysql"):
        settings.set_option("using_mysql", False)
    return settings.get_option("using_mysql")


def get_mysql_hostname():
    """
    Returns the mysql hostname from the settings file.
    """
    if not settings.has_option("mysql_hostname"):
        settings.set_option("mysql_hostname", "localhost")
    return settings.get_option("mysql_hostname")


def get_mysql_username():
    """
    Returns the mysql user to use when connecting to a server.
    """
    if not settings.has_option("mysql_username"):
        settings.set_option("mysql_username", "atxcf")
    return settings.get_option("mysql_username")


def get_mysql_password():
    """
    Returns the mysql password to use when connecting to a server
    """
    if not settings.has_option("mysql_password"):
        settings.set_option("mysql_password", "")
    return settings.get_option("mysql_password")


def get_mysql_db():
    """
    Returns the mysql database to use on the server.
    """
    if not settings.has_option("mysql_db"):
        settings.set_option("mysql_db", "atxcf")
    return settings.get_option("mysql_db")


def sqlight_db_file():
    """
    Returns the sqlight file to use if we are using sqlight.
    """
    if not settings.has_option("sqlight_db"):
        settings.set_option("sqlight_db", "atxcf.db")
    return settings.get_option("sqlight_db")


def get_db():
    """
    Returns the peewee database object to use for db I/O.
    """
    if using_mysql():
        return peewee.MySQLDatabase(get_mysql_db(),
                                    host=get_mysql_hostname(),
                                    user=get_mysql_username(),
                                    password=get_mysql_password())
    else:
        return peewee.SqliteDatabase(sqlight_db_file())


class PriceEntry(peewee.Model):
    source_name = peewee.CharField()
    from_asset = peewee.CharField()
    to_asset = peewee.CharField()
    price = peewee.DoubleField()
    price_time = peewee.DateTimeField()

    class Meta:
        database = get_db()


class SourceEntry(peewee.Model):
    source_name = peewee.CharField()
    from_asset = peewee.CharField()
    to_asset = peewee.CharField()

    class Meta:
        database = get_db()
       

def _get_assets_from_pair(mkt_pair):
    asset_strs = string.split(mkt_pair,"/",1)
    if len(asset_strs) != 2:
        raise PriceDBError("Invalid mkt pair %s" % mkt_pair)
    asset_strs = [cur.strip() for cur in asset_strs]
    return (asset_strs[0], asset_strs[1])


def store_source(source_name, mkt_pair):
    """
    Stores a source in the database.
    """
    SourceEntry.create_table(fail_silently=True)
    from_asset, to_asset = _get_assets_from_pair(mkt_pair)
    source, created = SourceEntry.get_or_create(source_name=source_name,
                                                from_asset=from_asset,
                                                to_asset=to_asset)
    source.save()
    if created:
        print "Stored source %s for %s" % (source_name, mkt_pair)
        

def store_price(source_name, mkt_pair, price, price_time=datetime.datetime.now()):
    """
    Stores a price in the database.
    """
    print "Storing price for %s at %s" % (mkt_pair, source_name)
    store_source(source_name, mkt_pair)
    from_asset, to_asset = _get_assets_from_pair(mkt_pair)
    PriceEntry.create_table(fail_silently=True)
    db_price = PriceEntry(source_name=source_name,
                          from_asset=from_asset,
                          to_asset=to_asset,
                          price=price,
                          price_time=price_time)
    db_price.save()


def has_stored_price(mkt_pair):
    """
    Check if a price has been stored for the specfied mkt_pair.
    """
    try:
        PriceEntry.get(PriceEntry.mkt_pair == mkt_pair)
    except:
        return False
    return True


def has_source(source_name):
    """
    Check if a specified source exists
    """
    # TODO: this isn't working as expected...
    try:
        SourceEntry.get(SourceEntry.source_name == source_name)
    except:
        return False
    return True


def get_last_price(mkt_pair):
    """
    Returns a tuple with (source_name, price, price_time)
    """
    if not has_stored_price(mkt_pair):
        raise PriceDBError("Missing price " + mkt_pair)

    prices = []
    # Collect all the last prices from each source
    # TODO: clean this up, it's a little ugly...
    for sources in SourceEntry.select().where(SourceEntry.mkt_pair == mkt_pair):
        for pe in PriceEntry.select().where(PriceEntry.source_name == sources.source_name,
                                            PriceEntry.mkt_pair == mkt_pair).order_by(-PriceEntry.price_time):
            prices.append((pe.source_name, pe.price, pe.price_time))
            break

    # Get newest time of all prices
    newest_time = prices[0][2]
    for price in prices:
        if newest_time < price[2]:
            newest_time = price[2]

    # Drop a price from the average if it is 5 minutes behind the newest source price
    # to minimize distortion of the average from volatile markets.
    timeout = datetime.timedelta(seconds=60*5)

    filtered_prices = []
    for price in prices:
        if price[2] >= newest_time - timeout:
            filtered_prices.append(price[1])

    # now average them and return
    return math.fsum(filtered_prices)/float(len(filtered_prices))


def get_last_stored_price_time(mkt_pair):
    """
    Returns the time of the last price for this market pair.
    """
    if not has_stored_price(mkt_pair):
        raise PriceDBError("Missing price " + mkt_pair)


    prices = []
    # Collect all the last prices from each source
    # TODO: clean this up, it's a little ugly...
    for sources in SourceEntry.select().where(SourceEntry.mkt_pair == mkt_pair):
        for pe in PriceEntry.select().where(PriceEntry.source_name == sources.source_name,
                                            PriceEntry.mkt_pair == mkt_pair).order_by(-PriceEntry.price_time):
            prices.append((pe.source_name, pe.price, pe.price_time))
            break

    # Get newest time of all prices
    newest_time = prices[0][2]
    for price in prices:
        if newest_time < price[2]:
            newest_time = price[2]

    return newest_time

