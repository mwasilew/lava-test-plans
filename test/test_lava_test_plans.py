from lava_test_plans.__main__ import main

from unittest import TestCase
from unittest.mock import patch, MagicMock
from jinja2 import Environment, FileSystemLoader
import sys
import glob
import os
import pytest
import shlex
import tempfile

from test.validity_helpers import (
    test_lava_validity,
    test_lava_validity_container,
)

# all Linux tests all devices
devices = [os.path.basename(d) for d in glob.glob("lava_test_plans/devices/*")]
testcases = [
    os.path.basename(d)
    for d in glob.glob("lava_test_plans/testcases/[!android-]*.yaml")
]
variable_input_file = "variables.ini"
tests = []
for device in devices:
    if device == "variables":
        continue
    for testcase in testcases:
        tests.append((variable_input_file, device, testcase))


@pytest.mark.parametrize("param", tests)
def test_call_lava_test_plan_testcases(param):
    variable_input_file, device, testcase = param
    sys.argv = shlex.split(
        f'lava_test_plans --dry-run --variables "{variable_input_file}" --device-type "{device}" --test-case "{testcase}"'
    )
    assert main() == 0


# meta-qcom tests
meta_qcom_project_device_path = "lava_test_plans/projects/meta-qcom/devices"
meta_qcom_devices = [
    os.path.basename(d)
    for d in glob.glob("lava_test_plans/projects/meta-qcom/devices/*")
]
assert len(meta_qcom_devices) > 0
meta_qcom_testplans = [
    "meta-qcom/nodistro/boot",
    "meta-qcom/poky-altcfg/boot",
    "meta-qcom/qcom-distro/boot",
    "meta-qcom/qcom-distro/pre-merge",
    "meta-qcom/qcom-distro/kernel",
    "meta-qcom/qcom-distro/connectivity",
    "meta-qcom/qcom-distro/multimedia",
    "meta-qcom/qcom-distro/performance",
    "meta-qcom/qcom-distro/system",
    "meta-qcom/qcom-distro/virtualization",
]
assert len(meta_qcom_testplans) > 0
meta_qcom_variable_input_file = "projects/meta-qcom/variables.yaml"
tests = []
for device in meta_qcom_devices:
    for testplan in meta_qcom_testplans:
        tests.append(
            (
                meta_qcom_variable_input_file,
                device,
                testplan,
                meta_qcom_project_device_path,
            )
        )


@pytest.mark.parametrize("param", tests)
def test_call_lava_test_plan_testplans_project_meta_qcom(param):
    variable_input_file, device, testplan, project_device_path = param
    sys.argv = shlex.split(
        f'lava_test_plans --dry-run --variables "{variable_input_file}" --testplan-device-path "{project_device_path}" --device-type "{device}" --test-plan "{testplan}" {test_lava_validity} {test_lava_validity_container}'
    )
    assert main() == 0


# qcom-deb-images tests
qcom_deb_images_project_device_path = "lava_test_plans/projects/qcom-deb-images/devices"
qcom_deb_images_devices = [
    os.path.basename(d)
    for d in glob.glob("lava_test_plans/projects/qcom-deb-images/devices/*")
]
assert len(qcom_deb_images_devices) > 0
qcom_deb_images_testplans = [
    "qcom-deb-images/debian/boot",
    "qcom-deb-images/debian/pre-merge",
]
assert len(qcom_deb_images_testplans) > 0
qcom_deb_images_variable_input_file = "projects/qcom-deb-images/variables.yaml"
tests = []
for device in qcom_deb_images_devices:
    for testplan in qcom_deb_images_testplans:
        tests.append(
            (
                qcom_deb_images_variable_input_file,
                device,
                testplan,
                qcom_deb_images_project_device_path,
            )
        )


