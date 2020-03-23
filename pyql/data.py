from contextlib import contextmanager
from collections import namedtuple
import json

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
        if self.type == 'sqlite':
            def describe_table_to_col_sqlite(colConfig):
                config = colConfig.split(' ')
                typeTranslate = {
                    'varchar': str,
                    'integer': int,
                    'text': str,
                    'real': float,
                    'boolean': bool,
                    'blob': bytes 
                }
                field, typ, extra = config[0], config[1], ' '.join(config[2:])
                return col(
                    field, 
                    typeTranslate[typ.lower() if not 'VARCHAR' in typ else 'varchar'], 
                    extra)
                
            for t in self.get("select name, sql from sqlite_master where type = 'table'"):
                if 'sqlite' in t[1]:
                    continue
                name = t[0]
                schema = t[1]
                config = schema.split(f'CREATE TABLE {name}')[1]
                colConfig = config[2:-2].split(', ')
                colsInTable = []
                for cfg in colConfig:
                    colsInTable.append(describe_table_to_col_sqlite(cfg))
                # Create tables
                primaryKey = None
                for colItem in colsInTable: 
                    if 'PRIMARY KEY' in colItem.mods:
                        primaryKey = colItem.name
                print(colsInTable)
                self.create_table(t[0], colsInTable, primaryKey)

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

                primaryKey = None
                for colItem in colsInTable: 
                    if 'PRIMARY KEY' in colItem.mods:
                        primaryKey = colItem.name
                self.create_table(table[0], colsInTable, primaryKey)
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
                        cols = f'{cols}, '
                    if cName == self.prim_key and (k=='text' or k=='blob'):
                        cols = f'{cols}{col.name} VARCHAR(36)'
                    else:
                        cols = f'{cols}{col.name} {k.upper()}'
                    if cName == self.prim_key:
                        cols = f'{cols} PRIMARY KEY'                    
                    if col.mods is not None:
                        cols = f'{cols} {col.mods}'
        cols = cols + ' )'
        schema = f"""CREATE TABLE {self.name} {cols}"""
        return schema
    def create_schema(self):
        self.database.run(self.get_schema())
    def _process_input(self, kw):
        for cName, col in self.columns.items():
            if cName in kw:
                if not col.type == bool:
                    #JSON handling
                    if col.type == str and type(kw[cName]) == dict:
                        kw[cName] = f"'{col.type(json.dumps(kw[cName]))}'"
                        continue
                    kw[cName] = col.type(kw[cName]) if not kw[cName] == None else 'NULL'
                else:
                    try:
                        kw[cName] = col.type(int(kw[cName])) if self.database.type == 'mysql' else int(col.type(int(kw[cName])))
                    except:
                        #Bool Input is string
                        if 'true' in kw[cName].lower():
                            kw[cName] = True if self.database.type == 'mysql' else 1
                        elif 'false' in kw[cName].lower():
                            kw[cName] = False if self.database.type == 'mysql' else 0
                        else:
                            print(f"Unsupported value {kw[cName]} provide for column type {col.type}")
                            del(kw[cName])
                            continue
        return kw

    def __where(self, kw):
        where_sel = ''
        index = 0
        if 'where' in kw:
            kw['where'] = self._process_input(kw['where'])
            for cName,v in kw['where'].items():
                assert cName in self.columns, f'{cName} is not a valid column in table {self.name}'
            andValue = 'WHERE '
            for cName,v in kw['where'].items():
                eq = '=' if not v == 'NULL' else ' IS '
                #json check
                if v == 'NULL' or self.columns[cName].type == str and '{"' and '}' in v:
                    where_sel = f"{where_sel}{andValue}{cName}{eq}{v}"
                else:
                    val = v if self.columns[cName].type is not str else "'"+v+"'"
                    where_sel = f"{where_sel}{andValue}{cName}{eq}{val}"
                andValue = ' AND '
        return where_sel

    def select(self, *selection, **kw):
        """
        Usage: returns list of dictionaries for each selection in each row. 
            tb = db.tables['stocks_new_tb2']

            sel = tb.select('order_num',
                            'symbol', 
                            where={'trans': 'BUY', 'qty': 100})
            sel = tb.select('*')
            # Iterate through table
            sel = [row for row in tb]
            # Using Primary key only
            sel = tb[0] # select * from <table> where <table_prim_key> = <val>
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
        if not selection == '*':
            keys = selection.split(',') if ',' in selection else selection.split(' ')
        else:
            keys = list(self.columns.keys())
        toReturn = []
        if not rows == None:
            for row in rows:
                r_dict = {}
                for i,v in enumerate(row):
                    if not v == None and self.columns[keys[i]].type == str and '{"' and '}' in v:
                            r_dict[keys[i]] = json.loads(v)
                    else:
                        r_dict[keys[i]] = v if not self.columns[keys[i]].type == bool else bool(v)
                toReturn.append(r_dict)
        return toReturn
    def insert(self, **kw):
        """
        Usage:
            db.tables['stocks_new_tb2'].insert(
                date='2006-01-05',
                trans={
                    'type': 'BUY', 
                    'conditions': {'limit': '36.00', 'time': 'EndOfTradingDay'}, #JSON
                'tradeTimes':['16:30:00.00','16:30:01.00']}, # JSON
                symbol='RHAT', 
                qty=100.0,
                price=35.14)
        """
        cols = '('
        vals = '('
        #checking input kw's for correct value types

        kw = self._process_input(kw)

        for cName, col in self.columns.items():
            if not cName in kw:
                if not col.mods == None:
                    if 'NOT NULL' in col.mods:
                        print(f'{cName} is a required field for INSERT in table {self.name}')
                        return
                continue
            if len(cols) > 2:
                cols = f'{cols}, '
                vals = f'{vals}, '
            cols = f'{cols}{cName}'
            #json handling
            if kw[cName]== 'NULL' or kw[cName] == None or col.type == str and '{"' and '}' in kw[cName]:
                newVal = kw[cName]
            else:
                newVal = kw[cName] if col.type is not str else f'"{kw[cName]}"'
            vals = f'{vals}{newVal}'

        cols = cols + ')'
        vals = vals + ')'

        query = f'INSERT INTO {self.name} {cols} VALUES {vals}'
        print(query)
        self.database.run(query)
    def update(self,**kw):
        """
        Usage:
            db.tables['stocks'].update(symbol='NTAP',trans='SELL', where={'order_num': 1})
        """
        try:
            kw = self._process_input(kw)
        except Exception as e:
            print(e)

  
        cols_to_set = ''
        for cName,cVal in kw.items():
            if cName.lower() == 'where':
                continue
            if len(cols_to_set) > 1:
                cols_to_set = f'{cols_to_set}, '
            #JSON detection
            if cVal == 'NULL' or self.columns[cName].type == str and '{"' and '}' in cVal:
                columnValue = cVal
            else:
                columnValue = cVal if self.columns[cName].type is not str else f"'{cVal}'"
            cols_to_set = f'{cols_to_set}{cName} = {columnValue}'

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
            db.tables['stocks'].delete(where={'order_num': 1})
            db.tables['stocks'].delete(all_rows=True)
        """
        where_sel = self.__where(kw)
        if len(where_sel) < 1:
            assert all_rows, "where statment is required with DELETE, otherwise specify .delete(all_rows=True)"
        query = "DELETE FROM {name} {where}".format(
            name=self.name,
            where=where_sel
        )
        self.database.run(query)
    def __get_val_column(self):
        if len(self.columns.keys()) == 2:
            for key in list(self.columns.keys()):
                if not key == self.prim_key:
                    print(f"__get_val_column key {key}")
                    return key

    def __getitem__(self, keyVal):
        val = self.select('*', where={self.prim_key: keyVal})
        if not val == None and len(val) > 0:
            if len(self.columns.keys()) == 2:
                return val[0][self.__get_val_column()] # returns 
            return val[0]
        return None
    def __setitem__(self, key, values):
        if not self[key] == None:
            if not isinstance(values, dict) and len(self.columns.keys()) == 2:
                return self.update(**{self.__get_val_column(): values}, where={self.prim_key: key})
            return self.update(**values, where={self.prim_key: key})
        if not isinstance(values, dict) and len(self.columns.keys()) == 2:
            return self.insert(**{self.prim_key: key, self.__get_val_column(): values})
        if len(self.columns.keys()) == 2 and isinstance(values, dict) and not self.prim_key in values:
            return self.insert(**{self.prim_key: key, self.__get_val_column(): values})
        if len(values) == len(self.columns):
            return self.insert(**values)

    def __contains__(self, key):
        if self[key] == None:
            return False
        return True
    def __iter__(self):
        def gen():
            for row in self.select('*'):
                yield row
        return gen()
#   TOODOO:
# - Add support for creating column indexes per tables
# - Add suppport for foreign keys & joins with queries
# - Determine if views are needed and add support
# - Support for transactions?