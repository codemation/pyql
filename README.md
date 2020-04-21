# pyql

A simple ORM(Object-relational mapping) for accessing, inserting, updating, deleting data within RBDMS tables using python

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

Un-packing

    # Note order_num is not required as auto_increment was specified
    trade = {'date': '2006-01-05', 'trans': 'BUY', 'symbol': 'RHAT', 'qty': 100.0, 'price': 35.14}
    db.tables['stocks'].insert(**trade)

    query:
        INSERT INTO stocks (date, trans, symbol, qty, price) VALUES ("2006-01-05", "BUY", "RHAT", 100, 35.14)

In-Line

    # Note order_num is not required as auto_increment was specified
    db.tables['stocks'].insert(
        date='2006-01-05', 
        trans='BUY',
        symbol='RHAT',
        qty=200.0,
        price=65.14
    )

    query:
        INSERT INTO stocks (date, trans, symbol, qty, price) VALUES ("2006-01-05", "BUY", "RHAT", 200, 65.14)

#### Inserting Special Data 
- Columns of type string can hold JSON dumpable python dictionaries as JSON strings and are automatically converted back into dicts when read. 
- Nested Dicts are also Ok, but all items should be JSON compatible data types


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
        query:
            INSERT INTO stocks (order_num, date, trans, symbol, qty, price, afterHours) VALUES (1, "2006-01-05", '{"type": "BUY", "condition": {"limit": "36.00", "time": "EndOfTradingDay"}}', "RHAT", 100, 35.14, True)
        result:
            In:
                db.tables['stocks'][1]['trans']['condition']
            Out: #
                {'limit': '36.00', 'time': 'EndOfTradingDay'}

        
### Select Data
#### Basic Usage:

All Rows & Columns in table

    db.tables['employees'].select('*')

All Rows & Specific Columns 

    db.tables['employees'].select('id', 'name', 'positionId')

All Rows & Specific Columns with Matching Values

    db.tables['employees'].select('id', 'name', 'positionId', where={'id': 1000})

All Rows & Specific Columns with Multple Matching Values

    db.tables['employees'].select('id', 'name', 'positionId', where={'id': 1000, 'name': 'Frank Franklin'})

#### Advanced Usage:

