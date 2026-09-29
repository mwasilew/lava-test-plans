# `lava-test-plans` action

Reusable composite GitHub action that renders LAVA test job definitions with
`lava-test-plans` and returns them as a job matrix, ready to be consumed by a
job submission step.

The action lives in the root of this repository, so it is imported directly as
`qualcomm-linux/lava-test-plans@<ref>` and the version of `lava-test-plans` used
for rendering is the one the action is pinned to. No separate checkout of this
repository is required in the calling workflow.

## Usage

```yaml
jobs:
  generate:
    runs-on: ubuntu-latest
    outputs:
      jobmatrix: ${{ steps.testjobs.outputs.jobmatrix }}
    steps:
      - id: testjobs
        uses: qualcomm-linux/lava-test-plans@master
        with:
          machines: rb3gen2-core-kit,qcs9100-ride-sx
          distro_name: qcom-distro-6.16
          build_id: ${{ needs.build.outputs.run_id }}
          gh_token: ${{ secrets.GITHUB_TOKEN }}
          project: meta-qcom
          testplan: qcom-distro/pre-merge
          os_info: qcom-distro
          pr_number: ${{ github.event.pull_request.number }}
          pr_url: ${{ github.event.pull_request.html_url }}

  submit:
    needs: generate
    runs-on: [self-hosted, lava]
    strategy:
      matrix: ${{ fromJson(needs.generate.outputs.jobmatrix) }}
    steps:
      - uses: actions/download-artifact@v6
        with:
          name: ${{ matrix.target.artifact }}
      - run: lavacli jobs submit "${{ matrix.target.path }}"
```

When the build URLs are not published as workflow artifacts, drop
`build_id`/`gh_token` and pass the URL directly instead, together with whatever
the templates need:

```yaml
      - uses: qualcomm-linux/lava-test-plans@master
        with:
          machines: rb3gen2-core-kit
          project: meta-qcom
          testplan: qcom-distro/boot
          build_url: ${{ needs.build.outputs.build_url }}
          os_info: qcom-distro
          variables: |
            IMAGE_FILE_NAME=qcom-multimedia-image-%MACHINE%.rootfs.qcomflash.tar.gz
            ROOTFS_URL=${{ needs.build.outputs.build_url }}/%MACHINE%/qcom-multimedia-image-%MACHINE%.rootfs.qcomflash.tar.gz
```

## Selecting a revision

By default the action installs itself - it lives in the root of this repository, so
`uses: qualcomm-linux/lava-test-plans@<ref>` pins the tool, the projects and the test
plans in one go. This is the recommended way to pin it.

A workflow that has to choose the revision at run time cannot do it through `uses:`,
because `uses:` does not accept expressions. Pass `ref` instead: the action is then
resolved at its own pinned revision, and installs the revision you asked for from git.

```yaml
      - uses: qualcomm-linux/lava-test-plans@v1
        with:
          machines: rb3gen2-core-kit
          ref: ${{ inputs.lava_test_plans_ref }}
```

The tool and the test plans ship in the same package, so `ref` moves both together;
there is no way for them to disagree. Add `repository` to install from a fork. Checking
this repository out in the calling workflow is never necessary.

## Test definitions revision

