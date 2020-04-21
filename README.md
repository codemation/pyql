# pyql

Simple python database orchestration utility which makes it easy to add tables, insert, select, update, delete items with tables

### Instalation

    $ python3 -m venv env

    $ source my-project/bin/activate

Install with PIP

     (env)$ pip install pyql-db   

Download & install Library from Github:

    (env)$ git clone https://github.com/codemation/pyql.git

Use install script to install the pyql into the activated environment libraries

    (env)$ cd pyql; sudo ./install.py install

### Compatable Databases - Currently

- mysql
- sqlite

## Getting Started 

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
Existing tables schemas within databases are loaded when database object is instantiated and ready for use immedielty.

### Table Create
Requires List of at least 2 item tuples, max 3

('ColumnName', type, 'modifiers')
- ColumnName - str - database column name exclusions apply
- types: str, int, float, byte, bool, None # JSON dumpable dicts fall under str types
- modifiers: NOT NULL, UNIQUE, AUTO_INCREMENT

Note Some differences may apply for column options i.e AUTOINCREMENT(sqlite) vs AUTO_INCREMENT(mysql) - 
See DB documentation for reference.

Note: Unique constraints are not validated by pyql but at db, so if modifier is supported it will be added when table is created.

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

#### Creating Tables with Foreign Keys

    db.create_table(
        'departments', 
        [    
            ('id', int, 'UNIQUE'),
            ('name', str)

        ], 
        'id' # Primary Key 
    )

    db.create_table(
        'positions', 
        [    
            ('id', int, 'UNIQUE'),
            ('name', str),
            ('departmentId', int)
        ], 
        'id', # Primary Key
        fKeys={
            'departmentId': {
                    'table': 'departments', 
                    'ref': 'id',
                    'mods': 'ON UPDATE CASCADE ON DELETE CASCADE'
            }
        }
    )

    db.create_table(
        'employees', 
        [    
            ('id', int, 'UNIQUE'),
            ('name', str),
            ('positionId', int)
        ], 
        'id', # Primary Key
        fKeys={
            'positionId': {
                    'table': 'positions', 
                    'ref': 'id',
                    'mods': 'ON UPDATE CASCADE ON DELETE CASCADE'
            }
        }
    )

    
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

#### Inserting Special Data 
Columns of type string can hold JSON dumpable python dictionaries as JSON strings and are automatically converted back into dicts when read. Nested Dicts are also Ok, but all items should be JSON compatible data types

        txData = {
            'type': 'BUY', 
            'condition': {
                        'limit': '36.00', 
                        'time': 'EndOfTradingDay'
                    }
        }

        trade = {
            'order_num': 1, 'date': '2006-01-05', 
            'trans': txData, # 
            'symbol': 'RHAT', 
            'qty': 100, 'price': 35.14, 'afterHours': True
            }

        db.tables['stocks'].insert(**trade)
    
        
### Select Data
Usage:

    db.tables['table'].select('*')

    db.tables['table'].select('col1', 'col2', 'col3')

    db.tables['table'].select('col1', 'col2', 'col3')

    db.tables['table'].select('col1', 'col2', 'col3', where={'col1': 'val1'})


#### Examples:

    tb = db.tables['stocks']

Bracket indexs can only be used for primary keys and return all column values 

    sel = tb[0] # Select * from stocks where order_num = 1

If using WHERE condition for non-primary key column, where={'col': val} is required

    sel = tb.select('*', where={'symbol': 'RHAT'}) # select * from stocks where symbol = 'RHAT'

Iterate through table - grab all rows

    sel = [row for row in tb] # select * from stocks

    In:
        print(sel)
    Out:
        [
            {'order_num': 1, 'date': '2006-01-05', 'trans': 'BUY', 'symbol': 'RHAT', 'qty': 100.0, 'price': '35.14'},
            {'order_num': 2, 'date': '2006-01-06', 'trans': 'BUY', 'symbol': 'RHAT', 'qty': 100.0, 'price': '35.14'},
            ..
        ]

#### Join Usage:

    joinSel = db.tables['employees'].select(
        '*', 
        join={
            'positions': {'employees.positionId': 'positions.id'},
            'departments': {'positions.departmentId': 'departments.id'}
            },
        where={
            'positions.name': 'Director',
            'departments.name': 'HR'
            }
    )

resulting query:

        SELECT * FROM employees JOIN positions ON employees.positionId = positions.id JOIN departments ON positions.departmentId = departments.id WHERE positions.name='Director' AND departments.name='HR'
    
Auto foreign-key usage - will detect foreign key relationship if exists

    db.tables['employees'].select('*', join='positions')

resulting query:

        SELECT * FROM employees JOIN positions ON employees.positionId = positions.id


### Update Data
Define update values in-line or un-pack

    tb = db.tables['stocks']

    tb.update(
        symbol='NTAP',trans='SELL', 
        where={'order_num': 1})

OR

    # Un-Pack
    toUpdate = {'symbol': 'NTAP', 'trans': 'SELL'}
    where = {'order_num': 1}

    tb.update(
        **toUpdate,
        where=where
    )

OR

    # Primary-Key - Where [] 
    tb[1] = toUpdate # Primary Key is assumed in brackets 
    tb[1] = {'qty': 200}

### Delete Data 

    db.tables['stocks'].delete(where={'order_num': 1})
