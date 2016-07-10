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


class BaseModel(peewee.Model):
    class Meta:
        database = get_db()


class Source(BaseModel):
    name = peewee.CharField(primary_key=True)
    info = peewee.TextField(default="")


class Asset(BaseModel):
    name = peewee.CharField(primary_key=True)
    info = peewee.TextField(default="")


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


def store_asset(asset_name, asset_info=""):
    """
    Stores an asset in the database, then returns its model.
    """
    Asset.create_table(fail_silently=True)
    asset_model, asset_created = Asset.get_or_create(name=asset_name,
                                                     info=asset_info)
    asset_model.save()
    if asset_created:
        print "Stored asset %s" % asset_name
    return asset_model


def set_asset_info(asset_name, asset_info):
    """
    Sets the asset info.
    """
    # store/get the asset model
    asset_model = store_asset(asset_name, asset_info)
    asset_model.info = asset_info
    asset_model.save()


def get_asset_info(asset_name):
    """
    Returns the asset info
    """
    return Asset.get(Asset.name == asset_name).info


def store_source(source_name):
    """
    Stores a source in the database then returns its model.
    """
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
    # store/get the source model
    source_model = store_source(source_name)
    source_model.info = source_info
    source_model.save()


def get_source_info(source_name):
    """
    Returns source info.
    """
    return Source.get(Source.name == source_name).info


def store_sourceentry(source_name, mkt_pair):
    """
    Stores a source in the database.
    """
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
    Stores a price in the database.
    """
    print "Storing price for %s at %s" % (mkt_pair, source_name)
    sourceentry_model = store_sourceentry(source_name, mkt_pair)
    PriceEntry.create_table(fail_silently=True)
    db_price = PriceEntry(from_source=sourceentry_model,
                          price=price,
                          price_time=price_time)
    db_price.save()
    return db_price


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
