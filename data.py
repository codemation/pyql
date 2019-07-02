from contextlib import contextmanager

def get_db_manager(db_connect):
    @contextmanager
    def connect(*args, **kwds):
        # Code to acquire resource, e.g.:
        conn = db_connect(*args, **kwds)
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
    def execute(db_name):
        with connect_db(db_name) as conn:
            c = conn.cursor()
            try:
                yield c
            finally:
                conn.commit()
    return execute

class database:
    def __init__(self, db, db_name):
        self.db_con = db
        self.db_name = db_name
        self.connect = get_db_manager(self.db_con)
        self.cursor = get_cursor_manager(self.connect)
    def run(self, query):
        with self.cursor(self.db_name) as c:
            try:
                c.execute(query)
            except Exception as e:
                print(repr(e))
    def get(self, query):
        with self.cursor(self.db_name) as c:
            try:
                rows = []
                for row in c.execute(query):
                    rows.append(row)
                return rows
            except Exception as e:
                print(repr(e))


def run_test():
    import sqlite3
    db = database(sqlite3.connect, 'testdb')
    """
    db.run('''CREATE TABLE stocks
             (date text, trans text, symbol text, qty real, price real)''')
    db.run("INSERT INTO stocks VALUES ('2006-01-05','BUY','RHAT',100,35.14)")
    db = database(sqlite3.connect, 'testdb')
    """
    for i in db.get('SELECT * FROM stocks ORDER BY price'):
        print(i)
run_test()