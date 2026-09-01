from lava_test_plans.__main__ import main

from unittest import TestCase
import sys
import glob
import os
import pytest
import shlex

from test.validity_helpers import (
    test_lava_validity,
    test_lava_validity_container,
)

devices = ["qemu_arm64"]
testcase = "boot.yaml"
variable_input_files = [
    "test/variables-visibility.ini",
    "test/variables-visibility-one-group.ini",
]
tests = []
for device in devices:
    for variable_file in variable_input_files:
        tests.append((variable_file, device, testcase))


@pytest.mark.parametrize("param", tests)
def test_call_lava_visibility_group_testcase(param):
    variable_input_file, device, testcase = param
    sys.argv = shlex.split(
        f'lava_test_plans --dry-run --variables "{variable_input_file}" --device-type "{device}" --test-case "{testcase}" {test_lava_validity} {test_lava_validity_container}'
    )
    assert main() == 0
