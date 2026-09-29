#!/usr/bin/env python3
#
# Copyright 2026 Qualcomm Technologies, Inc.
#
# SPDX-License-Identifier: MIT
"""Build the LAVA test overlay of rendered jobs without a device.

The dispatcher fetches every test definition of a job, reads it and writes the
scripts lava-test-runner executes into an overlay before the device boots. A
definition that cannot be fetched, a path missing from the repository or a
malformed test definition only fails there, in the lab, after the image was
flashed. This script walks the same steps offline:

- TestDefinitionAction.validate/populate: per namespace, every test action is a
  stage, every definition gets the name <index>_<name>
- GitRepoAction, UrlRepoAction, InlineRepoAction: fetch the definition and
  read the YAML file at its path
- RepoAction.store_testdef: the metadata LAVA keeps from the definition
- TestOverlayAction, TestInstallAction, TestRunnerAction: write testdef.yaml,
  uuid, testdef_metadata, install.sh and run.sh
- TestDefinitionAction.run: write lava-test-runner.conf for every stage

It follows lava_dispatcher/actions/deploy/testdef.py. Repositories are fetched
once and shared between definitions, so an overlay directory only holds the
files LAVA generates, not a copy of the repository.
"""

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import urllib.request

import yaml

# lava_common/constants.py
DEFAULT_TEST_NAME_CLASS = r"^[\w\d\_\-]+$"
LAVA_TEST_RESULTS_DIR = "/lava-%s"
SKIP_INSTALL = ["keys", "sources", "deps", "steps", "git-repos", "all"]


class OverlayError(Exception):
    """Anything that makes the dispatcher fail the job: JobError, TestError,
    InfrastructureError or a crash on a malformed definition."""


def yaml_safe_load(stream):
    # lava_common.yaml uses the C loader when it is available
    return yaml.load(stream, Loader=getattr(yaml, "CSafeLoader", yaml.SafeLoader))


def yaml_safe_dump(data):
    return yaml.dump(data, Dumper=getattr(yaml, "CSafeDumper", yaml.SafeDumper))


def run(args, cwd=None):
    try:
        return subprocess.run(
            args, cwd=cwd, check=True, capture_output=True, text=True
        ).stdout
    except subprocess.CalledProcessError as exc:
        raise OverlayError(
            "'%s' failed: %s" % (" ".join(args), (exc.stderr or exc.stdout).strip())
        )


class Fetcher:
    """Fetches each repository once for the whole run."""

    def __init__(self, cache_dir):
        self.cache_dir = cache_dir
        self.cache = {}

    def _dir(self, kind, *key):
        digest = hashlib.sha256("\0".join(map(str, key)).encode()).hexdigest()[:16]
        return os.path.join(self.cache_dir, "%s-%s" % (kind, digest))

    def _remember(self, key, fetch):
        if key not in self.cache:
            try:
                self.cache[key] = (fetch(), None)
            except OverlayError as exc:
                self.cache[key] = (None, exc)
        tree, error = self.cache[key]
        if error:
            raise error
        return tree

    def url(self, url, strip_components):
        """UrlRepoAction: download the file and untar it"""

        def fetch():
            tarball = self._dir("download", url)
            if not os.path.exists(tarball):
                try:
                    with urllib.request.urlopen(url, timeout=120) as response:
                        with open(tarball + ".part", "wb") as out:
                            shutil.copyfileobj(response, out)
                except OSError as exc:
                    raise OverlayError("Unable to download %s: %s" % (url, exc))
                os.rename(tarball + ".part", tarball)
            tree = self._dir("url", url, strip_components)
            shutil.rmtree(tree, ignore_errors=True)
            os.makedirs(tree)
            # lava_dispatcher.utils.compression.untar_file
            args = ["tar", "-h", "-xf", tarball]
            if strip_components:
                args.append("--strip-components=%d" % strip_components)
            try:
                run(args, cwd=tree)
            except OverlayError as exc:
                raise OverlayError("unable to untar file %s: %s" % (url, exc))
            return tree

        return self._remember(("url", url, strip_components), fetch)

    def git(self, url, revision=None, branch=None):
        """GitHelper.clone: clone, check the revision out, report the commit"""

        def fetch():
            mirror = self._dir("mirror", url)
            if not os.path.exists(mirror):
                run(["git", "clone", "--quiet", "--mirror", url, mirror])
            tree = self._dir("git", url, revision, branch)
            shutil.rmtree(tree, ignore_errors=True)
            args = ["git", "clone", "--quiet"]
            if branch is not None:
                args += ["-b", branch]
            run(args + [mirror, tree])
            if revision is not None:
                run(["git", "-C", tree, "checkout", "--quiet", str(revision)])
            commit = run(["git", "-C", tree, "log", "-1", "--pretty=%H"]).strip()
            return tree, commit

        return self._remember(("git", url, revision, branch), fetch)


