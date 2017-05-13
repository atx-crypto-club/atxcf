import peewee
from settings import get_settings_option
import datetime
import string


class PriceDBError(RuntimeError):
    pass


def using_mysql():
    """
    Returns True if settings says to use mysql, else returns False.
    """
    return get_settings_option("using_mysql", False)


def get_mysql_hostname():
    """
    Returns the mysql hostname from the settings file.
    """
    return get_settings_option("mysql_hostname", "localhost")


def get_mysql_username():
    """
    Returns the mysql user to use when connecting to a server.
    """
    return get_settings_option("mysql_username", "atxcf")


def get_mysql_password():
    """
    Returns the mysql password to use when connecting to a server
    """
    return get_settings_option("mysql_password", "")


def get_mysql_db():
    """
    Returns the mysql database to use on the server.
    """
    return get_settings_option("mysql_db", "atxcf")


def sqlight_db_file():
    """
    Returns the sqlight file to use if we are using sqlight.
    """
    return get_settings_option("sqlight_db", "atxcf.db")


def readonly():
    """
    Returns whether we are in readonly mode.
    """
    return get_settings_option("pricedb_readonly", False)


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


_asset_types = {
    "cryptocurrency": 1,
    "fiatcurrency": 2,
    "cryptoasset": 3,
    "commodity": 4,
    "basket": 5
}


_source_types = {
    "exchange": 1,
    "website": 2,
    "programatic": 3
}


class BaseModel(peewee.Model):
    class Meta:
        database = get_db()


class Source(BaseModel):
    name = peewee.CharField(primary_key=True)
    info = peewee.TextField(default="")
    source_type = peewee.IntegerField(default=_source_types["exchange"])


class Asset(BaseModel):
    name = peewee.CharField(primary_key=True)
    info = peewee.TextField(default="")
    asset_type = peewee.IntegerField(default=_asset_types["cryptocurrency"])


class SourceEntry(BaseModel):
    source = peewee.ForeignKeyField(Source)
    from_asset = peewee.ForeignKeyField(Asset)
    to_asset = peewee.ForeignKeyField(Asset, related_name='base_assets')


class PriceEntry(BaseModel):
    from_source = peewee.ForeignKeyField(SourceEntry)
    price = peewee.DoubleField()
    price_time = peewee.DateTimeField(default=datetime.datetime.now)
       

def _get_assets_from_pair(mkt_pair):
    asset_strs = string.split(mkt_pair,"/",1)
    if len(asset_strs) != 2:
        raise PriceDBError("Invalid mkt pair %s" % mkt_pair)
    asset_strs = [cur.strip() for cur in asset_strs]
    return (asset_strs[0], asset_strs[1])


def store_asset(asset_name):
    """
    Stores an asset in the database, then returns its model.
    """
    if readonly():
        return # TODO: log this
    Asset.create_table(fail_silently=True)
    asset_model, asset_created = Asset.get_or_create(name=asset_name)
    asset_model.save()
    if asset_created:
        print "Stored asset %s" % asset_name
    return asset_model


def set_asset_info(asset_name, asset_info):
    """
    Sets the asset info.
    """
    if readonly():
        return # TODO: log this

    # store/get the asset model
    asset_model = store_asset(asset_name)
    asset_model.info = asset_info
    asset_model.save()


def get_asset_info(asset_name):
    """
    Returns the asset info
    """
    return Asset.get(Asset.name == asset_name).info


def set_asset_type(asset_name, asset_type):
    """
    Sets the asset type
    """
    if readonly():
        return # TODO: log this
    
    if type(asset_type) is str:
        asset_type = _asset_types[asset_type]
    asset_model = store_asset(asset_name)
    asset_model.asset_type = asset_type
    asset_model.save()


def get_asset_type(asset_name):
    """
    Returns the asset type.
    """
    return Asset.get(Asset.name == asset_name).asset_type


def store_source(source_name):
    """
    Stores a source in the database then returns its model.
    """
    if readonly():
        return # TODO: log this
    
    Source.create_table(fail_silently=True)
    source_model, source_model_created = Source.get_or_create(name=source_name)
    source_model.save()
    if source_model_created:
        print "Stored source %s" % source_name
    return source_model


def set_source_info(source_name, source_info):
    """
    Sets the source info
    """
    if readonly():
        return # TODO: log this

    # store/get the source model
    source_model = store_source(source_name)
    source_model.info = source_info
    source_model.save()


def get_source_info(source_name):
    """
    Returns source info.
    """
    return Source.get(Source.name == source_name).info


def set_source_type(source_name, source_type):
    """
    Sets the source type.
    """
    if readonly():
        return # TODO: log this
    
    if type(source_type) is str:
        source_type = _source_types[source_type]
    source_model = store_source(source_name)
    source_model.source_type = source_type
    source_model.save()


def get_source_type(source_name):
    """
    Gets the source type.
    """
    return Source.get(Source.name == source_name).source_type


def get_asset_names():
    """
    Returns a set of all the assets in the database.
    """
    assets = set()
    for asset in Asset.select():
        assets.add(asset.name)
    return assets


