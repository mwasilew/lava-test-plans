# meta-qcom-arduino LAVA test plans

## Brief

Test plans for [meta-qcom-arduino](https://github.com/qualcomm-linux/meta-qcom-arduino),
the Yocto BSP layer for Arduino boards based on Qualcomm SoCs. The layer builds
`core-image-base` for the `nodistro` configuration and `qcom-multimedia-image`
for `qcom-distro`, publishing a `qcomflash` tarball per machine, so every device
here deploys with `to: qdl`.

## Devices

| Yocto MACHINE | LAVA device type | Base device |
|---|---|---|
| `uno-q` | `qrb2210-arduino-imola` | `devices/qrb2210-arduino-imola` |
| `ventuno-q` | `monaco-arduino-monza` | `devices/monaco-arduino-monza` |

The device files are named after the Yocto MACHINE, because the GitHub workflow
passes the machine name as `--device-type projects/meta-qcom-arduino/devices/<machine>`
and derives the artifact names from it. The rendered `device_type:` comes from
the base device's `device_type` block, so the LAVA device type and the machine
name stay decoupled.

Two things differ from the Debian images the base devices were written for:

- the boot prompt is `root@<machine>`, since the image hostname is the Yocto
  MACHINE name rather than the board name;
- `ventuno-q` flashes the `qcs8275-monza` eMMC layout, which spans two eMMC
  physical partitions, so it needs both rawprogram/patch pairs in a single eMMC
  stage rather than the Debian spinor + eMMC split.

## Testing

Render a job without submitting it:

```sh
python3 -m lava_test_plans \
    --variables lava_test_plans/projects/meta-qcom-arduino/variables.ini \
    --device-type projects/meta-qcom-arduino/devices/ventuno-q \
    --test-plan meta-qcom-arduino/nodistro/boot \
    --dry-run
```

Swap `ventuno-q` for `uno-q`, and `nodistro` for `qcom-distro`, to cover the
other combinations. `variables.ini` carries placeholder URLs; point `ROOTFS_URL`
at a real published `qcomflash.tar.gz` to produce a submittable job.