def test_namespaces(job):
    """lava_dispatcher.job parser: test actions grouped by namespace, in job
    order, including the ones of a repeat block"""
    actions = []
    for action in job.get("actions", []):
        if "repeat" in action:
            actions += action["repeat"].get("actions", [])
        else:
            actions.append(action)
    namespaces = {}
    for action in actions:
        test = action.get("test")
        if isinstance(test, dict) and "definitions" in test:
            namespace = test.get("namespace", "common")
            namespaces.setdefault(namespace, []).append(test["definitions"])
    return namespaces


def deploy_distro(job, namespace):
    for action in job.get("actions", []):
        deploy = action.get("deploy")
        if isinstance(deploy, dict) and deploy.get("namespace", "common") == namespace:
            return deploy.get("os")
    return None


def validate(test_list):
    """TestDefinitionAction, TestOverlayAction, TestInstallAction and
    TestRunnerAction validate()"""
    errors = []
    exp = re.compile(DEFAULT_TEST_NAME_CLASS)
    names = []
    for testdefs in test_list:
        for testdef in testdefs:
            if "parameters" in testdef and not isinstance(testdef["parameters"], dict):
                errors.append("Invalid test definition parameters")
            if "from" not in testdef:
                errors.append("missing 'from' field in test definition %s" % testdef)
            elif testdef["from"] not in ("git", "url", "inline"):
                errors.append(
                    "No testdef_repo handler is available for the given"
                    " repository type '%s'." % testdef["from"]
                )
            if "name" not in testdef:
                errors.append("missing 'name' field in test definition %s" % testdef)
                continue
            if not exp.match(str(testdef["name"])):
                errors.append(
                    "Invalid characters found in test definition name: %s"
                    % testdef["name"]
                )
            names.append(testdef["name"])
            if "expected" in testdef and not isinstance(testdef["expected"], list):
                errors.append("'expected' should be a test case list")
            if "repository" not in testdef:
                errors.append("%s: repository not specified" % testdef["name"])
            if "path" not in testdef:
                errors.append("%s: Missing path in parameters" % testdef["name"])
            skip = testdef.get("skip_install")
            if skip and set(skip) - set(SKIP_INSTALL):
                errors.append("%s: Unrecognised skip_install value" % testdef["name"])
    if len(names) != len(set(names)):
        errors.append("Test definition names need to be unique.")
    return errors


def handle_parameters(testdef, parameters):
    """TestOverlayAction.handle_parameters"""

    def as_dict(data, key):
        if not isinstance(data[key], dict):
            raise OverlayError("Test definition item '%s' should be a dictionary" % key)
        return data[key].items()

    def lines(data, keys):
        ret = []
        for key in keys:
            if key in data:
                for name, value in as_dict(data, key):
                    ret.append("%s='%s'\n" % (name, "" if value is None else value))
        return ret

    return (
        ["###default parameters from test definition###\n"]
        + lines(testdef, ("params", "parameters"))
        + ["######\n", "###test parameters from job submission###\n"]
        # the job parameters are written the other way round
        + lines(parameters, ("parameters", "params"))
        + ["######\n"]
    )


def read_testdef(tree, path):
    try:
        with open(os.path.join(tree, path)) as test_file:
            return yaml_safe_load(test_file)
    except (OSError, yaml.YAMLError) as exc:
        raise OverlayError("Unable to open test definition '%s': %s" % (path, exc))


def store_testdef(testdef, vcs_name, commit_id=None):
    """RepoAction.store_testdef"""
    try:
        metadata = testdef["metadata"]
        val = {
            "os": metadata.get("os", ""),
            "devices": metadata.get("devices", ""),
            "environment": metadata.get("environment", ""),
            "branch_vcs": vcs_name,
            "project_name": metadata["name"],
        }
    except (KeyError, TypeError, AttributeError) as exc:
        raise OverlayError("test definition has no metadata name: %r" % exc)
    if commit_id is not None:
        val["commit_id"] = commit_id
    if "parse" in testdef:
        # compiled by the test shell once the results come in
        try:
            re.compile(testdef["parse"].get("pattern", ""))
        except (re.error, AttributeError, TypeError) as exc:
            raise OverlayError("invalid parse pattern: %s" % exc)
    return val


