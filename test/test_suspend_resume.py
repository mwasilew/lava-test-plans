import shlex
import sys

from ruamel.yaml import YAML

from lava_test_plans.__main__ import main

PROJECT = "projects/meta-qcom-arduino"


def render(tmp_path, modes=None):
    variables = f"{PROJECT}/variables.yaml"
    if modes is not None:
        extra = tmp_path / "modes.yaml"
        extra.write_text(f"SUSPEND_MODES: {modes!r}\n")
        variables += f" {extra}"
    sys.argv = shlex.split(
        f'lava_test_plans --dry-run --dry-run-path "{tmp_path}" '
        f"--variables {variables} "
        f'--testplan-device-path "lava_test_plans/{PROJECT}/devices" '
        f'--device-type ventuno-q --test-plan "meta-qcom-arduino/qcom-distro/suspend"'
    )
    assert main() == 0
    path = tmp_path / "ventuno-q" / "suspend-resume.yaml"
    return YAML(typ="safe").load(open(path))


def steps(job):
    out = []
    for action in job["actions"]:
        if "command" in action:
            out.append(action["command"]["name"])
        for d in action.get("test", {}).get("definitions", []):
            out.append(d["name"])
        for i in action.get("test", {}).get("interactive", []):
            out.append(i["name"])
    return out


def suspend_commands(job):
    return [
        s["command"]
        for action in job["actions"]
        for i in action.get("test", {}).get("interactive", [])
        for s in i["script"]
        if s["name"].endswith("-request")
    ]


def test_default_mode(tmp_path):
    job = render(tmp_path)
    assert steps(job) == [
        "pre-suspend-check-default",
        "suspend-default",
        "wait_resume",
        "wake_up",
        "resume-default",
        "shell-default",
        "resume-check-default",
    ]
    (command,) = suspend_commands(job)
    assert "mem_sleep" not in command
    assert "echo mem > /sys/power/state" in command


def test_one_cycle_per_mode(tmp_path):
    job = render(tmp_path, ["s2idle", "deep"])
    assert steps(job) == [
        "pre-suspend-check-s2idle",
        "suspend-s2idle",
        "wait_resume",
        "wake_up",
        "resume-s2idle",
        "shell-s2idle",
        "resume-check-s2idle",
        "pre-suspend-check-deep",
        "suspend-deep",
        "wait_resume",
        "wake_up",
        "resume-deep",
        "shell-deep",
        "resume-check-deep",
    ]
    commands = suspend_commands(job)
    assert "echo s2idle > /sys/power/mem_sleep" in commands[0]
    assert "echo deep > /sys/power/mem_sleep" in commands[1]


def test_prompts(tmp_path):
    # The console echoes the command, so the markers must not match their
    # own echo; the last step hands the test shell the image's prompt.
    job = render(tmp_path)
    prompts = [
        p
        for action in job["actions"]
        for i in action.get("test", {}).get("interactive", [])
        for p in i["prompts"]
    ]
    assert prompts == [
        "lava-suspend-2",
        "lava-resumed-3",
        "root@ventuno-q",
        "root@(.*):[/~]#",
    ]
    (command,) = suspend_commands(job)
    for marker in ("lava-suspend-2", "lava-resumed-3", "lava-suspend-failed-3"):
        assert marker not in command


def test_failed_suspend_stops_the_job(tmp_path):
    job = render(tmp_path)
    (returned,) = [
        s
        for action in job["actions"]
        for i in action.get("test", {}).get("interactive", [])
        for s in i["script"]
        if s["name"].endswith("-returned")
    ]
    assert returned["failures"] == [
        {
            "message": "lava-suspend-failed-3",
            "exception": "TestError",
            "error": "echo mem > /sys/power/state failed",
        }
    ]


def test_prompt_without_boot_os_prompt(tmp_path):
    # A device without a BOOT_OS_PROMPT boots on the fallback prompt; the
    # hand-back step must wait for it as well.
    extra = tmp_path / "prompt.yaml"
    extra.write_text("BOOT_OS_PROMPT: []\n")
    sys.argv = shlex.split(
        f'lava_test_plans --dry-run --dry-run-path "{tmp_path}" '
        f'--variables variables.ini "{extra}" --device-type qrb5165-rb5 '
        "--test-case suspend-resume.yaml"
    )
    assert main() == 0
    job = YAML(typ="safe").load(open(tmp_path / "qrb5165-rb5" / "suspend-resume.yaml"))
    (shell,) = [
        i
        for action in job["actions"]
        for i in action.get("test", {}).get("interactive", [])
        if i["name"].startswith("shell-")
    ]
    assert shell["prompts"] == ["root@(.*):[/~]#"]
