import codecs, json, os, re, shutil, sys, time

# Dances around python versions and modules conflict
try:
    from BaseHTTPServer import HTTPServer
    from BaseHTTPServer import BaseHTTPRequestHandler
except ImportError:
    from http.server import HTTPServer
    from http.server import BaseHTTPRequestHandler


# TODO(alexr): To support parallel requests, temp folders should have unique
# names.
dcos_oss_dir = "dcos"
dcos_oss_repo = "https://github.com/dcos/dcos.git"
#dcos_ee_dir = "dcos-ee"
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
def get_xfailflakes_from_files(target_files):
    pattern = "xfailflake\(reason=\"(DCOS\S*).*?def\s*(\S*)\("
    xfailflakes = []
    for file in target_files:
        with codecs.open(file, 'r', encoding='utf-8', errors='ignore') as f:
            contents = f.read()
            matched = re.findall(pattern, contents, re.MULTILINE|re.DOTALL)
            for t in matched:
                if not t:
                    print("Unexpected match in file \"{}\"".format(file))
                if len(t) != 2:
                    print("Match {} in file \"{}\" has {} components while 2 are expected".format(t, file, len(t)))
                xfailflakes.append({
                    "file": file,
                    "test": t[1],
                    "ticket": t[0]})
    return xfailflakes


# Combines all pieces together: clone the repo, scan it, generate the output.
#
# TODO(alexr): Add support for branches.
def get_xfailflakes_from_repo(repo, tmpdir):
    # Clone DC/OS OSS repo.
    os.system("git clone {} {}".format(repo, tmpdir))

    target_files = get_target_files(tmpdir)
    xfailflakes = get_xfailflakes_from_files(target_files)

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

    rows = xfailflakes

    output = {
        "columns": columns,
        "rows": rows
    }

    return json.dumps(output)


# For each GET request this handler replies with JSON in redash format.
#
# TODO(alexr): Serve both formats, redash and the default one.
class RedashHandler(BaseHTTPRequestHandler):
    def _set_headers(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

    def do_GET(self):
        self._set_headers()
        if self.path == '/':
            dcos_oss_output = get_xfailflakes_from_repo(dcos_oss_repo, dcos_oss_dir)
            self.wfile.write(convert_to_redash(dcos_oss_output).encode('utf-8'))


# Starts a simple server with the `RedashHandler`.
def serve(port):
    server_address = ('', port)
    httpd = HTTPServer(server_address, RedashHandler)

    # TODO(alexr): Spawn the server in a separate thread.
    print("Starting httpd on port {}".format(port))
    httpd.serve_forever()


# Entrypoint. If `port` has been passed, serve JSON for GET requests,
# otherwise spit out JSON to stdout.
if __name__ == "__main__":
    if len(sys.argv) == 2:
        serve(int(sys.argv[1]))
    else:
        dcos_oss_output = get_xfailflakes_from_repo(dcos_oss_repo, dcos_oss_dir)
        print("xfailflakes JSONified: '{}'".format(convert_to_default_format(dcos_oss_output, dcos_oss_repo)))
        print("xfailflakes redashified: '{}'".format(convert_to_redash(dcos_oss_output)))