def get_source_names(mkt_pair=None):
    """
    Returns a set of all the source names in the database for sources that contain info
    about the specified market pair string. If none, return all source names.
    """
    source_names = set()
    if mkt_pair:
        from_asset, to_asset = _get_assets_from_pair(mkt_pair)
        from_asset_model = None
        to_asset_model = None
        for cur_asset in Asset.select().where(Asset.name == from_asset):
            from_asset_model = cur_asset
        for cur_asset in Asset.select().where(Asset.name == to_asset):
            to_asset_model = cur_asset
        for cur_se in SourceEntry.select().where(SourceEntry.from_asset == from_asset_model,
                                                 SourceEntry.to_asset == to_asset_model):
            source_names.add(cur_se.source.name)
    else:
        for cur_source in Source.select():
            source_names.add(cur_source.name)
    return source_names


def store_sourceentry(source_name, mkt_pair):
    """
    Stores a source in the database.
    """
    if readonly():
        return # TODO: log this
    
    source_model = store_source(source_name)
    from_asset, to_asset = _get_assets_from_pair(mkt_pair)
    from_asset_model = store_asset(from_asset)
    to_asset_model = store_asset(to_asset)
    
    SourceEntry.create_table(fail_silently=True)
    sourceentry_model, created = SourceEntry.get_or_create(source=source_model,
                                                           from_asset=from_asset_model,
                                                           to_asset=to_asset_model)
    sourceentry_model.save()
    if created:
        print "Stored source %s for %s" % (source_name, mkt_pair)
    return sourceentry_model
        

def store_price(source_name, mkt_pair, price, price_time=datetime.datetime.now()):
    """
    Stores a price in the database and returns it's price entry.
    """
    if readonly():
        return # TODO: log this
    
    sourceentry_model = store_sourceentry(source_name, mkt_pair)
    PriceEntry.create_table(fail_silently=True)

    # Check the last price taken from this source. If it is the same, lets
    # just update the timestamp instead of adding a lot of duplicate price data
    # for quiet markets. Else, just write the new price.
    last_price = None
    try:
        last_price = PriceEntry.select().where(PriceEntry.from_source == sourceentry_model) \
            .order_by(-PriceEntry.price_time).get()
    except:
        pass

    if last_price and last_price.price == price:
        print "No price change for %s in %s" % (mkt_pair, source_name)
        return last_price
    else:
        print "Storing price for %s at %s" % (mkt_pair, source_name)
        db_price = PriceEntry(from_source=sourceentry_model,
                              price=price,
                              price_time=price_time)
        db_price.save()
        return db_price


def get_last_price_pairs(mkt_pair):
    """
    Returns the last prices across all sources for the specified mkt_pair.
    """
    price_list = []
    from_asset, to_asset = _get_assets_from_pair(mkt_pair)
    from_asset_model = None
    to_asset_model = None
    for cur_asset in Asset.select().where(Asset.name == from_asset):
        from_asset_model = cur_asset
    for cur_asset in Asset.select().where(Asset.name == to_asset):
        to_asset_model = cur_asset
    for cur_se in SourceEntry.select().where(SourceEntry.from_asset == from_asset_model,
                                             SourceEntry.to_asset == to_asset_model):
        last_price = None
        try:
            last_price = PriceEntry.select().where(PriceEntry.from_source == cur_se) \
                .order_by(-PriceEntry.price_time).get()
        except:
            continue
        price_list.append((last_price.price_time, last_price.price))
    return price_list


def get_price_total_time_range(mkt_pair):
    """
    Returns the range of time for which we have prices saved for the specified
    market pair.
    """
    first_price = PriceEntry.select().order_by(+PriceEntry.price_time).get()
    last_price = PriceEntry.select().order_by(-PriceEntry.price_time).get()
    return (first_price.price_time, last_price.price_time)


def get_price_info(mkt_pair, timerange=(None, None), from_sources=[]):
    """
    Returns a 4-tuple containing the low, high, open, and close prices
    for the time range specified. If timerange is none, just return info for the last 1 minute of
    price info available. Else, None in the timerange tuple makes it open ended in that direction.
    You can specify the sources you only want to pull info from. If the list is empty, returns
    price info using all sources. 

    Becareful with this- sometimes price sources can vary significantly so we need to be sure 
    we're normalizing price info in a sane manner. By default we are averaging, but we might 
    consider weighting sources to account for distortion.
    """
    if timerange[0] == None or timerange[1] == None:
        first_price, last_price = get_price_total_time_range(mkt_pair)
        if timerange == (None, None):
            one_minute = datetime.timedelta(minutes=1)
            timerange = (last_price - one_minute, last_price)
        else:
            if timerange[0] == None:
                timerange[0] = first_price
            if timerange[1] == None:
                timerange[1] = last_price
                

    # TODO: handle from_sources
    query = PriceEntry.select().where(PriceEntry.price_time >= timerange[0],
                                      PriceEntry.price_time <= timerange[1])

    low_price = None
    high_price = None
    open_price = query.order_by(+PriceEntry.price_time).get().price
    close_price = query.order_by(-PriceEntry.price_time).get().price
    for price in query:
        if low_price == None:
            low_price = price.price
        if high_price == None:
            high_price = price.price
        if low_price > price.price:
            low_price = price.price
        if high_price < price.price:
            high_price = price.price

    return (low_price, high_price, open_price, close_price)


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
