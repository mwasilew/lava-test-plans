import os

# Shared LAVA validity command line fragments. Every test module uses these so
# that the whole suite validates against the same, pinned container image.
test_lava_validity = (
    "" if os.getenv("SKIP_TEST_LAVA_VALIDITY") else "--test-lava-validity"
)

test_lava_validity_container = (
    "--test-lava-validity-container %s" % os.getenv("TEST_LAVA_VALIDITY_CONTAINER")
    if os.getenv("TEST_LAVA_VALIDITY_CONTAINER")
    else ""
)
