
import os, sys

# Dances around python versions and modules conflict
try:
    from BaseHTTPServer import HTTPServer
    from BaseHTTPServer import BaseHTTPRequestHandler
except ImportError:
    from http.server import HTTPServer
    from http.server import BaseHTTPRequestHandler

# Internal helpers. Transitive dependencies:
#  * psycopg2-binary
import json_formats as jf
import postgres_redshift as db
import repo_utils as ru


# For each GET request this handler replies with JSON in redash format.
#
# TODO(alexr): Serve both formats, redash and the default one.
class RedashHandler(BaseHTTPRequestHandler):
    repo = None
    branch = None

    def _set_headers(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

    def do_GET(self):
        self._set_headers()
        if self.path == '/' and repo is not None:
            xfailflakes = ru.get_xfailflakes_from_repo(repo, branch)
            print("Serving xfailflakes redashified:\n'{}'".format(jf.convert_to_redash(xfailflakes)))
            self.wfile.write(jf.convert_to_redash(xfailflakes).encode('utf-8'))


class Server(HTTPServer):
    def serve_forever(self, repo, branch):
        self.RequestHandlerClass.repo = repo
        self.RequestHandlerClass.branch = branch
        HTTPServer.serve_forever(self)


def dump_to_stdout(repo, branch, args):
    xfailflakes = ru.get_xfailflakes_from_repo(repo, branch)
    print("xfailflakes JSONified:\n'{}'".format(jf.convert_to_default(xfailflakes, repo)))


# Starts a simple server with the `RedashHandler`.
def serve_redash(repo, branch, args):
    port = int(args[0])

    server_address = ('', port)
    httpd = Server(server_address, RedashHandler)

    # TODO(alexr): Spawn the server in a separate thread.
    print("Starting httpd on port {}".format(port))
    httpd.serve_forever(repo, branch)


def push_to_redshift(repo, branch, args):
    xfailflakes = ru.get_xfailflakes_from_repo(repo, branch)

    conn = db.connection()
    cursor = conn.cursor()

    db.ensure_schema(cursor)
    db.ensure_history(cursor)

    for xfailflake in xfailflakes:
        print("Inserting xfailflake: {}".format(xfailflake))
        db.insert(cursor, db.TABLE_HISTORY, xfailflake)


def print_help(repo, args):
    print(
        "{0}Scans a given repository branch for 'xfailflake' marked tests and{0}"
        "presents the resulted output in various ways. Relies on a specific{0}"
        "pattern to extract the test name and the associated JIRA ticket. Note{0}"
        "that the repository must be cloneable; an access token can be provided{0}"
        "via the `GITHUB_TOKEN` env var.{0}{0}"
        "Usage: python xfailflake-grabber.py <action> <repository> <branch> [args]{0}{0}"
        "Available actions:".format(os.linesep)
    )
    for a in actions:
        print("  {0} - {1}".format(a, actions[a]["msg"]))


# List of supported actions with callback and help message.
actions = {
    "dump": {
        "msg": "Dumps a JSON blob containing 'xfailflake' marked tests to stdout",
        "cmd": dump_to_stdout
    },
    "serve": {
        "msg": "Starts a webserver which responds to each 'GET /' request "
               "with a JSON blob in redash format containing 'xfailflake' "
               "marked tests; extra arguments: <port>",
        "cmd": serve_redash
    },
    "redshift": {
        "msg": "Pushes 'xfailflake' marked tests together with a timestamp to "
               "a redshift database; extra arguments: ; <user> and <password> "
               "must be supplied via env vars 'POSTGRES_USER' and "
               "'POSTGRES_PASSWORD'",
        "cmd": push_to_redshift
    },
    "help": {
        "msg": "Prints help message",
        "cmd": print_help
    }
}


# Entrypoint.
if __name__ == "__main__":
    if (len(sys.argv) < 2):
        print("Error: Parameter <action> is required")
        print_help('', [])
        sys.exit(1)

    action = sys.argv[1]

    if action == "help":
        print_help('', [])
        sys.exit(0)

    if len(sys.argv) < 4:
        print("Error: Each <action> requires target <repository> and <branch>")
        print_help('', [])
        sys.exit(1)

    repo = sys.argv[2]
    branch = sys.argv[3]
    args = sys.argv[4:]

if action in actions:
    actions[action]["cmd"](repo, branch, args)
else:
    print("Unknown action '{}'".format(action))
    print_help('', [])
    sys.exit(1)
