
### ETL Flow with pygrametl - SQLite database & CSV to PostgreSQL[dw] database. - currently do not load table content
# https://chrthomsen.github.io/pygrametl/doc/quickstart/beginner.html?utm_source=xp&utm_medium=blog&utm_campaign=content


# psycopg2 is a database driver allowing CPython to access PostgreSQL
import psycopg2

# sqlite3 is a database driver allowing CPython to access SQLite
import sqlite3

# pygrametl's __init__ file provides a set of helper functions and more
# importantly the class ConnectionWrapper for wrapping PEP 249 connections
import pygrametl

# pygrametl makes it simple to read external data through datasources
from pygrametl.datasources import SQLSource, CSVSource

# Interacting with the dimensions and the fact table is done through a set
# of classes. A suitable object must be created for each table
from pygrametl.tables import CachedDimension, FactTable

# Opening of connections and creation of a ConnectionWrapper
sale_conn = sqlite3.connect("sale.sqlite",
        detect_types=sqlite3.PARSE_DECLTYPES)

# Connect to the PostgreSQL database
dw_string = "host='localhost' dbname='dw' user='dwuser' password='dwpass'"
dw_conn = psycopg2.connect(dw_string)
dw_conn_wrapper = pygrametl.ConnectionWrapper(connection=dw_conn)

### Extract & Transform

# Creation of data sources for the sales database and the CSV file
# containing extra information about cities and regions in Denmark
name_mapping = 'book', 'genre', 'city', 'date', 'sale'
query = "SELECT book, genre, store, date, sale FROM sale"
sale_source = SQLSource(connection=sale_conn, query=query,
        names=name_mapping)

region_file_handle = open('region.csv', 'r', 16384, "utf-8")
region_source = CSVSource(f=region_file_handle, delimiter=',')

# Creation of dimension and fact table abstractions for use in the ETL flow
book_dimension = CachedDimension(
        name='book',
        key='bookid',
        attributes=['book', 'genre'])

time_dimension = CachedDimension(
        name='time',
        key='timeid',
        attributes=['day', 'month', 'year'])

location_dimension = CachedDimension(
        name='location',
        key='locationid',
        attributes=['city', 'region'],
        lookupatts=['city'])

fact_table = FactTable(
        name='sale',
        keyrefs=['bookid', 'locationid', 'timeid'],
        measures=['sale'])

# Python function needed to split the date into its three parts
def split_date(row):
    """Splits a date represented by a datetime into its three parts"""

    # Splitting of the date into parts
    date = row['date']
    row['year'] = date.year
    row['month'] = date.month
    row['day'] = date.day

# The location dimension is loaded from the CSV file
[location_dimension.insert(row) for row in region_source]

# The file handle for the CSV file can then be closed
region_file_handle.close()

# Each row in the sales database is iterated through and inserted
for row in sale_source:

    # Each row is passed to the date split function for splitting
    split_date(row)

    # Lookups are performed to find the key in each dimension for the fact
    # and if the data is not there, it is inserted from the sales row
    row['bookid'] = book_dimension.ensure(row)
    row['timeid'] = time_dimension.ensure(row)

    # The location dimension is pre-filled, so a missing row is an error
    row['locationid'] = location_dimension.lookup(row)
    if not row['locationid']:
        raise ValueError("city was not present in the location dimension")

    # The row can then be inserted into the fact table
    fact_table.insert(row)

# The data warehouse connection is then ordered to commit and close
dw_conn_wrapper.commit()
dw_conn_wrapper.close()

# Finally, the connection to the sales database is closed
sale_conn.close()

