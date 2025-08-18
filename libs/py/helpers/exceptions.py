class CommandException(BaseException):
    """Exception class for command error handling."""

    def __init__(self, returncode, stderr_output):
        super().__init__(
            f"Command failed with return code {returncode}: {stderr_output}"
        )
        self.returncode = returncode
        self.stderr = stderr_output
