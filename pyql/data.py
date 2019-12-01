from contextlib import contextmanager
from collections import namedtuple

#Used for grouping columns with database class
col = namedtuple('col', ['name', 'type', 'mods'])

def get_db_manager(db_connect):
    @contextmanager
    def connect(*args, **kwds):
        # Code to acquire resource, e.g.:
        conn = db_connect(*args, **kwds)
        try:
            yield conn
        except:
            print(f'failed to yeild connection with params {kwds} using {db_connect} result {conn}')
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()
    return connect
def get_cursor_manager(connect_db, params={}):
    @contextmanager
    def cursor():
        connect_params = params
        with connect_db(**connect_params) as conn:
            c = conn.cursor()
            try:
                yield c
            finally:
                conn.commit()
    return cursor

class database:
    """
        Intialize with db connector & name of database. If database exists, it will be used else a new db will be created \n

        sqlite example:
            import sqlite3
            db = database(sqlite3.connect, "testdb")
        mysql example:
            import mysql.connector
            db = database(mysql.connector.connect, **config)
        
    """
    def __init__(self, db_con, **kw):
        self.connetParams =  ['user', 'password', 'database', 'host', 'port']
        self.connectConfig = {}
        for k,v in kw.items():
            if k in self.connetParams:
                self.connectConfig[k] = v
        self.db_con = db_con
        self.type = 'sqlite' if not 'type' in kw else kw['type']
        self.db_name = kw['database'] if 'database' in kw else 'NO_DB_NAME_PROVIDED'
        assert not self.db_name == 'NO_DB_NAME_PROVIDED', "NO_DB_NAME_PROVIDED"

        self.connect = get_db_manager(self.db_con)
        self.cursor = get_cursor_manager(self.connect, self.connectConfig) 
        self.tables = {}
        self.load_tables()
    def run(self, query):
        with self.cursor() as c:
            print(f'{self.db_name}.run cursor {c} {query}')
            try:
                result = c.execute(query)
                if result == None:
                    result = []
                    for v in c:
                        result.append(v)
                return result
            except Exception as e:
                print(repr(e))
                return repr(e)

    def get(self, query):
        print(f'{self.db_name}.get query: {query}')
        with self.cursor() as c:
            try:
                rows = []
                result = c.execute(query)
                if result == None:
                    result = []
                    for v in c:
                        result.append(v)
                    return result
                for row in result:
                    rows.append(row)
                return rows
            except Exception as e:
                print(repr(e))
    def load_tables(self):
        if self.type == 'mysql':
            def describe_table_to_col(column):
                typeTranslate = {'tinyint': bool, 'int': int, 'text': str, 'double': float, 'varchar': str}
                field = column[0]
                typ = None
                for k in typeTranslate:
                    if k in column[1]:
                        typ = typeTranslate[k]
                        break
                assert typ is not None, f'type not found in translate dict for {column}'
                Null = 'NOT NULL ' if column[2] == 'NO' else ''
                Key = 'PRIMARY KEY ' if column[3] == 'PRI' else ''
                Default = '' # TOODOO - check if this needs implementing
                Extra = column[5].upper()
                return col(field, typ, Null+Key+Extra)
            for table in self.run('show tables'):
                colsInTable = []
                for c in self.run(f'describe {table[0]}'):
                    colsInTable.append(describe_table_to_col(c))
                PrimaryKey = None
                for colItem in colsInTable: 
                    if 'PRIMARY KEY' in colItem.mods:
                        PrimaryKey = colItem.name
                self.create_table(table[0], colsInTable, PrimaryKey)
    def create_table(self,name, columns, prim_key=None):
        """
            Usage:
                    db.create_table(
                        'stocks_new_tb2', 
                        [
                            ('order_num', int, 'AUTOINCREMENT'),
                            ('date', str, None),
                            ('trans', str, None),
                            ('symbol', str, None),
                            ('qty', float, None),
                            ('price', str, None)
                            ], 
                        'order_num' # Primary Key
                    )
        """
        #Convert tuple columns -> named_tuples
        cols = []
        for c in columns:
            # Allows for len(2) tuple input ('name', int) --> converts to col('name', int, None)
            cols.append(col(*c) if len(c) > 2 else col(*c, None)) 
        self.tables[name] = table(name, self, cols, prim_key)


