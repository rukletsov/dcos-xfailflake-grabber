import json, os, re, shutil, sys, time

dcos_oss_dir = "dcos"
dcos_oss_repo = "https://github.com/dcos/dcos.git"
#dcos_ee_dir = "dcos-ee"
#dcos_ee_repo = "https://github.com/mesosphere/dcos-enterprise.git"

# Clone DC/OS OSS repo.
os.system("git clone {} {}".format(dcos_oss_repo, dcos_oss_dir))

# An alternative to scanning the whole repo is to whitelist directories of
# interest. For now there is no reason to do so.
rootdir = dcos_oss_dir
target_files = []
for folder, _, filenames in os.walk(rootdir):
    for filename in filenames:
        target_files.append(os.path.join(folder, filename))

# Scan contents of each target file in search for a specific pattern:
#     `...xfailflake(reason="DCOS... .... (\n)*... def test_foo(...`
# Once the pattern is matched extract DCOS or DCOS_OSS ticket and the associated
# text name. Augment the resulted tuple with the filename and convert it to a
# dictionary.
#
# NOTE: Use `.*?` to switch-off regex greediness; use `()` to leverage regex
# groups and yield ticket and test name in the resulted match.
pattern = "xfailflake\(reason=\"(DCOS\S*).*?def\s*(\S*)\("
xfailflakes = []
for file in target_files:
    with open(file, 'r') as f:
        contents = f.read()
        matched = re.findall(pattern, contents, re.MULTILINE|re.DOTALL)
        for t in matched:
            if not t:
                print "Unexpected match in file \"{}\"".format(file)
            if len(t) != 2:
                print "Match {} in file \"{}\" has {} components while 2 are expected".format(t, file, len(t))
            xfailflakes.append({
                "file": file,
                "test": t[1],
                "ticket": t[0]})

# Bake everything together with a timestamp and repo.
output = {
    "repo": dcos_oss_repo,
    "timestamp": time.strftime("%Y.%m.%d %H:%M"),
    "xfailflakes": xfailflakes
}

print "xfailflakes JSONified: '{}'".format(json.dumps(output))

# Cleanup after ourselves.
print "Cleaning up: removing {}".format(dcos_oss_dir)
shutil.rmtree(dcos_oss_dir)
