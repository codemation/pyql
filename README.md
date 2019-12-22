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
   ('column name', str|int|float|byte, None|AUTO_INCREMENT|NOT NULL|OTHERS(not listed)
    
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
   Result:
    
        mysql> describe stocks;
        +-----------+---------+------+-----+---------+----------------+
        | Field     | Type    | Null | Key | Default | Extra          |
        +-----------+---------+------+-----+---------+----------------+
        | order_num | int(11) | NO   | PRI | NULL    | auto_increment |
        | date      | text    | YES  |     | NULL    |                |
        | trans     | text    | YES  |     | NULL    |                |
        | symbol    | text    | YES  |     | NULL    |                |
        | qty       | double  | YES  |     | NULL    |                |
        | price     | text    | YES  |     | NULL    |                |
        +-----------+---------+------+-----+---------+----------------+
        6 rows in set (0.00 sec)
    
### Insert Data
Requires key-value pairs - may be input using dict or the following
    
        trade = {'date': '2006-01-05', 'trans': 'BUY', 'symbol': 'RHAT', 'qty': 100.0, 'price': 35.14}
        db.tables['stocks'].insert(**trade)
        
        
        db.tables['stocks'].insert(
            date='2006-01-05', # Note order_num was not required as auto_increment was specified
            trans='BUY',
            symbol='RHAT',
            qty=100.0,
            price=35.14
        )
        
### Select Data

        sel = db.tables['stocks'].select('*', where={'symbol': 'RHAT'})
        print(sel)
    
Result:
    
        [{'order_num': 1, 'date': '2006-01-05', 'trans': 'BUY', 'symbol': 'RHAT', 'qty': 100.0, 'price': '35.14'}]
    
### Update Data
    
        db.tables['stocks'].update(symbol='NTAP',trans='SELL', where={'order_num': 1})
        sel = db.tables['stocks'].select('*', where={'order_num': 1})
        
Result:

    db.tables['stocks'].update(symbol='NTAP',trans='SELL', where={'order_num': 1})
    sel = db.tables['stocks'].select('*', where={'order_num': 1})

Result:

        [{'order_num': 1, 'date': '2006-01-05', 'trans': 'SELL', 'symbol': 'NTAP', 'qty': 100.0, 'price': '35.14'}]

### Delete Data 

    db.tables['stocks'].delete(where={'order_num': 1})
