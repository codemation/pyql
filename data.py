from contextlib import contextmanager
from collections import namedtuple

def get_db_manager(db_connect, db_name):
    @contextmanager
    def connect(*args, **kwds):
        # Code to acquire resource, e.g.:
        db_n = db_name
        conn = db_connect(db_n,*args, **kwds)
        try:
            yield conn
        except:
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()
    return connect
def get_cursor_manager(connect_db):
    @contextmanager
    def cursor():
        with connect_db() as conn:
            c = conn.cursor()
            try:
                yield c
            finally:
                conn.commit()
    return cursor

class database:
    def __init__(self, db_con, db_name):
        self.db_con = db_con
        self.db_name = db_name
        self.connect = get_db_manager(self.db_con, self.db_name)
        self.cursor = get_cursor_manager(self.connect)
        self.tables = {}
    def run(self, query):
        with self.cursor() as c:
            try:
                result = c.execute(query)
                return result
            except Exception as e:
                print(repr(e))
    def get(self, query):
        with self.cursor() as c:
            try:
                rows = []
                for row in c.execute(query):
                    rows.append(row)
                return rows
            except Exception as e:
                print(repr(e))
    def create_table(self,name, columns, prim_key=None):
        self.tables[name] = table(name, self, columns, prim_key)
col = namedtuple('col', ['name', 'type', 'mods'])

class table:
    def __init__(self, name, database, columns, prim_key = None):
        self.name = name
        self.database = database
        self.types = {int,str,float,bytes}
        self.translation = {
            'integer': int,
            'text': str,
            'real': float,
            'blob': bytes 
        }
        self.columns = {}
        for c in columns:
            print(c.type)
            assert c.type in self.types
            assert c.name not in self.columns
            self.columns[c.name] = c
        if prim_key is not None:
            self.prim_key = prim_key if prim_key in self.columns else None
        self.create_schema()
    def create_schema(self):
        cols = '('
        for cName,col in self.columns.items():
            for k,v in self.translation.items():
                if col.type == v:
                    if len(cols) > 1:
                        cols = cols + ', '
                    cols = cols + '%s %s'%(col.name, k.upper())
                    if cName == self.prim_key:
                        cols = cols + ' PRIMARY KEY'                    
                    if col.mods is not None:
                        cols = cols + ' %s'%(col.mods)
        cols = cols + ' )'
        schema = """CREATE TABLE {name} {cols}""".format(name = self.name, cols=cols)
        self.database.run(schema)
    def __where(self, kw):
        where_sel = ''
        if 'where' in kw:
            assert kw['where'][0] in self.columns, "%s is not a valid column in table within 'where' statement %s"%(kw['where'][0], self.name)
            where_sel = ' ' + 'WHERE %s=%s'%(kw['where'][0], kw['where'][1] if self.columns[kw['where'][0]].type is not str else "'" +kw['where'][1] + "'")
        return where_sel

    def select(self, selection, **kw):
        
        if ',' in selection:
            sels = ''.join(selection.split(' ')).split(',')
            for i in sels:
                assert i in self.columns, "%s is not a column in table %s"%(i, self.name)
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
            keys = sels if ',' in selection else ''.join(selection.split(' '))
        else:
            keys = list(self.columns.keys())
        toReturn = []
        for row in rows:
            r_dict = {}
            for i,v in enumerate(row):
                r_dict[keys[i]] = v
            toReturn.append(r_dict)

        return toReturn
    def insert(self, **kw):
        cols = '('
        vals = '('
        #checking input kw's for correct value types
        for cName, col in self.columns.items():
            if not cName in kw:
                if 'NOT NULL' in col.mods:
                    print(cName + ' is a required field for INSERT in table %s'%(self.name))
                    return
                continue
            try:
                kw[cName] = col.type(kw[cName])
            except:
                print("Value provided for %s is not of the correct %s type or could not be converted"%(cName, col.type))
                return
            if len(cols) > 2:
                cols = cols + ', '
                vals = vals + ', '
            cols = cols + cName
            vals = vals + str(kw[cName] if col.type is not str else "'" + kw[cName] + "'" )

        cols = cols + ')'
        vals = vals + ')'

        query = 'INSERT INTO {name} {columns} VALUES {values}'.format(
            name = self.name,
            columns = cols,
            values = vals
        )
        print(query)
        self.database.run(query)
    def update(self,**kw):
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


def run_test():
    import sqlite3
    db = database(sqlite3.connect, "testdb")
    db.run('''CREATE TABLE stocks_with_order
             (order_num integer primary key, date text, trans text, symbol text, qty real, price real)''')
    db.run('''CREATE TABLE stocks_with_unique_order 
    (order_num INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, date text, trans text, symbol text, qty real, price real)''')
    db.run("INSERT INTO stocks_with_order VALUES (0,'2006-01-05','BUY','RHAT',100,35.14)")
    db.run("INSERT INTO stocks_with_unique_order (date, trans, symbol, qty, price) VALUES ('2006-01-05','BUY','RHAT',100,35.14)")
    for i in db.get('SELECT * FROM stocks_with_unique_order ORDER BY price'):
        print(i)
    for i in db.get("select name,sql from sqlite_master where type = 'table'"):
        print(i)
    db.create_table('stocks_new_tb2', [
        col('order_num', int, 'AUTOINCREMENT'),
        col('date', str, None),
        col('trans', str, None),
        col('symbol', str, None),
        col('qty', float, None),
        col('price', str, None)], 'order_num')
    db.tables['stocks_new_tb2'].insert(
        date='2006-01-05',
        trans='BUY',
        symbol='RHAT',
        qty=100.0,
        price=35.14)
    db.tables['stocks_new_tb2'].update(symbol='NTAP', where=('order_num', 1))
    sel = db.tables['stocks_new_tb2'].select('*', where=('symbol','NTAP'))
    for r in sel:
        print(r)
    db.tables['stocks_new_tb2'].delete(where=('order_num', 1))
    sel = db.tables['stocks_new_tb2'].select('*')
    for r in sel:
        print(r)