@pytest.mark.parametrize("param", tests)
def test_call_lava_test_plan_testplans_project_qcom_deb_images(param):
    variable_input_file, device, testplan, project_device_path = param
    sys.argv = shlex.split(
        f'lava_test_plans --dry-run --variables "{variable_input_file}" --testplan-device-path "{project_device_path}" --device-type "{device}" --test-plan "{testplan}" {test_lava_validity} {test_lava_validity_container}'
    )
    assert main() == 0


# meta-qcom-arduino tests
meta_qcom_arduino_project_device_path = (
    "lava_test_plans/projects/meta-qcom-arduino/devices"
)
meta_qcom_arduino_devices = [
    os.path.basename(d)
    for d in glob.glob("lava_test_plans/projects/meta-qcom-arduino/devices/*")
]
assert len(meta_qcom_arduino_devices) > 0
meta_qcom_arduino_testplans = [
    "meta-qcom-arduino/nodistro/boot",
    "meta-qcom-arduino/qcom-distro/boot",
]
assert len(meta_qcom_arduino_testplans) > 0
meta_qcom_arduino_variable_input_file = "projects/meta-qcom-arduino/variables.yaml"
tests = []
for device in meta_qcom_arduino_devices:
    for testplan in meta_qcom_arduino_testplans:
        tests.append(
            (
                meta_qcom_arduino_variable_input_file,
                device,
                testplan,
                meta_qcom_arduino_project_device_path,
            )
        )


@pytest.mark.parametrize("param", tests)
def test_call_lava_test_plan_testplans_project_meta_qcom_arduino(param):
    variable_input_file, device, testplan, project_device_path = param
    sys.argv = shlex.split(
        f'lava_test_plans --dry-run --variables "{variable_input_file}" --testplan-device-path "{project_device_path}" --device-type "{device}" --test-plan "{testplan}" {test_lava_validity} {test_lava_validity_container}'
    )
    assert main() == 0


# Test for template count with exclusions - dynamic approach
def get_excluded_testplans(device_name):
    """Extract EXCLUDED_TESTPLANS from device file using Jinja2."""
    # Need both devices and base template directories for extends to work
    template_dirs = ["lava_test_plans", "lava_test_plans/devices"]
    j2_env = Environment(loader=FileSystemLoader(template_dirs))
    device_template = j2_env.get_template(f"{device_name}")
    device_module = device_template.make_module()
    return getattr(device_module, "EXCLUDED_TESTPLANS", [])


# Test configuration
test_devices = ["qcs615-ride", "rb3gen2-core-kit", "iq-9075-evk"]
exclusion_variable_input_file = "variables.ini"
testplan_directory = "lava_test_plans/testplans/meta-qcom/qcom-distro/pre-merge"


@pytest.mark.parametrize("device_name", test_devices)
def test_template_count_with_exclusions(device_name, tmp_path):
    """
    Test that EXCLUDED_TESTPLANS works correctly.
    Dynamically calculates expected count based on device exclusions.
    Uses isolated temporary directory and explicitly tests --template-path.
    """
    # Count testplans from the actual testplan directory being tested
    total_testplans = len(glob.glob(f"{testplan_directory}/*.yaml"))

    full_device_name = f"projects/meta-qcom/devices/{device_name}"
    excluded = get_excluded_testplans(full_device_name)
    expected_count = total_testplans - len(excluded)

    # Use temporary directory for isolated output
    temp_output = tmp_path / "test_output"

    sys.argv = shlex.split(
        f'lava_test_plans --dry-run --variables "{exclusion_variable_input_file}" '
        f'--device-type "{full_device_name}" '
        f'--test-plan "meta-qcom/qcom-distro/pre-merge" '
        f'--template-path "lava_test_plans" '
        f'--dry-run-path "{temp_output}"'
    )

    assert main() == 0, f"Failed to generate templates for {device_name}"

    generated_files = glob.glob(
        str(temp_output / f"projects/meta-qcom/devices/{device_name}/*.yaml")
    )

    assert len(generated_files) == expected_count, (
        f"{device_name}: Expected {expected_count} (total={total_testplans}, "
        f"excluded={excluded}), got {len(generated_files)}"
    )
