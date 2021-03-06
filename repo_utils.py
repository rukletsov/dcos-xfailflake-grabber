
import codecs, os, re, shutil, uuid


# Pattern to match 'xfailflake' marked tests, see `get_xfailflakes_from_files()`.
# Each match yields a 3-tuple: <jira_ticket, since_when_muted, test_name>.
#
# We start with searching for `xfailflake(`, then skip symbols until we observe
# `jira`, which value we extract, then skip sympols again and scan for `since`,
# last comes the test name, which we expect to be enclosed between `def` and `)`.
#
# NOTE: We use `.*?` to switch-off regex greediness and `()` to leverage regex
# groups and yield ticket and test name in the resulted match.
PATTERN = "xfailflake\(.*?jira=['\"](\S*?)['\"].*?since=['\"](\S*?)['\"].*?def\s*(\S*?)\("


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
def get_xfailflakes_from_files(repo, branch, rootdir, target_files):
    xfailflakes = []
    for filepath in target_files:
        if not filepath.startswith(rootdir):
            raise RuntimeError("Unexpected file '{}' in '{}'".format(filepath, rootdir))

        with codecs.open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            contents = f.read()
            matched = re.findall(PATTERN, contents, re.MULTILINE | re.DOTALL)
            for t in matched:
                if not t:
                    raise RuntimeError("Unexpected match in file '{}'".format(filepath))
                if len(t) != 3:
                    raise RuntimeError("Match {} in file '{}' has {} components "
                        "while 3 are expected".format(t, filepath, len(t)))
                xfailflakes.append({
                    "file": filepath[len(rootdir):],
                    "test": t[2],
                    "ticket": t[0],
                    "since": t[1],
                    "repo": repo,
                    "branch": branch})

    return xfailflakes


# Combines all pieces together: clone the repo, scan it, generate the output.
#
# Return value is a list of dictionaries:
#     [
#         {
#             "file": <filepath>,
#             "test": <testname>,
#             "ticket": <jira ticket>,
#             "since": <date>,
#             "repo": <repo>,
#             "branch": <branch>
#         },
#         ...
#     ]
def get_xfailflakes_from_repo(repo, branch):
    tmpdir = "repo_" + str(uuid.uuid1())

    # Clone DC/OS OSS repo. Use `GITHUB_TOKEN` env var if present.
    repocmd = repo

    token = os.getenv("GITHUB_TOKEN")
    if token is not None:
        index = repo.find("github")
        repocmd = repo[:index] + token + "@" + repo[index:]

    os.system("git clone {} {}".format(repocmd, tmpdir))
    os.chdir(tmpdir)
    os.system("git checkout -b {0} origin/{0}".format(branch))
    os.chdir("..")

    # Extract xfailflakes.
    target_files = get_target_files(tmpdir)
    xfailflakes = get_xfailflakes_from_files(repo, branch, tmpdir, target_files)

    # Cleanup after ourselves.
    #
    # TODO(alexr): If an exception is thrown above, this will be skipped.
    print("Cleaning up: removing {}".format(tmpdir))
    shutil.rmtree(tmpdir)

    return xfailflakes
