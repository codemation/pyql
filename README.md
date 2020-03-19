# pyql

Simple python database orchestration utility which makes it easy to add tables, insert, select, update, delete items with tables

### Instalation

    $ python3 -m venv myproj

    $ source my-project/bin/activate

Install with PIP

     (myproj)$ pip install pyql-db   

Download & install Library from Github:

    (myproj)$ git clone https://github.com/codemation/pyql.git

Use install script to install the pyql into the activated environment libraries

    (myproj)$ cd pyql; sudo ./install.py install

### Compatable Databases - Currently

- mysql
- sqlite

## Getting Started 

Note Some differences may apply for column options i.e AUTOINCREMENT(sqlite) vs AUTO_INCREMENT(mysql)
See DB documentation for reference.

### DB connection

        import sqlite3
        db = database(
            sqlite3.connect, 
            database="testdb"
            )
    
        import mysql.connector

        db = database(
            mysql.connector.connect,
            database='mysql_database',
            user='mysqluser',
            password='my-secret-pw',
            host='localhost',
            type='mysql'
            )
    
### Table Create
Requires List of at least 2 item tuples, max 3

    ('ColumnName', type, 'modifiers')
        ColumnName - str - database column name exclusions apply
        types: str, int, float, byte, bool, None # JSON dumpable dicts fall under str types
        modifiers: NOT NULL, UNIQUE, AUTO_INCREMENT
    Note: constraints are not validated by pyql but at db, so if modifier is supported it will be added when table is created.

    # Table Create    
    db.create_table(
        'stocks', 
        [    
            ('order_num', int, 'AUTO_INCREMENT'),
            ('date', str),
            ('trans', str),
            ('symbol', str),
            ('qty', float),
            ('price', str)
        ], 
        'order_num' # Primary Key 
    )
    
    mysql> describe stocks;
    +-----------+---------+------+-----+---------+----------------+
    | Field     | Type    | Null | Key | Default | Extra          |
    +-----------+---------+------+-----+---------+----------------+
    | order_num | int(11) | NO   | PRI | NULL    | auto_increment |
    | date      | text    | YES  |     | NULL    |                |
    | trans     | text    | YES  |     | NULL    |                |
    | condition | text    | YES  |     | NULL    |                |
    | symbol    | text    | YES  |     | NULL    |                |
    | qty       | double  | YES  |     | NULL    |                |
    | price     | text    | YES  |     | NULL    |                |
    +-----------+---------+------+-----+---------+----------------+
    6 rows in set (0.00 sec)
    
### Insert Data
Requires key-value pairs - may be input using dict or the following

    tb = db.tables['stocks']

    trade = {'date': '2006-01-05', 'trans': 'BUY', 'symbol': 'RHAT', 'qty': 100.0, 'price': 35.14}
    tb.insert(**trade)
    tb.insert(
        date='2006-01-05', # Note order_num was not required as auto_increment was specified
        trans='BUY',
        symbol='RHAT',
        qty=100.0,
        price=35.14
    )

    # Special Data 
    Columns of type string can hold JSON dump-able python dictionaries as JSON strings and are automatically converted back into dicts when read.

    txData = {
        'type': 'BUY', 
        'condition': {'limit': '36.00', 'time': 'EndOfTradingDay'} #  Dict Value 
        }
    
        
### Select Data
Use * for all columns
Use col1,col2,col3 to select specific columns

    tb = db.tables['stocks']

    # Bracket indexs can only be used for primary keys and return all column values 
    sel = tb[0] # Select * from stocks where order_num = 1

    # If using WHERE condition for non-primary key column, where={'col': <val>} is required
    sel = tb.select('*', where={'symbol': 'RHAT'}) # select * from stocks where symbol = 'RHAT'

    # Iterate through table - grab all rows
    sel = [row for row in tb] # select * from stocks

    In:
        print(sel)
    Out:
        [
            {'order_num': 1, 'date': '2006-01-05', 'trans': 'BUY', 'symbol': 'RHAT', 'qty': 100.0, 'price': '35.14'},
            {'order_num': 2, 'date': '2006-01-06', 'trans': 'BUY', 'symbol': 'RHAT', 'qty': 100.0, 'price': '35.14'},
            ..
        ]


### Update Data

    Define update values in-line or un-pack

        tb = db.tables['stocks']

        # in-line
        tb.update(
            symbol='NTAP',trans='SELL', 
            where={'order_num': 1})

        is the same as 

        # Un-Pack
        toUpdate = {'symbol': 'NTAP', 'trans': 'SELL'}
        where = {'order_num': 1}

        tb.update(
            **toUpdate,
            where=where
        )

        is the same as 

        # Primary-Key - Where [] 
        tb[1] = toUpdate # Primary Key is assumed in brackets 
        tb[1] = {'qty': 200}

### Delete Data 

    db.tables['stocks'].delete(where={'order_num': 1})