class table:
    def __init__(self, name, database, columns, prim_key = None):
        self.name = name
        self.database = database
        self.types = {int,str,float,bool,bytes}
        self.translation = {
            'integer': int,
            'text': str,
            'real': float,
            'boolean': bool,
            'blob': bytes 
        }
        self.columns = {}
        for c in columns:
            assert c.type in self.types, f'unknown type {c.type} in {c.name} {c}'
            assert c.name not in self.columns
            self.columns[c.name] = c
        if prim_key is not None:
            self.prim_key = prim_key if prim_key in self.columns else None
        self.create_schema()
    def get_schema(self):
        cols = '('
        for cName,col in self.columns.items():
            for k,v in self.translation.items():
                if col.type == v:
                    if len(cols) > 1:
                        cols = cols + ', '
                    if cName == self.prim_key and (k=='text' or k=='blob'):
                        cols = cols + '%s %s'%(col.name, 'VARCHAR(36)')
                    else:
                        cols = cols + '%s %s'%(col.name, k.upper())
                    if cName == self.prim_key:
                        cols = cols + ' PRIMARY KEY'                    
                    if col.mods is not None:
                        cols = cols + ' %s'%(col.mods)
        cols = cols + ' )'
        schema = """CREATE TABLE {name} {cols}""".format(name = self.name, cols=cols)
        return schema
    def create_schema(self):
        self.database.run(self.get_schema())
    def __where(self, kw):
        where_sel = ''
        index = 0
        if 'where' in kw:
            for k,v in kw['where'].items():
                assert k in self.columns, f'{k} is not a valid column in table {self.name}'
                if index < 1:
                    where_sel = "WHERE {col}={val}".format(
                        col = k,
                        val = v if self.columns[k].type is not str else "'"+v+"'"
                    )
                    index+=1
                else:
                    where_sel = where_sel + " AND {col}={val}".format(
                        col = k,
                        val = v if self.columns[k].type is not str else "'"+v+"'"
                    )
        return where_sel

        if 'where' in kw:
            assert kw['where'][0] in self.columns, "%s is not a valid column in table within 'where' statement %s"%(kw['where'][0], self.name)
            where_sel = ' ' + 'WHERE %s=%s'%(kw['where'][0], kw['where'][1] if self.columns[kw['where'][0]].type is not str else "'" +kw['where'][1] + "'")
        return where_sel

    def select(self, *selection, **kw):
        """
            Usage: returns list of dictionaries for each selection in each row. 
                sel = db.tables['stocks_new_tb2'].select('order_num','symbol', where={'trans': 'BUY'})
                    OR
                sel = db.tables['stocks_new_tb2'].select('*')
                for r in sel:
                    print(r)
        """
        if '*' in selection:
            selection = '*'
        else:
            for i in selection:
                assert i in self.columns, f"{i} is not a column in table {self.name}"
            selection = ','.join(selection)
        where_sel = self.__where(kw)
        orderby = ''
        if 'orderby' in kw:
            assert kw['orderby'] in self.columns
            orderby = ' ORDER BY '+ kw['orderby']
        query = 'SELECT {select_item} FROM {name} {where}{order}'.format(
            select_item = selection,
            name = self.name,
            where = where_sel,
            order = orderby
        )
        rows = self.database.get(query)

        #dictonarify each row result and return
        if selection is not '*':
            keys = selection.split(',') if ',' in selection else selection.split(' ')
        else:
            keys = list(self.columns.keys())
        toReturn = []
        for row in rows:
            r_dict = {}
            for i,v in enumerate(row):
                r_dict[keys[i]] = v if not self.columns[keys[i]].type == bool else bool(v)
            toReturn.append(r_dict)
        return toReturn
    def insert(self, **kw):
        """
            Usage:
                    db.tables['stocks_new_tb2'].insert(
                        date='2006-01-05',
                        trans='BUY',
                        symbol='RHAT',
                        qty=100.0,
                        price=35.14)
        """
        cols = '('
        vals = '('
        #checking input kw's for correct value types
        for cName, col in self.columns.items():
            if not cName in kw:
                if not col.mods == None:
                    if 'NOT NULL' in col.mods:
                        print(f'{cName} is a required field for INSERT in table {self.name}')
                        return
                continue
            try:
                if not col.type == bool:
                    kw[cName] = col.type(kw[cName])
                else:
                    try:
                        kw[cName] = col.type(int(kw[cName])) if self.database.type == 'mysql' else int(col.type(int(kw[cName])))
                    except:
                        #Input is string
                        if 'true' in kw[cName].lower():
                            kw[cName] = True if self.database.type == 'mysql' else 1
                        elif 'false' in kw[cName].lower():
                            kw[cName] = False if self.database.type == 'mysql' else 0
                        else:
                            print(f"Unsupported value {kw[cName]} provide for column type {col.type}")
                            del(kw[cName])
                            continue
                    
            except:
                print(f"Value provided for {cName} is not of the correct {col.type} type or could not be converted")
                return
            if len(cols) > 2:
                cols = cols + ', '
                vals = vals + ', '
            cols = cols + cName
            vals = vals + str(kw[cName] if col.type is not str else '"' + kw[cName] + '"' )

        cols = cols + ')'
        vals = vals + ')'

        query = f'INSERT INTO {self.name} {cols} VALUES {vals}'
        print(query)
        self.database.run(query)
    def update(self,**kw):
        """
            Usage:
                db.tables['stocks'].update(symbol='NTAP',trans='SELL', where=('order_num', 1))
        """
        for cName, col in self.columns.items():
            if not cName in kw:
                continue
            try:
                kw[cName] = col.type(kw[cName])
            except:
                print("Value provided for %s is not of the correct %s type or could not be converted"%(cName, col.type))
                return
        cols_to_set = ''
        for k,v in kw.items():
            if k.lower() == 'where':
                continue
            if len(cols_to_set) > 1:
                cols_to_set = cols_to_set + ', '
            cols_to_set = cols_to_set + '%s = %s'%(k,v if self.columns[k].type is not str else "'"+ v + "'")
        where_sel = self.__where(kw)
        query = 'UPDATE {name} SET {cols_vals} {where}'.format(
            name=self.name,
            cols_vals=cols_to_set,
            where=where_sel
        )
        print(query)
        self.database.run(query)
    def delete(self, all_rows=False, **kw):
        """
            Usage:
                db.tables['stocks'].delete(where=('order_num', 1))
                db.tables['stocks'].delete(all_rows=True)
        """
        where_sel = self.__where(kw)
        print(len(where_sel) < 1)
        if len(where_sel) < 1:
            assert all_rows, "where statment is required with DELETE, otherwise specify .delete(all_rows=True)"
        query = "DELETE FROM {name} {where}".format(
            name=self.name,
            where=where_sel
        )
        self.database.run(query)
