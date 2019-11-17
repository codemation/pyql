import data, os, unittest


class TestData(unittest.TestCase):
    def test_run_mysql_test(self):
        import mysql.connector
        os.environ['DB_USER'] = 'testuser'
        os.environ['DB_PASSWORD'] = 'abcd1234'
        os.environ['DB_HOST'] = '172.17.0.1' if not 'DB_HOST' in os.environ['DB_HOST'] else os.environ['DB_HOST']
        os.environ['DB_PORT'] = '3306'
        os.environ['DB_NAME'] = 'testdb'
        os.environ['DB_TYPE'] = 'mysql'

        env = ['DB_USER','DB_PASSWORD','DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_TYPE']
        conf = ['user','password','host','port', 'database', 'type']
        config = {cnfVal: os.getenv(dbVal).rstrip() for dbVal,cnfVal in zip(env,conf)}

        db = data.database(
            mysql.connector.connect, 
            **config
            )
        test(db)
    def test_run_sqlite_test(self):
        import sqlite3
        db = data.database(
            sqlite3.connect, 
            database="testdb"
            )
        test(db)

def test(db):
    assert str(type(db)) == "<class 'data.database'>", "failed to create data.database object)"
    db.run('drop table stocks')
    db.create_table(
        'stocks', 
        [    
            ('order_num', int, 'AUTO_INCREMENT'if db.type == 'mysql' else 'AUTOINCREMENT'),
            ('date', str),
            ('trans', str),
            ('symbol', str),
            ('qty', float),
            ('price', str),
            ('afterHours', bool)
        ], 
        'order_num' # Primary Key 
    )
    assert 'stocks' in db.tables, "table creation failed"
    colNames = ['order_num', 'date', 'trans', 'symbol', 'qty', 'price', 'afterHours']
    for col in colNames:
        assert col in db.tables['stocks'].columns

    trade = {'date': '2006-01-05', 'trans': 'BUY', 'symbol': 'RHAT', 'qty': 100.0, 'price': 35.14, 'afterHours': True}
    db.tables['stocks'].insert(**trade)
    #    OR
    # db.tables['stocks'].insert(
    #     date='2006-01-05', # Note order_num was not required as auto_increment was specified
    #     trans='BUY',
    #     symbol='NTAP',
    #     qty=100.0,
    #     price=35.14,
    #     afterHours=True
    # )


    # Select Data

    sel = db.tables['stocks'].select('*', where={'symbol':'RHAT'})
    print(sel)
    for col, value in trade.items():
        assert len(sel) > 0, f"selection should be greater than lenth 0, data was inserted"
        assert col in sel[0], f"missing column '{col}' in select return"
        assert str(value) == str(sel[0][col]), f"value {sel[0][col]} returned from select is not what was inserted {value}."

    
    
    # Update Data
    
    db.tables['stocks'].update(symbol='NTAP',trans='SELL', where={'order_num': 1})
    sel = db.tables['stocks'].select('*', where={'order_num': 1})[0]
    print(sel)
    assert sel['trans'] == 'SELL' and sel['symbol'] == 'NTAP', f"values not correctly updated"

    print(sel)

    # Delete Data 

    db.tables['stocks'].delete(where={'order_num': 1})
    sel = db.tables['stocks'].select('*', where={'order_num': 1})
    print(sel)
    assert len(sel) < 1, "delete should have removed order_num 1"