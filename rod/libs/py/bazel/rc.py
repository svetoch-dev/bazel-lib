from dataclasses import make_dataclass, fields
from pathlib import Path
from rod.libs.py.utils.logger import CliLogger, BaseLogger
import shlex


def bazelrc_str_to_obj(rc_string: str) -> object:
    """
    Convert a bazelrc command line string into an object.

    Option names with a ``--`` prefix are stored with an ``o_`` field prefix.
    Options may be written as ``--name value`` or ``--name=value``. Bare command
    names are stored as boolean fields set to True. ``try-import`` entries store
    the imported path as a value.

    Args:
        rc_string: Bazelrc command line string to parse.

    Returns:
        A dataclass instance containing parsed bazelrc fields.
    """
    tokens = shlex.split(rc_string)
    properties = {}

    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.startswith("--"):
            token = token[2:]
            if "=" in token:
                name, value = token.split("=", 1)
                property_name = "o_" + name
                property_value = value
                i += 1
            else:
                property_name = "o_" + token
                property_value = tokens[i + 1]
                i += 2

            properties[property_name] = property_value
        elif token == "try-import":
            property_name = token.replace("-", "_")
            properties[property_name] = tokens[i + 1]
            i += 2
        else:
            property_name = token.replace("-", "_")
            properties[property_name] = True
            i += 1

    BazelRc = make_dataclass(
        "BazelRc",
        [
            (property_name, type(property_value))
            for property_name, property_value in properties.items()
        ],
    )

    return BazelRc(**properties)


def bazelrc_obj_to_str(obj: object) -> str:
    """
    Convert a parsed bazelrc object back into a command line string.

    Fields with an ``o_`` prefix are written as ``--`` options. The
    ``try_import`` field is written as ``try-import`` followed by its value.
    Boolean fields set to True are written as bare command names.

    Args:
        obj: Object containing bazelrc fields.

    Returns:
        Shell-quoted bazelrc command line string.
    """
    parts = []

    for field in fields(obj):
        name = field.name
        value = getattr(obj, name)

        if name.startswith("o_"):
            option_name = "--" + name[2:]
            parts.extend([option_name, str(value)])
        elif name == "try_import":
            parts.extend(["try-import", str(value)])
        elif value == True:
            parts.append(name)

    return " ".join(shlex.quote(part) for part in parts)


def bazelrc_parse(
    file: str,
    logger: BaseLogger = CliLogger("rod.libs.py.bazel.rc.bazelrc_parse"),
) -> list[object]:
    """
    Parse a bazelrc file into a list of objects.

    Each non-empty line in the file is parsed as a separate bazelrc command
    line entry. Inline comments starting with ``#`` are ignored.

    Args:
        file: Path to the bazelrc file to parse.
        logger: Logger used to print status messages.

    Returns:
        A list of parsed bazelrc objects.
    """

    bazelrc_objects = []
    file_obj = Path(file)
    if not file_obj.exists():
        logger.error(f"bazelrc file - {file} does not exist")
        return

    with file_obj.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.split("#")[0].strip()
            if line:
                bazelrc_objects.append(bazelrc_str_to_obj(line))

    return bazelrc_objects


def bazelrc_create(
    file: str,
    bazelrc_objects: list[object],
    logger: BaseLogger = CliLogger("rod.libs.py.bazel.rc.bazelrc_parse"),
) -> bool:
    """
    Create a bazelrc file from parsed bazelrc objects.

    Each object is converted to a command line string and written as one line in
    the output file. If file creation fails, logs the error and returns False.

    Args:
        file: Path to the bazelrc file to create.
        bazelrc_objects: Parsed bazelrc objects to write.
        logger: Logger used to print status messages.

    Returns:
        True if the bazelrc file was created successfully, False otherwise.
    """

    try:
        file_obj = Path(file)

        with file_obj.open("w", encoding="utf-8") as f:
            for obj in bazelrc_objects:
                f.write(bazelrc_obj_to_str(obj) + "\n")
    except Exception as e:
        logger.error(f"Error occured while creating {file}. {e}")
        return False

    logger.info(f"bazelrc file {file} created successfully")
    return True