#   TOODOO:
# - Add support for creating column indexes per tables
# - Add suppport for foreign keys & joins with queries
# - Determine if views are needed and add support
# - Support for transactions?

def run_mysql_test():
    import mysql.connector
    db = database(
        mysql.connector.connect,
        database='titanic',
        user='mysqluser',
        password='abcd1234',
        host='192.168.122.120',
        port='32043',
        type='mysql'
        )
    test(db)
def run_sqlite_test(dbName="testdb"):
    import sqlite3
    db = database(
        sqlite3.connect, 
        database=dbName
        )
    test(db)

def test(db):

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
    print(db.run('describe stocks'))
    trade = {'data': '2006-01-05', 'trans': 'BUY', 'symbol': 'RHAT', 'qty': 100.0, 'price': 35.14, 'afterHours': True if db.type == 'myql' else 1}
    db.tables['stocks'].insert(**trade)
    #    OR
    db.tables['stocks'].insert(
        date='2006-01-05', # Note order_num was not required as auto_increment was specified
        trans='BUY',
        symbol='NTAP',
        qty=100.0,
        price=35.14,
        afterHours=True
    )
    # Select Data

    sel = db.tables['stocks'].select('*', where={'symbol':'RHAT'})
    print(sel)
    
    # Update Data
    
    db.tables['stocks'].update(symbol='NTAP',trans='SELL', where={'order_num': 1})
    sel = db.tables['stocks'].select('*', where={'order_num': 1})
    print(sel)

    # Delete Data 

    db.tables['stocks'].delete(where={'order_num': 1})