`testkit_ref` defaults to the [qcom-linux-testkit](https://github.com/qualcomm-linux/qcom-linux-testkit)
tag this revision of the action is tested with, so the `uses:` pin selects the test
definitions as well and calling workflows do not have to carry a testkit tag of their
own. Moving to a newer testkit is a change to that default in `action.yml`. The default
comes from the action itself, not from the revision installed through `ref`. Set
`testkit_ref` only to try a different revision, for example a testkit pull request.

## Build URLs

With `build_id` set, the action downloads the `build-url_<machine>_<distro_name>`
artifacts of that workflow run (authenticated with `gh_token`) and reads
`BUILD_URL` for every machine from the matching file. `dragonboard-410c` and
`dragonboard-820c` read the `qcom-armv8a` file, because both are built from that
machine. A machine without a build URL file is skipped with an error
annotation.

Without `build_id`, the `build_url` input is used for all machines.

## Inputs

| Input | Required | Default | Description |
| --- | --- | --- | --- |
| `machines` | yes | | Comma separated list of machines. One set of jobs is rendered per machine, using `projects/<project>/devices/<machine>` as the device type. |
| `ref` | no | the revision the action was resolved to | Revision of lava-test-plans to render with. Selects the tool and the test plans together. See [Selecting a revision](#selecting-a-revision). |
| `repository` | no | `qualcomm-linux/lava-test-plans` | Repository `ref` is installed from. Only used when `ref` is set. |
| `distro_name` | no | | Name of the distro including kernel suffix. Selects the build URL artifacts and drives the image name, the rootfs URL and the artifact name. |
| `build_id` | no | | ID of the workflow run the build URL artifacts are downloaded from. |
| `gh_token` | no | | Token used to download the build URL artifacts. Required when `build_id` is set. |
| `build_url` | no | | Build URL used for all machines when `build_id` is not set. |
| `kernel` | no | | Kernel suffix appended to the distro name in `BUILD_OS`. |
| `image_type` | no | `qcom-multimedia-image` for `qcom-distro*`, `core-image-base` otherwise | Image type used to build the image and rootfs file names. |
| `project` | no | calling repository name | Project directory used for device overrides and test plans. |
| `testplan` | no | `boot` | Test plan path relative to the project directory, for example `qcom-distro/pre-merge`. |
| `prefix` | no | `testjobs` | Prefix of the artifact name and of the result file names. `distro_name` is appended to both when set. |
| `variables` | no | | Extra `KEY=VALUE` lines appended to the generated variables file. See [Variables](#variables). |
| `variables_files` | no | | Space or newline separated list of existing variable files (ini or yaml). Relative paths are resolved against the workspace. |
| `os_info` | no | | Sets `OS_INFO`, used in the test job name. |
| `lava_job_priority` | no | `50` | Priority of the generated jobs. |
| `test_definitions_repository` | no | `https://github.com/qualcomm-linux/qcom-linux-testkit/` | Repository with the test definitions. |
| `testkit_ref` | no | `testkit-2026.09.27` | Revision of the test definitions repository (tag, branch or commit SHA). See [Test definitions revision](#test-definitions-revision). |
| `pr_number` | no | | Added to the LAVA job metadata as `PR_NUMBER`. |
| `pr_url` | no | | Added to the LAVA job metadata as `PR_URL`. |
| `validity_container` | no | | When set, rendered jobs are validated with the LAVA validator using this container image. Requires docker on the runner. |
| `fail_on_error` | no | `true` | Fail the action when rendering fails or a build URL is missing for any machine. |
| `upload_artifact` | no | `true` | Upload the rendered jobs as a workflow artifact. |
| `python_version` | no | `3.11` | Python version used to install and run `lava-test-plans`. |

## Outputs

| Output | Description |
| --- | --- |
| `jobmatrix` | JSON matrix of the rendered jobs: `{"target": [{"path", "artifact", "result_file", "name"}]}`. `path` is relative to the artifact root, `name` is the machine name. |
| `jobs_path` | Directory with the rendered test jobs. |
| `artifact_id` | ID of the uploaded artifact, empty when nothing was uploaded. |

## Variables

Variables are assembled per machine, in the following order, later values
overwriting earlier ones:

1. files listed in `variables_files`
2. variables set by the action: `PROJECT_NAME`, `PROJECT`, `LAVA_JOB_PRIORITY`,
   `BUILD_NUMBER`, `TEST_DEFINITIONS_REPOSITORY`, `GITHUB_WORKFLOW_URL`,
   `GITHUB_WORKFLOW_RUN_ID`, `GITHUB_WORKFLOW_RUN_ATTEMPT`, `DEVICE_TYPE`,
   `BUILD_URL`, `BUILD_DOWNLOAD_URL` and, when the matching input is set,
   `OS_INFO`, `TEST_DEFINITIONS_REVISION`, `PR_NUMBER`, `PR_URL`
3. variables derived from `distro_name`: `IMAGE_FILE_NAME`, `ROOTFS_URL`,
   `AUTO_LOGIN_PASSWORD_PROMPT` and `AUTO_LOGIN_PASSWORD` for `qcom-distro*`
   builds, plus `ROOTFS_IMG_FILE`, `BOOT_IMG_FILE` and `BUILD_OS` for
   `dragonboard-410c` and `dragonboard-820c`
4. the `variables` input

In the `variables` input the token `%MACHINE%` is replaced with the name of the
machine the jobs are rendered for, which makes it possible to build per machine
image names and URLs from a single input. Since it is applied last, it can also
be used to overwrite any of the variables above.

Anything else the templates need - tags, extra URLs, credentials - is passed
through `variables` or `variables_files`.

## Rendering failures

When the build URL is missing or rendering fails for a machine, the machine is
skipped, an error annotation is emitted and the action fails at the end, after
all remaining machines have been processed. Set `fail_on_error: false` to submit the jobs that were rendered
successfully instead.