All Rows & Columns from employees, Combining ALL Rows & Columns of table positions (if foreign keys match)

    # Basic Join
    db.tables['employees'].select('*', join='positions'
    query:
        SELECT * FROM employees JOIN positions ON employees.positionId = positions.id
    output:
        [{
            'employees.id': 1000, 'employees.name': 'Frank Franklin', 
            'employees.positionId': 100101, 'positions.name': 'Director', 
            'positions.departmentId': 1001},
            ...
        ]
All Rows & Specific Columns from employees, Combining All Rows & Specific Columns of table positions (if foreign keys match)

    # Basic Join 
    db.tables['employees'].select('employees.name', 'positions.name', join='positions')
    query:
        SELECT employees.name,positions.name FROM employees JOIN positions ON employees.positionId = positions.id
    output:
        [
            {'employees.name': 'Frank Franklin', 'positions.name': 'Director'}, 
            {'employees.name': 'Eli Doe', 'positions.name': 'Manager'},
            ...
        ]

All Rows & Specific Columns from employees, Combining All Rows & Specific Columns of table positions (if foreign keys match) with matching 'position.name' value

    # Basic Join with conditions
    db.tables['employees'].select('employees.name', 'positions.name', join='positions', where={'positions.name': 'Director'})
    query:
        SELECT employees.name,positions.name FROM employees JOIN positions ON employees.positionId = positions.id WHERE positions.name='Director'
    output:
        [
            {'employees.name': 'Frank Franklin', 'positions.name': 'Director'}, 
            {'employees.name': 'Elly Doe', 'positions.name': 'Director'},
            ..
        ]

All Rows & Specific Columns from employees, Combining Specific Rows & Specific Columns of tables positions & departments4

Note: join='xTable' will only work if the calling table has a f-key reference to table 'xTable'

    # Multi-table Join with conditions
    db.tables['employees'].select(
        'employees.name', 
        'positions.name', 
        'departments.name', 
        join={
            'positions': {'employees.positionId': 'positions.id'}, 
            'departments': {'positions.departmentId': 'departments.id'}
        }, 
        where={'positions.name': 'Director'})
    query:
        SELECT employees.name,positions.name,departments.name FROM employees JOIN positions ON employees.positionId = positions.id JOIN departments ON positions.departmentId = departments.id WHERE positions.name='Director'
    result:
        [
            {'employees.name': 'Frank Franklin', 'positions.name': 'Director', 'departments.name': 'HR'}, 
            {'employees.name': 'Elly Doe', 'positions.name': 'Director', 'departments.name': 'Sales'}
        ]

Special Note: When performing multi-table joins, joining columns must be explicity provided. The key-value order is not explicity important, but will determine which column name is present in returned rows

    join={'yTable': {'yTable.id': 'xTable.yId'}}
    result:
        [
            {'xTable.a': 'val1', 'yTable.id': 'val2'},
            {'xTable.a': 'val1', 'yTable.id': 'val3'}
        ]
OR

    join={'yTable': {'xTable.yId': 'yTable.id'}}
    result:
        [
            {'xTable.a': 'val1', 'xTable.yId': 'val2'},
            {'xTable.a': 'val1', 'xTable.yId': 'val3'}
        ]


#### Special Examples:

Bracket indexs can only be used for primary keys and return all column values

    db.tables['employees'][1000]
    query:
        SELECT * FROM employees WHERE id=1000
    result:
        {'id': 1000, 'name': 'Frank Franklin', 'positionId': 100101}
    

Iterate through table - grab all rows - allowing client side filtering 

    for row in db.tables['employees']:
        print(row['id], row['name'])
    query:
        SELECT * FROM employees
    result:
        1000 Frank Franklin
        1001 Eli Doe
        1002 Chris Smith
        1003 Clara Carson
    
Using list comprehension

    sel = [(row['id'], row['name']) for row in db.tables['employees']]
    query:
        SELECT * FROM employees
    result:
        [
            (1000, 'Frank Franklin'), 
            (1001, 'Eli Doe'), 
            (1002, 'Chris Smith'), 
            (1003, 'Clara Carson'),
            ...
        ]


### Update Data

Define update values in-line or un-pack

    db.tables['stocks'].update(symbol='NTAP',trans='SELL', where={'order_num': 1})
    query:
        UPDATE stocks SET symbol = 'NTAP', trans = 'SELL' WHERE order_num=1

Un-Pack

    #JSON capable Data 
    txData = {'type': 'BUY', 'condition': {'limit': '36.00', 'time': 'EndOfTradingDay'}}
    toUpdate = {'symbol': 'NTAP', 'trans': txData}
    where = {'order_num': 1}

    db.tables['stocks'].update(**toUpdate, where=where)
    query:
        UPDATE stocks SET symbol = 'NTAP', trans = '{"type": "BUY", "condition": {"limit": "36.00", "time": "EndOfTradingDay"}}' WHERE order_num=1

Bracket Assigment - Primary Key name assumed inside Brackets for value

    #JSON capable Data 

    txData = {'type': 'BUY', 'condition': {'limit': '36.00', 'time': 'EndOfTradingDay'}}
    toUpdate = {'symbol': 'NTAP', 'trans': txData, 'qty': 500}

    db.tables['stocks'][2] = toUpdate

    query:
        # check that primary_key value 2 exists
        SELECT * FROM stocks WHERE order_num=2

        # update 
        UPDATE stocks SET symbol = 'NTAP', trans = '{"type": "BUY", "condition": {"limit": "36.00", "time": "EndOfTradingDay"}}', qty = 500 WHERE order_num=2

    result:
        db.tables['stocks'][2]
        {
            'order_num': 2, 
            'date': '2006-01-05', 
            'trans': {'type': 'BUY', 'condition': {'limit': '36.00', 'time': 'EndOfTradingDay'}}, 
            'symbol': 'NTAP', 
            'qty': 500, 
            'price': 35.16, 
            'afterHours': True
        }


### Delete Data 

    db.tables['stocks'].delete(where={'order_num': 1})

### Other
Table Exists

    'employees' in db
    query:
        show tables
    result:
        True

Primary Key Exists:

    1000 in db.tables['employees']
    query:
        SELECT * FROM employees WHERE id=1000
    result:
        True

