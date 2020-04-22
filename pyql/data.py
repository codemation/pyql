from contextlib import contextmanager
from collections import namedtuple
import json, re, logging

#Used for grouping columns with database class
col = namedtuple('col', ['name', 'type', 'mods'])

def get_db_manager(db_connect):
    @contextmanager
    def connect(*args, **kwds):
        # Code to acquire resource, e.g.:
        conn = db_connect(*args, **kwds)
        try:
            yield conn
        except Exception as e:
            try:
                logging.debug(f'failed to yeild connection with params {kwds} using {db_connect} result {conn} {repr(e)}')
            except Exception:
                pass
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
def flatten(s):
    return re.sub('\n',' ', s)

def no_blanks(s):
    return re.sub(' ', '', s)
    """
    washed = ''
    for l in s:
        if not l == ' ':
            washed = f"{washed}{l}"
    return washed
    """
def inner(s, l='(', r=')'):
    if not l in s or not r in s:
        return s
    sMap = [(ind, t) for ind, t in enumerate(s)]
    left, right = False, False
    inside = {}
    for ind, t in sMap:
        if left == False:
            if t == l:
                left = True
                inside['left'] =  ind
            continue
        if right == False:
            if t == r:
                inside['right'] = ind
    return s[inside['left']+1:inside['right']]


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
        self.debug = 'DEBUG' if 'debug' in kw else None
        self.log = kw['logger'] if 'logger' in kw else None
        self.setup_logger(self.log, level=self.debug)
        self.connetParams =  ['user', 'password', 'database', 'host', 'port']
        self.connectConfig = {}
        for k,v in kw.items():
            if k in self.connetParams:
                self.connectConfig[k] = v
        self.db_con = db_con
        self.type = 'sqlite' if not 'type' in kw else kw['type']
        if not 'database' in kw:
            raise InvalidInputError(kw, "missing field for 'database'")
        self.db_name = kw['database']
        self.connect = get_db_manager(self.db_con)
        self.cursor = get_cursor_manager(self.connect, self.connectConfig)
        if self.type == 'sqlite':
            self.foreign_keys = False
        self.preQuery = [] # SQL commands Ran before each for self.get self.run query 
        self.tables = {}
        self.load_tables()
    def __contains__(self, table):
        if self.type == 'sqlite':
            return table in [i[0] for i in self.get("select name, sql from sqlite_master where type = 'table'")]
        else:
            return table in [i[0] for i in self.get("show tables")]
    def setup_logger(self, logger=None, level=None):
        if logger == None:
            level = logging.DEBUG if level == 'DEBUG' else logging.ERROR
            logging.basicConfig(
                        level=level,
                        format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                        datefmt='%m-%d %H:%M'
            )
            self.log = logging.getLogger()
            self.log.setLevel(level)
        else:
            self.log = logger

    def run(self, query):
        return self.get(query)
    def get(self, query):
        query = f"{';'.join(self.preQuery + [query])}"
        self.log.debug(f'{self.db_name}.get query: {query}')
        with self.cursor() as c:
            try:
                rows = []
                result = []
                query = query.split(';') if ';' in query else [query]
                for q in query:
                    r = c.execute(q)
                    if r == None:
                        for v in c:
                            result.append(v)
                    else:
                        for row in r:
                            rows.append(row)
                return result if len(rows) == 0 else rows
            except Exception as e:
                self.log.exception(f"exception in .get {repr(e)}")
    def load_tables(self):
        if self.type == 'sqlite':
            def describe_table_to_col_sqlite(colConfig):
                config = []
                for i in ' '.join(colConfig.split(',')).split(' '):
                    if not i == '' and not i == '\n':
                        config.append(i.rstrip())
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
                config = flatten(config)
                colConfig = inner(config).split(', ')
                colsInTable = []
                foreignKeys = None
                for cfg in colConfig:
                    if not 'FOREIGN KEY' in cfg:
                        colsInTable.append(describe_table_to_col_sqlite(cfg))
                    else:
                        if foreignKeys == None:
                            foreignKeys = {}
                        lkey, ref = cfg.split('FOREIGN KEY')[1].split('REFERENCES')
                        lkey = inner(lkey)
                        parentTable, mods = ref.split(')')
                        parentTable, parentKey = parentTable.split('(')
                        foreignKeys[no_blanks(lkey)] = {
                                    'table': no_blanks(parentTable), 
                                    'ref': no_blanks(parentKey),
                                    'mods': mods.rstrip()
                                }
                # Create tables
                primaryKey = None
                for colItem in colsInTable: 
                    if 'PRIMARY KEY' in colItem.mods.upper():
                        primaryKey = colItem.name
                self.create_table(t[0], colsInTable, primaryKey, fKeys=foreignKeys)
                if not foreignKeys == None:
                    self.foreign_keys = True
                    fKeysPreQuery = 'PRAGMA foreign_keys=true'
                    if not fKeysPreQuery in self.preQuery:
                        self.preQuery.append(fKeysPreQuery)


        if self.type == 'mysql':
            def describe_table_to_col(column):
                typeTranslate = {'tinyint': bool, 'int': int, 'text': str, 'double': float, 'varchar': str}
                config = []
                for i in ' '.join(column.split(',')).split(' '):
                    if not i == '' and not i == '\n':
                        config.append(i.rstrip())
                column = config
                field = inner(column[0], '`','`')
                typ = None
                for k, v in typeTranslate.items():
                    if k in column[1]:
                        typ = v
                        break
                if typ == None:
                    raise InvalidColumnType(column[1], f"invalid type provided for column, supported types {list(typeTranslate.keys())}")
                """
                Null = 'NOT NULL ' if column[2] == 'NO' else ''
                Key = 'PRIMARY KEY ' if column[3] == 'PRI' else ''
                Default = '' # TOODOO - check if this needs implementing
                """
                extra = ' '.join(column[2:])
                return col(field, typ, extra)
            for table, in self.run('show tables'):
                colsInTable = []
                for _, schema in self.run(f'show create table {table}'):
                    schema = flatten(schema.split(f'CREATE TABLE `{table}`')[1])
                    colConfig = inner(schema).split(', ')
                    colsInTable = []
                    foreignKeys = None
                    for cfg in colConfig:
                        if not 'FOREIGN KEY' in cfg:
                            if not 'PRIMARY KEY' in cfg:
                                if not 'KEY' in cfg:
                                    colsInTable.append(describe_table_to_col(cfg))
                            else:
                                primaryKey = inner(inner(cfg.split('PRIMARY KEY')[1]), '`', '`')
                        else:
                            if foreignKeys == None:
                                foreignKeys = {}
                            lkey, ref = cfg.split('FOREIGN KEY')[1].split('REFERENCES')
                            lkey = inner(inner(lkey), '`', '`')
                            parentTable, mods = ref.split(')')
                            parentTable, parentKey = parentTable.split('(')
                            foreignKeys[no_blanks(lkey)] = {
                                        'table': no_blanks(inner(parentTable, '`', '`')), 
                                        'ref': no_blanks(inner(parentKey, '`', '`')),
                                        'mods': mods.rstrip()
                                    }
                table = inner(table, '`', '`')
                self.create_table(table, colsInTable, primaryKey, fKeys=foreignKeys)
    def create_table(self,name, columns, prim_key=None, **kw):
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
                'order_num', # Primary Key
                fkeys={'trans': {'table': 'transactions', 'ref': 'txId'}} 
            )
        """
        #Convert tuple columns -> named_tuples
        cols = []
        for c in columns:
            # Allows for len(2) tuple input ('name', int) --> converts to col('name', int, None)
            if not isinstance(c, col):
                cols.append(col(*c) if len(c) > 2 else col(*c, ''))
            else:
                cols.append(c)
        self.tables[name] = table(name, self, cols, prim_key, **kw)


class table:
    def __init__(self, name, database, columns, prim_key = None, **kw):
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
            if not c.type in self.types:
                raise InvalidColumnType(f"input type: {type(c.type)} of {c}", f"invalid type provided for column, supported types {self.types}")
            if c.name in self.columns:
                raise InvalidInputError(f"duplicate column name {c.name} provided", f"column names may only be specified once for table objects")
            self.columns[c.name] = c
        if prim_key is not None:
            self.prim_key = prim_key if prim_key in self.columns else None
        self.fKeys = kw['fKeys'] if 'fKeys' in kw else None
            
        self.create_schema()
    def get_schema(self):
        constraints = ''
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
                        if col.mods is not None and 'primary key' in col.mods.lower():
                            cols = f"{cols} {''.join(col.mods.upper().split('PRIMARY KEY'))}"
                        else:
                            cols = f"{cols} {col.mods.upper()}"
                    else:
                        if col.mods is not None:
                            cols = f'{cols} {col.mods}'
        if not self.fKeys == None:
            for lKey, fKey in self.fKeys.items():
                comma = ', ' if len(constraints) > 0 else ''
                constraints = f"{constraints}{comma}FOREIGN KEY({lKey}) REFERENCES {fKey['table']}({fKey['ref']}) {fKey['mods']}"
        comma = ', ' if len(constraints) > 0 else ''
        schema = f"CREATE TABLE {self.name} {cols}{comma}{constraints})"
        return schema
    def create_schema(self):
        if not self.name in self.database:
            self.database.run(self.get_schema())
    def _process_input(self, kw):
        tables = [self]
        if 'join' in kw:
            if isinstance(kw['join'], dict):
                for table in kw['join']:
                    if table in self.database.tables:
                        tables.append(self.database.tables[table])
            else:
                if kw['join'] in self.database.tables:
                    tables.append(self.database.tables[kw['join']])
        def verify_input(where):
            for table in tables:
                for cName, col in table.columns.items():
                    if cName in where:
                        if not col.type == bool:
                            #JSON handling
                            if col.type == str and type(where[cName]) == dict:
                                where[cName] = f"'{col.type(json.dumps(where[cName]))}'"
                                continue
                            where[cName] = col.type(where[cName]) if not where[cName] == None else 'NULL'
                        else:
                            try:
                                where[cName] = col.type(int(where[cName])) if table.database.type == 'mysql' else int(col.type(int(where[cName])))
                            except:
                                #Bool Input is string
                                if 'true' in where[cName].lower():
                                    where[cName] = True if table.database.type == 'mysql' else 1
                                elif 'false' in where[cName].lower():
                                    where[cName] = False if table.database.type == 'mysql' else 0
                                else:
                                    self.database.log.warning(f"Unsupported value {where[cName]} provide for column type {col.type}")
                                    del(where[cName])
                                    continue
            return where
        kw = verify_input(kw)
        if 'where' in kw:
            kw['where'] = verify_input(kw['where'])
        return kw

    def __where(self, kw):
        where_sel = ''
        index = 0
        kw = self._process_input(kw)
        if 'where' in kw:
            """
            for cName,v in kw['where'].items():
                if not cName in self.columns:
                    error = f'{cName} is not a valid column in table {self.name}'
                    raise InvalidInputError(error, f"columns available {[self.columns[c].name for c in self.columns]}")
            """
            andValue = 'WHERE '
            for cName,v in kw['where'].items():
                if '.' in cName:
                    table, column = cName.split('.')
                else:
                    table, column = self.name, cName
                if not column in self.database.tables[table].columns:
                    raise InvalidInputError(f"{column} is not a valid column in table {table}", "invalid column specified for 'where'")
                table = self.database.tables[table]
                eq = '=' if not v == 'NULL' else ' IS '
                #json check
                if v == 'NULL' or table.columns[column].type == str and '{"' and '}' in v:
                    where_sel = f"{where_sel}{andValue}{cName}{eq}{v}"
                else:
                    val = v if table.columns[column].type is not str else f"'{v}'"
                    where_sel = f"{where_sel}{andValue}{cName}{eq}{val}"
                andValue = ' AND '
        return where_sel
    def _join(self, kw):
        join = ''
        if not 'join' in kw:
            return join
        for joinTable, condition in kw['join'].items():
            if not joinTable in self.database.tables:
                error = f"{joinTable} does not exist in database"
                raise InvalidInputError(error, f"valid tables {list(t for t in self.database.tables)}")
            #if not len(condition) == 1:
            #    message = "join usage: join={'table1': {'table1.col': 'this.col'} } or  join={'table1': {'this.col': 'table1.col'} }"
            #    raise InvalidInputError(f"join expects dict of len 1, not {len(condition)} for {condition}", message)
            count = 0
            for col1, col2 in condition.items():
                for col in [col1, col2]:
                    if not '.' in col:
                        usage = "join usage: join={'table1': {'table1.col': 'this.col'} } or  join={'table1': {'this.col': 'table1.col'} }"
                        raise InvalidInputError(f"column {col} missing expected '.'", usage)
                    table, column = col.split('.')
                    if not table in self.database.tables:
                        error = f"table {table} does not exist in database"
                        raise InvalidInputError(error, f"valid tables {list(t for t in self.database.tables)}")
                    if not column in self.database.tables[table].columns:
                        error = f"column {column} is not a valid column in table {table}"
                        raise InvalidColumnType(error, f"valid column types {self.database.tables[table].columns}")
                joinAnd = ' AND ' if count > 0 else f'JOIN {joinTable} ON'
                join = f'{join}{joinAnd} {col1} = {col2} '
                count+=1
        return join

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


        if 'join' in kw and isinstance(kw['join'], str):
            if kw['join'] in [self.fKeys[k]['table'] for k in self.fKeys]:
                for lKey, fKey in self.fKeys.items():
                    if fKey['table'] == kw['join']:
                        kw['join'] = {
                            fKey['table']: {
                                f"{self.name}.{lKey}": f"{fKey['table']}.{fKey['ref']}"}
                                }
            else:
                error = f"join table {kw['join']} specified without specifying matching columns or tables do not share keys"
                raise InvalidInputError(error, f"valid fKeys {self.fkeys}")
        if '*' in selection:
            selection = '*'
            if 'join' in kw:
                if isinstance(kw['join'], dict):
                    colRefs = {f'{self.name}.{self.columns[c].name}': self.columns[c] for c in self.columns}
                    keys = [f'{self.name}.{self.columns[c].name}' for c in self.columns]
                    for table in list(kw['join'].keys()):
                        for joinC1, joinC2 in kw['join'][table].items():
                            if table in self.database.tables:
                                for col in self.database.tables[table].columns:
                                    column = self.database.tables[table].columns[col]
                                    if f'{table}.{column.name}' == joinC2:
                                        keys.append(joinC1)
                                        continue
                                    colRefs[f'{table}.{column.name}'] =  column
                                    keys.append(f'{table}.{column.name}')
            else:
                colRefs = self.columns
                keys = list(self.columns.keys())
        else:
            colRefs = {}
            keys = []
            for col in selection:
                if not col in self.columns:
                    if '.' in col:
                        table, column = col.split('.')
                        if table in self.database.tables and column in self.database.tables[table].columns:
                            colRefs[col] = self.database.tables[table].columns[column]
                            keys.append(col)
                            continue
                    raise InvalidColumnType(f"column {col} is not a valid column", f"valid column types {self.columns}")
                colRefs[col] = self.columns[col]
                keys.append(col)
            selection = ','.join(selection)
        join = ''
        if 'join' in kw:
            join = self._join(kw)        
        where_sel = self.__where(kw)
        orderby = ''
        if 'orderby' in kw:
            if not kw['orderby'] in self.columns:
                raise InvalidInputError(f"orderby input {kw['orderby']} is not a valid column name", f"valid columns {self.columns}")
            orderby = ' ORDER BY '+ kw['orderby']
        query = 'SELECT {select_item} FROM {name} {join}{where}{order}'.format(
            select_item = selection,
            name = self.name,
            join=join,
            where = where_sel,
            order = orderby
        )
        rows = self.database.get(query)

        #dictonarify each row result and return
        """
        if not selection == '*':
            keys = selection.split(',') if ',' in selection else selection.split(' ')
        else:
            keys = list(self.columns.keys())
        """
        toReturn = []
        if not rows == None:
            for row in rows:
                r_dict = {}
                for i,v in enumerate(row):
                    #if not v == None and self.columns[keys[i]].type == str and '{"' and '}' in v:
                    if not v == None and colRefs[keys[i]].type == str and '{"' and '}' in v:
                            r_dict[keys[i]] = json.loads(v)
                    else:
                        r_dict[keys[i]] = v if not colRefs[keys[i]].type == bool else bool(v)
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
                    if 'NOT NULL' in col.mods and not 'INCREMENT' in col.mods:
                        raise InvalidInputError(f'{cName} is a required field for INSERT in table {self.name}', "correct and try again")
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
        self.database.log.debug(query)
        self.database.run(query)
    def update(self,**kw):
        """
        Usage:
            db.tables['stocks'].update(symbol='NTAP',trans='SELL', where={'order_num': 1})
        """
        
        kw = self._process_input(kw)

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
        self.database.log.debug(query)
        self.database.run(query)
    def delete(self, all_rows=False, **kw):
        """
        Usage:
            db.tables['stocks'].delete(where={'order_num': 1})
            db.tables['stocks'].delete(all_rows=True)
        """
        try:
            where_sel = self.__where(kw)
        except Exception as e:
            return repr(e)
        if len(where_sel) < 1 and not all_rows:
            error = "where statment is required with DELETE, otherwise specify .delete(all_rows=True)"
            raise InvalidInputError(error, "correct & try again later")
        query = "DELETE FROM {name} {where}".format(
            name=self.name,
            where=where_sel
        )
        self.database.run(query)
    def __get_val_column(self):
        if len(self.columns.keys()) == 2:
            for key in list(self.columns.keys()):
                if not key == self.prim_key:
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
class Error(Exception):
    pass
class InvalidInputError(Error):
    def __init__(self, invalidInput, message):
        self.invalidInput = invalidInput
        self.message = message
class InvalidColumnType(Error):
    def __init__(self, invalidType, message):
        self.invalidType = invalidType
        self.message = message
#   TOODOO:
# - Add support for creating column indexes per tables
# - Determine if views are needed and add support
# - Support for transactions?