# Test cases

Each file in this directory renders one LAVA job. Files whose name is not
`boot.yaml` or `u-boot.yaml` group test definitions from
[qcom-linux-testkit](https://github.com/qualcomm-linux/qcom-linux-testkit) by
functional area, so that one area maps to one LAVA job and one result suite per
test definition.

The paths in `all_tests` refer to test definitions as they are laid out from tag
`testkit-2026.08.30` onwards. Set `TEST_DEFINITIONS_REPOSITORY` (and optionally
`TEST_DEFINITIONS_REVISION`) in the project variables to pin the revision that
is fetched.

## Areas

| Test case | qcom-linux-testkit suites |
| --- | --- |
| `kernel-baseport.yaml` | `Kernel/Baseport` core (CPU, IRQ, timers, buses, IOMMU), `Kernel/DCVS`, `Kernel/Scheduler` |
| `kernel-remoteproc.yaml` | `Kernel/Baseport` remoteproc family and SMP2P |
| `kernel-interconnect.yaml` | `Kernel/Baseport` interconnect, LLCC, BWMON, MEMLAT, EDAC, DMAEngine |
| `kernel-peripherals.yaml` | `Kernel/Baseport` PCIe, USB host, IPA, RMNET |
| `kernel-storage.yaml` | `Kernel/Baseport/Storage` |
| `kernel-security.yaml` | `Kernel/Baseport` crypto, RNG, fscrypt and the MinkIPC/QTEE stack |
| `kernel-coresight.yaml` | `Kernel/DEBUG` plus the STM/ETM baseport tests |
| `kernel-rt.yaml` | `Kernel/RT-tests` |
| `connectivity-bluetooth.yaml` | `Connectivity/Bluetooth` |
| `connectivity-ethernet.yaml` | `Connectivity/Ethernet` |
| `connectivity-wifi.yaml` | `Connectivity/WiFi` |
| `multimedia-audio.yaml` | `Multimedia/Audio`, the ten playback and ten record configurations |
| `multimedia-audio-minimal.yaml` | `Multimedia/Audio` ALSA-only variants, for minimal images |
| `multimedia-camera.yaml` | `Multimedia/Camera` |
| `multimedia-display.yaml` | `Multimedia/Display` |
| `multimedia-graphics.yaml` | `Multimedia/Graphics`, Wayland clients |
| `multimedia-graphics-x11.yaml` | `Multimedia/Graphics`, X11 clients |
| `multimedia-gstreamer.yaml` | `Multimedia/GSTreamer` |
| `multimedia-video.yaml` | `Multimedia/Video` |
| `multimedia-dsp.yaml` | `Multimedia/CDSP`, `Multimedia/DSP_AudioPD`, `Multimedia/OpenCV`, `Multimedia/Sensors` |
| `performance.yaml` | `Performance`, except Geekbench |
| `performance-geekbench.yaml` | `Performance/Geekbench` |
| `system.yaml` | `System` |
| `virtualization.yaml` | `Virtualization` |

The `pre-merge-*.yaml` test cases stay as they are. They deliberately pick a
small subset across several areas so that a pull request gets a fast answer.

`Kernel/Baseport/Kernel_Selftests`, `Kernel/Baseport/Reboot_health_check`,
`Kernel/Stress/Stressapptest` and `Kernel/Stress/Stress-ng` are not covered:
qcom-linux-testkit ships a `run.sh` but no LAVA test definition for them, so
there is nothing for `path:` to point at.

## Tests that need lab setup

Some entries carry an `include` condition and only end up in the job when the
matching variable is set, because they need something the board cannot provide
on its own:

| Variable | Enables |
| --- | --- |
| `AUDIO_CLIPS_URL` | audio playback (the clip bundle is deployed as a rootfs overlay) |
| `WIFI_SSID_NAME`, `WIFI_SSID_PASSWORD` | `WiFi_Dynamic_IP`, `WiFi_Manual_IP` |
| `BT_TARGET_MAC` | `BT_SCAN_PAIR` |
| `ETH_IPERF_SERVER` | `Ethernet_Throughput_Validation` |
| `ETH_DUAL_INTERFACES` | `Ethernet_Dual_Port_Validation` |
| `ETH_SUSPEND_ENABLE` | `Ethernet_Suspend_Resume_Validation` |
| `NHX_JSON` | `Camera_NHX` |

## Skipping tests per device

A device file under `projects/<project>/devices/` can drop individual tests with
`EXCLUDED_TESTS` (matched against the `name` of an entry in `all_tests`) and
whole test cases with `EXCLUDED_TESTPLANS`.
