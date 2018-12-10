import os, psycopg2

# A production instance of Mesosphere's redshift cluster,
# see https://wiki.mesosphere.com/display/OPS/Segment+Redshift+Production+Instance
#
# TODO(alexr): Ideally we'd use a separate db.
HOST = "segment.cin53qlhwf0y.us-west-2.redshift.amazonaws.com"
PORT = 5439
CONNECT_TIMEOUT = 15 # in seconds
DB = "events"
SCHEMA = "dashboards"
TABLE = "dashboards.xfailflake_v1"

MAX_VARCHAR_LEN=65535


def connection():
    host = os.getenv("POSTGRES_HOST", HOST)
    port = os.getenv("POSTGRES_PORT", PORT)
    db = os.getenv("POSTGRES_DB", DB)
    user = os.environ["POSTGRES_USER"]
    password = os.environ["POSTGRES_PASSWORD"]

    print("DB: Creating postgres connection to\n"
          "    host: {}:{}\n"
          "    db: {}\n"
          "    user: {}\n".format(
              host, port, db, user))

    conn = psycopg2.connect(
        "host={} dbname={} user={} password={} port={} connect_timeout={}".format(
            host, db, user, password, port, CONNECT_TIMEOUT))
    conn.autocommit = True
    return conn


def execute(cursor, statement, values=()):
    print("DB: Executing SQL Statement: {} (values=({}))".format(
        statement, ", ".join(str(v) for v in values)))
    cursor.execute(statement, values)


def ensure_table(cursor):
    statement = """
    CREATE SCHEMA IF NOT EXISTS {schema};
    CREATE TABLE IF NOT EXISTS {table} (
        test        VARCHAR,
        ticket      VARCHAR,
        file        VARCHAR,
        timestamp   timestamp default current_timestamp,
        PRIMARY KEY (test, ticket, file, timestamp)
    );
    """.format(
        schema=SCHEMA,
        table=TABLE)

    cursor.execute(statement)


def insert(cursor, values_dict):
    columns = values_dict.keys()
    columns_str = _paren_csv(columns)

    values = [_cleaned_val(v) for v in values_dict.values()]
    values_template_str = _paren_csv(["%s"] * len(columns))

    statement = "INSERT INTO {} {} VALUES {}".format(
        TABLE, columns_str, values_template_str)

    execute(cursor, statement, values)


def _paren_csv(values):
    return "(" + ", ".join(values) + ")"


def _cleaned_val(val):
    if type(val) is str and len(val) > MAX_VARCHAR_LEN:
        print("DB: Truncating string '{}' value to be shorter than {} characters".format(
            val, MAX_VARCHAR_LEN))
        return val[:MAX_VARCHAR_LEN]
    else:
        return val


def blah():
    print("fuck")