def install_git_repos(fetcher, testdef, parameters, runner_path):
    """TestInstallAction.install_git_repos, clones are left in the cache"""

    def lookup(key, variable):
        if not variable or key not in ("url", "destination", "branch"):
            return variable
        ret = variable
        if variable in (testdef.get("params") or {}):
            ret = testdef["params"][variable]
        if variable in (parameters.get("parameters") or {}):
            ret = parameters["parameters"][variable]
        return ret

    seen = set()
    for repo in testdef["install"].get("git-repos", []) or []:
        if isinstance(repo, str):
            fetcher.git(repo)
        elif isinstance(repo, dict):
            url = lookup("url", repo.get("url", ""))
            branch = lookup("branch", repo.get("branch"))
            if not url:
                raise OverlayError(
                    "Invalid git-repos dictionary in install definition."
                )
            subdir = url.replace(".git", "", len(url) - 1)
            destination = lookup(
                "destination", repo.get("destination", os.path.basename(subdir))
            )
            if destination:
                dest_path = os.path.join(runner_path, destination)
                if os.path.abspath(runner_path) != os.path.dirname(dest_path):
                    raise OverlayError(
                        "Destination path is unacceptable %s" % destination
                    )
                if destination in seen:
                    raise OverlayError(
                        "Cannot mix string and url forms for the same repository."
                    )
                seen.add(destination)
                fetcher.git(url, branch=branch)
        else:
            raise OverlayError("Unrecognised git-repos block.")


def build_overlay(fetcher, job, overlay_dir, job_id):
    """Returns the list of errors; the overlay is written to overlay_dir"""
    errors = []
    for namespace, test_list in test_namespaces(job).items():
        problems = validate(test_list)
        if problems:
            errors += ["[%s] %s" % (namespace, p) for p in problems]
            continue
        results_dir = LAVA_TEST_RESULTS_DIR % job_id
        overlay_base = os.path.join(overlay_dir, namespace, results_dir.lstrip("/"))
        distro = deploy_distro(job, namespace)
        index = []
        for stage, testdefs in enumerate(test_list):
            runner_conf = []
            for testdef in testdefs:
                test_name = "%d_%s" % (len(index), testdef["name"])
                index.append(testdef["name"])
                runner_path = os.path.join(results_dir, str(stage), "tests", test_name)
                path = os.path.join(overlay_base, str(stage), "tests", test_name)
                try:
                    write_test(
                        fetcher,
                        testdef,
                        test_name,
                        stage,
                        len(index),
                        job_id,
                        runner_path,
                        path,
                        distro,
                    )
                except OverlayError as exc:
                    errors.append("[%s] %s: %s" % (namespace, test_name, exc))
                runner_conf.append(runner_path + "\n")
            os.makedirs(os.path.join(overlay_base, str(stage)), exist_ok=True)
            with open(
                os.path.join(overlay_base, str(stage), "lava-test-runner.conf"), "a"
            ) as conf:
                conf.writelines(runner_conf)
    return errors


