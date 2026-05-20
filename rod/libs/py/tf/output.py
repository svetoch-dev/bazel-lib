from copy import deepcopy
from typing import Any

from rod.libs.py.helpers import find_value
from rod.libs.py.utils.logger import BaseLogger, CliLogger


class TfOutputNotFound(Exception):
    """Raised when an expected Terraform output value cannot be found."""

    pass


def tf_output_find(tf_output: dict[str, Any], target_key: str) -> Any | None:
    """
    Find a value by key inside Terraform JSON output.

    Terraform output objects contain top-level metadata fields such as ``type``.
    These fields are removed from a copy of the supplied output before searching
    so callers find values from the actual output payload instead of Terraform's
    metadata.

    Args:
        tf_output: Terraform output parsed from ``terraform output -json``.
        target_key: Nested output key to find.

    Returns:
        The first matching value, or None when the key is not present.
    """
    tf_output_values = deepcopy(tf_output)
    for value in tf_output_values.values():
        value.pop("type", None)

    return find_value(tf_output_values, target_key)


def tf_output_registries(
    tf_output: dict[str, Any], logger: BaseLogger = None
) -> Any | None:
    """
    Extract registry endpoints from Terraform JSON output.

    Args:
        tf_output: Terraform output parsed from ``terraform output -json``.
        logger: Optional logger used by callers for a consistent logging setup.

    Returns:
        A mapping of registry name to endpoint configuration.

    Raises:
        TfOutputNotFound: If the ``registries`` output cannot be found.
    """
    logger = logger or CliLogger("rod.libs.py.tf.output.tf_output_registries")
    registries = tf_output_find(tf_output, "registries")
    if not registries:
        raise TfOutputNotFound("'registries' not found in tf outputs")
    result = {}

    for registry_name, registry_obj in registries.items():
        result[registry_name] = {"endpoint": registry_obj["endpoint"]}

    return result
