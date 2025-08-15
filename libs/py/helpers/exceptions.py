class CommandException(BaseException):
    """A mock exception class to test error handling."""

    def __init__(self, returncode, stderr_output):
        super().__init__(
            f"Command failed with return code {returncode}: {stderr_output}"
        )
        self.returncode = returncode
        self.stderr = stderr_output