def write_test(
    fetcher, testdef, test_name, stage, level, job_id, runner_path, path, distro
):
    """One RepoAction followed by its TestOverlayAction, TestInstallAction and
    TestRunnerAction"""
    params = testdef
    source = params["from"]
    commit_id = None
    os.makedirs(path)
    if source == "url":
        tree = fetcher.url(params["repository"], params.get("strip-components", 0))
    elif source == "git":
        revision = params.get("revision")
        tree, commit_id = fetcher.git(
            params["repository"], revision=revision, branch=params.get("branch")
        )
    else:
        if not isinstance(params["repository"], dict):
            raise OverlayError("Invalid inline definition in job definition")
        tree = path
        yaml_file = os.path.join(tree, params["path"])
        os.makedirs(os.path.dirname(yaml_file), exist_ok=True)
        with open(yaml_file, "w") as test_file:
            test_file.write(yaml_safe_dump(params["repository"]))

    testdef_yaml = read_testdef(tree, params["path"])
    metadata = store_testdef(testdef_yaml, source, commit_id)
    uuid = "%s_%s" % (job_id, level)

    # TestOverlayAction
    with open(os.path.join(path, "testdef.yaml"), "w") as out:
        out.write(yaml_safe_dump(testdef_yaml))
    with open(os.path.join(path, "uuid"), "w") as out:
        out.write(uuid)
    with open(os.path.join(path, "testdef_metadata"), "w") as out:
        out.write(yaml_safe_dump(metadata))

    # TestInstallAction
    skip = params.get("skip_install") or []
    if "all" in skip:
        skip = SKIP_INSTALL[:-1]
    if "install" in testdef_yaml:
        install = testdef_yaml["install"]
        if not isinstance(install, dict):
            raise OverlayError("install block should be a dictionary")
        content = handle_parameters(testdef_yaml, params)
        if "keys" not in skip:
            content += ["lava-add-keys %s\n" % k for k in install.get("keys", []) or []]
        if "sources" not in skip:
            content += [
                "lava-add-sources %s\n" % s for s in install.get("sources", []) or []
            ]
        if "deps" not in skip:
            deps = list(install.get("deps", []) or [])
            if distro:
                deps += install.get("deps-" + distro, []) or []
            if deps:
                content.append("lava-install-packages %s\n" % " ".join(map(str, deps)))
        if "steps" not in skip:
            steps = install.get("steps", []) or []
            if steps:
                content += ["cd %s\n" % runner_path, "pwd\n"]
                content += ["%s\n" % cmd for cmd in steps]
        with open(os.path.join(path, "install.sh"), "w") as out:
            out.writelines(content)
        if "git-repos" not in skip:
            install_git_repos(fetcher, testdef_yaml, params, path)

    # TestRunnerAction
    if params["name"] == "lava":
        raise OverlayError('The "lava" test definition name is reserved.')
    signal = params.get("lava-signal", "stdout")
    content = handle_parameters(testdef_yaml, params)
    content += [
        "set -e\n",
        "set -x\n",
        "export TESTRUN_ID=%s\n" % test_name,
        "cd %s\n" % runner_path,
        'UUID="$(cat uuid)"\n',
        "set +x\n",
    ]
    if signal == "kmsg":
        content += [
            "# USE_KMSG\n",
            "export KMSG=true\n",
            'echo "<0><LAVA_SIGNAL_STARTRUN $TESTRUN_ID $UUID>" > /dev/kmsg\n',
        ]
    else:
        content.append('echo "<LAVA_SIGNAL_STARTRUN $TESTRUN_ID $UUID>"\n')
    content.append("set -x\n")
    run_block = testdef_yaml.get("run", {}) or {}
    if not isinstance(run_block, dict):
        raise OverlayError("run block should be a dictionary")
    steps = run_block.get("steps", [])
    for cmd in [step for step in steps or [] if step is not None]:
        if not isinstance(cmd, str):
            raise OverlayError("run step is not a string: %r" % (cmd,))
        if "--cmd" in cmd or "--shell" in cmd:
            cmd = re.sub(r"\$(\d+)\b", r"\\$\1", cmd)
        content.append("%s\n" % cmd)
    content.append("set +x\n")
    if signal == "kmsg":
        content += [
            "unset KMSG\n",
            'echo "<0><LAVA_SIGNAL_ENDRUN $TESTRUN_ID $UUID>" > /dev/kmsg\n',
        ]
    else:
        content.append('echo "<LAVA_SIGNAL_ENDRUN $TESTRUN_ID $UUID>"\n')
    with open(os.path.join(path, "run.sh"), "a") as out:
        out.writelines(content)
    # lava-test-runner runs it with sh, but syntax errors are cheap to catch here
    try:
        run(["sh", "-n", os.path.join(path, "run.sh")])
    except OverlayError as exc:
        raise OverlayError("run.sh is not valid shell: %s" % exc)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("jobs", nargs="+", help="job files or directories")
    parser.add_argument("--output", required=True, help="overlay output directory")
    parser.add_argument("--cache", help="repository cache (default: <output>/.cache)")
    args = parser.parse_args()

    # (job file, overlay directory relative to --output)
    job_files = []
    for item in args.jobs:
        if os.path.isdir(item):
            for root, _, files in os.walk(item):
                for name in files:
                    if name.endswith(".yaml"):
                        job_file = os.path.join(root, name)
                        job_files.append((job_file, os.path.relpath(job_file, item)))
        else:
            job_files.append((item, os.path.basename(item)))
    job_files.sort()

    cache = args.cache or os.path.join(args.output, ".cache")
    os.makedirs(cache, exist_ok=True)
    fetcher = Fetcher(cache)
    failed = 0
    for job_id, (job_file, name) in enumerate(job_files, 1):
        overlay_dir = os.path.join(args.output, os.path.splitext(name)[0])
        shutil.rmtree(overlay_dir, ignore_errors=True)
        try:
            with open(job_file) as f:
                job = yaml_safe_load(f)
            errors = build_overlay(fetcher, job, overlay_dir, job_id)
        except (OSError, yaml.YAMLError) as exc:
            errors = [str(exc)]
        if errors:
            failed += 1
            for error in errors:
                print("::error file=%s::%s" % (job_file, error))
        else:
            print("ok %s" % job_file)
    print("%d of %d job(s) failed" % (failed, len(job_files)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
