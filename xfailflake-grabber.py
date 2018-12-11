
import codecs, json, os, re, shutil, sys, time, uuid

# Dances around python versions and modules conflict
try:
    from BaseHTTPServer import HTTPServer
    from BaseHTTPServer import BaseHTTPRequestHandler
except ImportError:
    from http.server import HTTPServer
    from http.server import BaseHTTPRequestHandler

# Internal helpers.
import postgres_redshift as db


dcos_oss_repo = "https://github.com/dcos/dcos.git"
#dcos_ee_repo = "https://github.com/mesosphere/dcos-enterprise.git"


# An alternative to scanning the whole repo is to whitelist directories of
# interest. For now there is no reason to do so.
def get_target_files(rootdir):
    target_files = []
    for folder, _, filenames in os.walk(rootdir):
        for filename in filenames:
            target_files.append(os.path.join(folder, filename))
    return target_files


# Scan contents of each target file in search for a specific pattern:
#     `...xfailflake(reason="DCOS... .... (\n)*... def test_foo(...`
# Once the pattern is matched extract DCOS or DCOS_OSS ticket and the associated
# text name. Augment the resulted tuple with the filename and convert it to a
# dictionary.
#
# NOTE: Use `.*?` to switch-off regex greediness; use `()` to leverage regex
# groups and yield ticket and test name in the resulted match.
def get_xfailflakes_from_files(rootdir, target_files):
    pattern = "xfailflake\(reason=\"(DCOS\S*).*?def\s*(\S*)\("
    xfailflakes = []
    for filepath in target_files:
        if not filepath.startswith(rootdir):
            print("Error: Unexpected file '{}' in '{}'".format(filepath, rootdir))

        with codecs.open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            contents = f.read()
            matched = re.findall(pattern, contents, re.MULTILINE|re.DOTALL)
            for t in matched:
                if not t:
                    print("Error: Unexpected match in file '{}'".format(filepath))
                if len(t) != 2:
                    print("Error: Match {} in file '{}' has {} components while "
                          "2 are expected".format(t, filepath, len(t)))
                xfailflakes.append({
                    "file": filepath[len(rootdir):],
                    "test": t[1],
                    "ticket": t[0]})
    return xfailflakes


# Combines all pieces together: clone the repo, scan it, generate the output.
#
# TODO(alexr): Add support for branches.
def get_xfailflakes_from_repo(repo):
    tmpdir = "repo_" + str(uuid.uuid1())

    # Clone DC/OS OSS repo.
    os.system("git clone {} {}".format(repo, tmpdir))

    target_files = get_target_files(tmpdir)
    xfailflakes = get_xfailflakes_from_files(tmpdir, target_files)

    # Cleanup after ourselves.
    print("Cleaning up: removing {}".format(tmpdir))
    shutil.rmtree(tmpdir)

    return xfailflakes


# Bakes xfailflakes together with a timestamp and a repo, and spits out JSON.
def convert_to_default_format(xfailflakes, repo):
    output = {
        "repo": repo,
        "timestamp": time.strftime("%Y.%m.%d %H:%M"),
        "xfailflakes": xfailflakes
    }

    return json.dumps(output)


# Redash requires particular format for JSON input,
# see https://redash.io/help/data-sources/querying-urls .
# We organise the output in three columns: "test", "ticket", "file".
def convert_to_redash(xfailflakes):
    columns = [
        {
            "name": "test",
            "type": "string",
            "friendly_name": "Test"
        },
        {
            "name": "ticket",
            "type": "string",
            "friendly_name": "JIRA ticket"
        },
        {
            "name": "file",
            "type": "string",
            "friendly_name": "File"
        }
    ]

    output = {
        "columns": columns,
        "rows": xfailflakes
    }

    return json.dumps(output)


# For each GET request this handler replies with JSON in redash format.
#
# TODO(alexr): Serve both formats, redash and the default one.
class RedashHandler(BaseHTTPRequestHandler):
    repo = None

    def _set_headers(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

    def do_GET(self):
        self._set_headers()
        if self.path == '/' and repo is not None:
            xfailflakes = get_xfailflakes_from_repo(repo)
            print("Serving xfailflakes redashified:\n'{}'".format(convert_to_redash(xfailflakes)))
            self.wfile.write(convert_to_redash(xfailflakes).encode('utf-8'))


class Server(HTTPServer):
    def serve_forever(self, repo):
        self.RequestHandlerClass.repo = repo
        HTTPServer.serve_forever(self)


def dump_to_stdout(repo, args):
    xfailflakes = get_xfailflakes_from_repo(repo)
    print("xfailflakes JSONified:\n'{}'".format(convert_to_default_format(xfailflakes, repo)))


# Starts a simple server with the `RedashHandler`.
def serve_redash(repo, args):
    port = int(args[0])

    server_address = ('', port)
    httpd = Server(server_address, RedashHandler)

    # TODO(alexr): Spawn the server in a separate thread.
    print("Starting httpd on port {}".format(port))
    httpd.serve_forever(repo)


def push_to_redshift(repo, args):
    conn = db.connection()
    cursor = conn.cursor()
    db.ensure_table(cursor)

    xfailflakes = get_xfailflakes_from_repo(repo)

    for xfailflake in xfailflakes:
        print("Inserting xfailflake: {}".format(xfailflake))
#        db.insert(cursor, xfailflake)


def print_help(repo, args):
    print(
        "{0}Scans a given repo for 'xfailflake' marked tests and presents the{0}"
        "resulted output in various ways. Relies on a specific pattern to{0}"
        "extract the test name and the associated JIRA ticket.{0}{0}"
        "Usage: python xfailflake-grabber.py <action> <repository> [args]{0}{0}"
        "Available actions:".format(os.linesep)
    )
    for a in actions:
        print "  {0} - {1}".format(a, actions[a]["msg"])


# List of supported actions with callback and help message.
#
# TODO(alexr): Support branches.
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

    if len(sys.argv) < 3:
        print("Error: Each <action> requires target <repository>")
        print_help('', [])
        sys.exit(1)

    repo = sys.argv[2]
    args = sys.argv[3:]

if action in actions:
    actions[action]["cmd"](repo, args)
else:
    print("Unknown action '{}'".format(action))
    print_help('', [])
    sys.exit(1)
