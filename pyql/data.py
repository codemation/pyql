from contextlib import contextmanager
from collections import namedtuple
import json, re, logging

#Used for grouping columns with database class
TableColumn = namedtuple('col', ['name', 'type', 'mods'])

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
def inner(s, l='(', r=')'):
    if not l in s or not r in s:
        return s
    string_map = [(ind, t) for ind, t in enumerate(s)]
    left, right = False, False
    inside = {}
    for ind, t in string_map:
        if left == False:
            if t == l:
                left = True
                inside['left'] =  ind
            continue
        if right == False:
            if t == r:
                inside['right'] = ind
    return s[inside['left']+1:inside['right']]


class Database:
    """
        Intialize with db connector & name of database. If database exists, it will be used else a new db will be created \n

        sqlite example:
            import sqlite3
            db = Database(sqlite3.connect, "testdb")
        mysql example:
            import mysql.connector
            db = Database(mysql.connector.connect, **config)
        
    """
    def __init__(self, db_con, **kw):
        self.debug = 'DEBUG' if 'debug' in kw else None
        self.log = kw['logger'] if 'logger' in kw else None
        self.setup_logger(self.log, level=self.debug)
        self.connect_params =  ['user', 'password', 'database', 'host', 'port']
        self.connect_config = {}
        for k,v in kw.items():
            if k in self.connect_params:
                self.connect_config[k] = v
        self.db_con = db_con
        self.type = 'sqlite' if not 'type' in kw else kw['type']
        if not 'database' in kw:
            raise InvalidInputError(kw, "missing field for 'database'")
        self.db_name = kw['database']
        self.connect = get_db_manager(self.db_con)
        self.cursor = get_cursor_manager(self.connect, self.connect_config)
        if self.type == 'sqlite':
            self.foreign_keys = False
        self.pre_query = [] # SQL commands Ran before each for self.get self.run query 
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
        query = f"{';'.join(self.pre_query + [query])}"
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
            def describe_table_to_col_sqlite(col_config):
                config = []
                for i in ' '.join(col_config.split(',')).split(' '):
                    if not i == '' and not i == '\n':
                        config.append(i.rstrip())
                TYPE_TRANSLATE = {
                    'varchar': str,
                    'integer': int,
                    'text': str,
                    'real': float,
                    'boolean': bool,
                    'blob': bytes 
                }
                field, typ, extra = config[0], config[1], ' '.join(config[2:])
                return TableColumn(
                    field, 
                    TYPE_TRANSLATE[typ.lower() if not 'VARCHAR' in typ else 'varchar'], 
                    extra)
                
            for t in self.get("select name, sql from sqlite_master where type = 'table'"):
                if 'sqlite' in t[1]:
                    continue
                name = t[0]
                schema = t[1]
                config = schema.split(f'CREATE TABLE {name}')[1]
                config = flatten(config)
                col_config = inner(config).split(', ')
                cols_in_table = []
                foreign_keys = None
                for cfg in col_config:
                    if not 'FOREIGN KEY' in cfg:
                        cols_in_table.append(describe_table_to_col_sqlite(cfg))
                    else:
                        if foreign_keys == None:
                            foreign_keys = {}
                        local_key, ref = cfg.split('FOREIGN KEY')[1].split('REFERENCES')
                        local_key = inner(local_key)
                        parent_table, mods = ref.split(')')
                        parent_table, parent_key = parent_table.split('(')
                        foreign_keys[no_blanks(local_key)] = {
                                    'table': no_blanks(parent_table), 
                                    'ref': no_blanks(parent_key),
                                    'mods': mods.rstrip()
                                }
                # Create tables
                primary_key = None
                for col_item in cols_in_table: 
                    if 'PRIMARY KEY' in col_item.mods.upper():
                        primary_key = col_item.name
                self.create_table(t[0], cols_in_table, primary_key, foreign_keys=foreign_keys)
                if not foreign_keys == None:
                    self.foreign_keys = True
                    foreign_keys_pre_query = 'PRAGMA foreign_keys=true'
                    if not foreign_keys_pre_query in self.pre_query:
                        self.pre_query.append(foreign_keys_pre_query)


        if self.type == 'mysql':
            def describe_table_to_col(column):
                TYPE_TRANSLATE = {'tinyint': bool, 'int': int, 'text': str, 'double': float, 'varchar': str}
                config = []
                for i in ' '.join(column.split(',')).split(' '):
                    if not i == '' and not i == '\n':
                        config.append(i.rstrip())
                column = config
                field = inner(column[0], '`','`')
                typ = None
                for k, v in TYPE_TRANSLATE.items():
                    if k in column[1]:
                        typ = v
                        break
                if typ == None:
                    raise InvalidColumnType(column[1], f"invalid type provided for column, supported types {list(TYPE_TRANSLATE.keys())}")
                """
                Null = 'NOT NULL ' if column[2] == 'NO' else ''
                Key = 'PRIMARY KEY ' if column[3] == 'PRI' else ''
                Default = '' # TOODOO - check if this needs implementing
                """
                extra = ' '.join(column[2:])
                return TableColumn(field, typ, extra)
            for table, in self.run('show tables'):
                cols_in_table = []
                for _, schema in self.run(f'show create table {table}'):
                    schema = flatten(schema.split(f'CREATE TABLE `{table}`')[1])
                    col_config = inner(schema).split(', ')
                    cols_in_table = []
                    foreign_keys = None
                    for cfg in col_config:
                        if not 'FOREIGN KEY' in cfg:
                            if not 'PRIMARY KEY' in cfg:
                                if not 'KEY' in cfg:
                                    cols_in_table.append(describe_table_to_col(cfg))
                            else:
                                primary_key = inner(inner(cfg.split('PRIMARY KEY')[1]), '`', '`')
                        else:
                            if foreign_keys == None:
                                foreign_keys = {}
                            local_key, ref = cfg.split('FOREIGN KEY')[1].split('REFERENCES')
                            local_key = inner(inner(local_key), '`', '`')
                            parent_table, mods = ref.split(')')
                            parent_table, parent_key = parent_table.split('(')
                            foreign_keys[no_blanks(local_key)] = {
                                        'table': no_blanks(inner(parent_table, '`', '`')), 
                                        'ref': no_blanks(inner(parent_key, '`', '`')),
                                        'mods': mods.rstrip()
                                    }
                table = inner(table, '`', '`')
                self.create_table(table, cols_in_table, primary_key, foreign_keys=foreign_keys)
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
                foreign_keys={'trans': {'table': 'transactions', 'ref': 'txId'}} 
            )
        """
        #Convert tuple columns -> named_tuples
        cols = []
        for c in columns:
            # Allows for len(2) tuple input ('name', int) --> converts to TableColumn('name', int, None)
            if not isinstance(c, TableColumn):
                cols.append(TableColumn(*c) if len(c) > 2 else TableColumn(*c, ''))
            else:
                cols.append(c)
        self.tables[name] = Table(name, self, cols, prim_key, **kw)


class Table:
    def __init__(self, name, database, columns, prim_key = None, **kw):
        self.name = name
        self.database = database
        self.types = {int,str,float,bool,bytes}
        self.TRANSLATION = {
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
        self.foreign_keys = kw['foreign_keys'] if 'foreign_keys' in kw else None
            
        self.create_schema()
    def get_schema(self):
        constraints = ''
        cols = '('
        for col_name,col in self.columns.items():
            for k,v in self.TRANSLATION.items():
                if col.type == v:
                    if len(cols) > 1:
                        cols = f'{cols}, '
                    if col_name == self.prim_key and (k=='text' or k=='blob'):
                        cols = f'{cols}{col.name} VARCHAR(36)'
                    else:
                        cols = f'{cols}{col.name} {k.upper()}'
                    if col_name == self.prim_key:
                        cols = f'{cols} PRIMARY KEY'
                        if col.mods is not None and 'primary key' in col.mods.lower():
                            cols = f"{cols} {''.join(col.mods.upper().split('PRIMARY KEY'))}"
                        else:
                            cols = f"{cols} {col.mods.upper()}"
                    else:
                        if col.mods is not None:
                            cols = f'{cols} {col.mods}'
        if not self.foreign_keys == None:
            for local_key, foreign_key in self.foreign_keys.items():
                comma = ', ' if len(constraints) > 0 else ''
                constraints = f"{constraints}{comma}FOREIGN KEY({local_key}) REFERENCES {foreign_key['table']}({foreign_key['ref']}) {foreign_key['mods']}"
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
                for col_name, col in table.columns.items():
                    if col_name in where:
                        if not col.type == bool:
                            #JSON handling
                            if col.type == str and type(where[col_name]) == dict:
                                where[col_name] = f"'{col.type(json.dumps(where[col_name]))}'"
                                continue
                            if type(where) == dict:
                                where[col_name] = col.type(where[col_name]) if not where[col_name] == None else 'NULL'
                        else:
                            try:
                                where[col_name] = col.type(int(where[col_name])) if table.database.type == 'mysql' else int(col.type(int(where[col_name])))
                            except:
                                #Bool Input is string
                                if 'true' in where[col_name].lower():
                                    where[col_name] = True if table.database.type == 'mysql' else 1
                                elif 'false' in where[col_name].lower():
                                    where[col_name] = False if table.database.type == 'mysql' else 0
                                else:
                                    self.database.log.warning(f"Unsupported value {where[col_name]} provide for column type {col.type}")
                                    del(where[col_name])
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
            and_value = 'WHERE '

            def get_valid_table_column(col_name, **kw):
                dot_table = False
                if isinstance(col_name, str) and '.' in col_name:
                    dot_table = True
                    table, column = col_name.split('.')
                else:
                    table, column = self.name, col_name
                if not column in self.database.tables[table].columns:
                    if 'no_raise' in kw and not dot_table:
                        pass
                    else:
                        raise InvalidInputError(
                            f"{column} is not a valid column in table {table}", 
                            "invalid column specified for 'where'")
                return table, column

            supported_operators = {'=', '==', '<>', '!=', '>', '>=', '<', '<=', 'like', 'in', 'not in', 'not like'}
            if isinstance(kw['where'], list):
                for condition in kw['where']:
                    if not type(condition) in [dict, list]:
                        raise InvalidInputError(
                            f"{condition} is not a valid type within where=[]", 
                            "invalid subcondition type within where=[], expected type(list, dict)"
                            )
                    if isinstance(condition, list):
                        if not len(condition) == 3:
                            cond_len = len(condition)
                            raise InvalidInputError(
                                f"{condition} has {cond_len} items, expected 3", 
                                f"{condition} has {cond_len} items, expected 3"
                        )
                        condition1 = f"{condition[0]}"
                        operator = condition[1]
                        condition2 = condition[2]

                        table, column = None, None
                        # expecting comparison operators
                        if not operator in supported_operators:
                            raise InvalidInputError(
                                f"Invalid operator {operator} within {condition}", f"supported operators [{supported_operators}]"
                            )
                        for i, value in enumerate([condition1, condition2]):
                            if i == 0:
                                table, column = get_valid_table_column(value)
                                pass
                            if i == 1 and 'in' in operator:
                                # in operators should be proceeded by a list of values
                                if not isinstance(condition2, list):
                                    raise InvalidInputError(
                                        f"Invalid use of operator '{operator}' within {condition}", 
                                        f"'in' should be proceeded by ['list', 'of', 'values'] not {type(condition2)} - {condition2}"
                                    )
                                if self.database.tables[table].columns[column].type == str:
                                    condition2 = [f"'{cond}'" for cond in condition2]
                                else:
                                    condition2 = [str(cond) for cond in condition2]
                                condition2 = ', '.join(condition2)
                                condition2 = f"({condition2})"
                                break
                            if i == 1:
                                get_valid_table_column(value, no_raise=True)
                                """still raises if dot_table used & not in table """
                                pass

                        if 'like' in operator:
                            condition2 = f"{condition2}"
                            if not '*' in condition2:
                                condition2 = f"'%{condition2}%'"
                            else:
                                condition2 = '%'.join(condition2.split('*'))
                                condition2 = f"'{condition2}'"

                        
                        where_sel = f"{where_sel}{and_value}{condition1} {operator} {condition2}"
                    if isinstance(condition, dict):
                        for col_name, v in condition.items():
                            table, column = get_valid_table_column(col_name)
                            table = self.database.tables[table]
                            eq = '=' if not v == 'NULL' else ' IS '
                            #json check
                            if v == 'NULL' or table.columns[column].type == str and '{"' and '}' in v:
                                where_sel = f"{where_sel}{and_value}{col_name}{eq}{v}"
                            else:
                                val = v if table.columns[column].type is not str else f"'{v}'"
                                where_sel = f"{where_sel}{and_value}{col_name}{eq}{val}"

                    and_value = ' AND '
                        
            if isinstance(kw['where'], dict):
                for col_name, v in kw['where'].items():
                    table, column = get_valid_table_column(col_name)
                    table = self.database.tables[table]
                    eq = '=' if not v == 'NULL' else ' IS '
                    #json check
                    if v == 'NULL' or table.columns[column].type == str and '{"' and '}' in v:
                        where_sel = f"{where_sel}{and_value}{col_name}{eq}{v}"
                    else:
                        val = v if table.columns[column].type is not str else f"'{v}'"
                        where_sel = f"{where_sel}{and_value}{col_name}{eq}{val}"
                    and_value = ' AND '
        return where_sel
    def _join(self, kw):
        join = ''
        if not 'join' in kw:
            return join
        for join_table, condition in kw['join'].items():
            if not join_table in self.database.tables:
                error = f"{join_table} does not exist in database"
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
                join_and = ' AND ' if count > 0 else f'JOIN {join_table} ON'
                join = f'{join}{join_and} {col1} = {col2} '
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
            if kw['join'] in [self.foreign_keys[k]['table'] for k in self.foreign_keys]:
                for local_key, foreign_key in self.foreign_keys.items():
                    if foreign_key['table'] == kw['join']:
                        kw['join'] = {
                            foreign_key['table']: {
                                f"{self.name}.{local_key}": f"{foreign_key['table']}.{foreign_key['ref']}"}
                                }
            else:
                error = f"join table {kw['join']} specified without specifying matching columns or tables do not share keys"
                raise InvalidInputError(error, f"valid foreign_keys {self.foreign_keys}")
        if '*' in selection:
            selection = '*'
            if 'join' in kw:
                if isinstance(kw['join'], dict):
                    col_refs = {}
                    links = {}
                    keys = []
                    for table in [self.name] + list(kw['join'].keys()):
                        if table in self.database.tables:
                            for col in self.database.tables[table].columns:
                                column = self.database.tables[table].columns[col]
                                if table in kw['join']:
                                    cont = False
                                    for col1, col2 in kw['join'][table].items():
                                        if f'{table}.{col}' == f'{col2}':
                                            cont = True
                                            if col1 in links:
                                                keys.append(links[col1])
                                                links[col2] = links[col1]
                                                break
                                            links[col2] = col1
                                            keys.append(col1)
                                            break
                                    if cont:
                                        continue
                                col_refs[f'{table}.{column.name}'] =  column
                                keys.append(f'{table}.{column.name}')
            else:
                col_refs = self.columns
                keys = list(self.columns.keys())
        else:
            col_refs = {}
            keys = []
            for col in selection:
                if not col in self.columns:
                    if '.' in col:
                        table, column = col.split('.')
                        if table in self.database.tables and column in self.database.tables[table].columns:
                            col_refs[col] = self.database.tables[table].columns[column]
                            keys.append(col)
                            continue
                    raise InvalidColumnType(f"column {col} is not a valid column", f"valid column types {self.columns}")
                col_refs[col] = self.columns[col]
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
        to_return = []
        if not rows == None:
            for row in rows:
                r_dict = {}
                for i,v in enumerate(row):
                    try:
                        if not v == None and col_refs[keys[i]].type == str and '{"' and '}' in v:
                                r_dict[keys[i]] = json.loads(v)
                        else:
                            r_dict[keys[i]] = v if not col_refs[keys[i]].type == bool else bool(v)
                    except Exception as e:
                        self.database.log.exception(f"error processing results on row {row} index {i} value {v} with {keys}")
                        assert False
                to_return.append(r_dict)
        return to_return
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

        for col_name, col in self.columns.items():
            if not col_name in kw:
                if not col.mods == None:
                    if 'NOT NULL' in col.mods and not 'INCREMENT' in col.mods:
                        raise InvalidInputError(f'{col_name} is a required field for INSERT in table {self.name}', "correct and try again")
                continue
            if len(cols) > 2:
                cols = f'{cols}, '
                vals = f'{vals}, '
            cols = f'{cols}{col_name}'
            #json handling
            if kw[col_name]== 'NULL' or kw[col_name] == None or col.type == str and '{"' and '}' in kw[col_name]:
                new_val = kw[col_name]
            else:
                new_val = kw[col_name] if col.type is not str else f'"{kw[col_name]}"'
            vals = f'{vals}{new_val}'

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
        for col_name, col_val in kw.items():
            if col_name.lower() == 'where':
                continue
            if len(cols_to_set) > 1:
                cols_to_set = f'{cols_to_set}, '
            #JSON detection
            if col_val == 'NULL' or self.columns[col_name].type == str and '{"' and '}' in col_val:
                column_value = col_val
            else:
                column_value = col_val if self.columns[col_name].type is not str else f"'{col_val}'"
            cols_to_set = f'{cols_to_set}{col_name} = {column_value}'

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

    def __getitem__(self, key_val):
        val = self.select('*', where={self.prim_key: key_val})
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
    def __init__(self, invalid_input, message):
        self.invalid_input = invalid_input
        self.message = message
class InvalidColumnType(Error):
    def __init__(self, invalid_type, message):
        self.invalid_type = invalid_type
        self.message = message
#   TOODOO:
# - Add support for creating column indexes per tables
# - Add OR statement querry support
# - Support for transactions?