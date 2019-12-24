import data, os, unittest, json


class TestData(unittest.TestCase):
    def test_run_mysql_test(self):
        import mysql.connector
        os.environ['DB_USER'] = 'testuser'
        os.environ['DB_PASSWORD'] = 'abcd1234'
        os.environ['DB_HOST'] = '172.17.0.1' if not 'DB_HOST' in os.environ else os.environ['DB_HOST']
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
    def check_sel(requested, selection):
        requestItems = []
        if requested == '*':
            requestItems = trade.keys()
        else:
            for request in requested:
                assert request in trade, f'{request} is not a valid column in {trade}'
                requestItems.append(request)
        
        for col, value in trade.items():
            if col in requestItems:
                assert len(selection) > 0, f"selection should be greater than lenth 0, data was inserted"
                assert col in selection[0], f"missing column '{col}' in select return"
                assert str(value) == str(sel[0][col]), f"value {selection[0][col]} returned from select is not what was inserted {value}."


    assert str(type(db)) == "<class 'data.database'>", "failed to create data.database object)"
    db.run('drop table stocks')
    db.create_table(
        'stocks', 
        [    
            ('order_num', int, 'AUTO_INCREMENT'if db.type == 'mysql' else 'AUTOINCREMENT'),
            ('date', str),
            ('trans', str),
            ('symbol', str),
            ('qty', int),
            ('price', float),
            ('afterHours', bool)
        ], 
        'order_num' # Primary Key 
    )
    assert 'stocks' in db.tables, "table creation failed"
    colNames = ['order_num', 'date', 'trans', 'symbol', 'qty', 'price', 'afterHours']
    for col in colNames:
        assert col in db.tables['stocks'].columns

    # JSON Load test
    txData = {'type': 'BUY', 'condition': {'limit': '36.00', 'time': 'EndOfTradingDay'}}

    trade = {'date': '2006-01-05', 'trans': txData, 'symbol': 'RHAT', 'qty': 100, 'price': 35.14, 'afterHours': True}

    # pre insert * select # 
    sel = db.tables['stocks'].select('*')
    assert not len(sel) > 0, "no values should exist yet"


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


    
    # * select # 
    sel = db.tables['stocks'].select('*')
    print(sel)
    check_sel('*', sel)


    # Partial insert

    partialTrade = {'date': '2006-01-05', 'trans': txData, 'price': 35.14, 'afterHours': True}

    db.tables['stocks'].insert(**partialTrade)

    # * select # 
    sel = db.tables['stocks'].select('*')
    print(sel)
    check_sel('*', sel)
    
    # * select + where # 
    sel = db.tables['stocks'].select('*', where={'symbol':'RHAT'})
    print(sel)
    check_sel('*', sel)

    # single select 
    sel = db.tables['stocks'].select('price', where={'symbol':'RHAT'})
    check_sel(['price'], sel)
    print(sel)
    # multi-select 
    sel = db.tables['stocks'].select('price', 'date', where={'symbol':'RHAT'})
    check_sel(['price', 'date'], sel)
    print(sel)
    
    # Update Data
    txOld = {'type': 'BUY', 'condition': {'limit': '36.00', 'time': 'EndOfTradingDay'}}
    txData['type'] = 'SELL'
    
    db.tables['stocks'].update(
        symbol='NTAP',trans=txData,
        afterHours=False, qty=101, 
        where={'order_num': 1, 'afterHours': True, 'trans': txOld})
    sel = db.tables['stocks'].select('*', where={'order_num': 1})[0]
    print(sel)
    assert sel['trans']['type'] == 'SELL' and sel['symbol'] == 'NTAP', f"values not correctly updated"

    print(sel)

    # Delete Data 

    db.tables['stocks'].delete(where={'order_num': 1, 'afterHours': False})
    sel = db.tables['stocks'].select('*', where={'order_num': 1, 'afterHours': False})
    print(sel)
    assert len(sel) < 1, "delete should have removed order_num 1"