import unittest
import logging
import sys
import io
from unittest.mock import patch

from libs.py.utils.logger import CliLogger
from libs.py.settings import LOG_LEVEL

class TestCliLogger(unittest.TestCase):

    logger_name = "test_cli_logger"

    def test_logger_initialization(self):
        """
        Test if the CliLogger is initialized correctly.
        """
        logger = CliLogger(self.logger_name)
        logger_instance = logger.logger
        self.assertIsInstance(logger, CliLogger)
        self.assertIsInstance(logger_instance, logging.Logger)
        self.assertEqual(logger_instance.name, self.logger_name)
        self.assertFalse(logger_instance.propagate)
        self.assertEqual(logger_instance.level, logging.INFO)
        
        handler = logger_instance.handlers[0]
        self.assertIsInstance(handler, logging.StreamHandler)
        self.assertIsInstance(handler.formatter, logging.Formatter)

    @patch('sys.stdout', new_callable=io.StringIO)
    def test_debug_logging(self, mock_stdout):
        """
        Test if debug messages are logged and have the correct format.
        """
        logger = CliLogger(self.logger_name)
        logger.logger.setLevel(logging.DEBUG)
        logger.debug("message")
        output = mock_stdout.getvalue()
        # Note: The `asctime` part of the format is variable, so we check for
        # the constant parts of the message.
        self.assertRegex(output, r".* DEBUG message")

    @patch('sys.stdout', new_callable=io.StringIO)
    def test_info_logging(self, mock_stdout):
        """
        Test if info messages are logged correctly.
        """
        logger = CliLogger(self.logger_name)
        logger.info("message")
        output = mock_stdout.getvalue()
        self.assertRegex(output, r".* INFO message")

    @patch('sys.stdout', new_callable=io.StringIO)
    def test_warning_logging(self, mock_stdout):
        """
        Test if warning messages are logged correctly.
        """
        logger = CliLogger(self.logger_name)
        logger.warning("message")
        output = mock_stdout.getvalue()
        self.assertRegex(output, r".* WARNING message")

    @patch('sys.stdout', new_callable=io.StringIO)
    def test_error_logging(self, mock_stdout):
        """
        Test if error messages are logged correctly.
        """
        logger = CliLogger(self.logger_name)
        logger.error("message")
        output = mock_stdout.getvalue()
        self.assertRegex(output, r".* ERROR message")

    @patch('sys.stdout', new_callable=io.StringIO)
    def test_logging_with_extra_kwargs(self, mock_stdout):
        """
        Test that extra keyword arguments are handled correctly (or ignored).
        Your implementation ignores them, so this test ensures that.
        """
        logger = CliLogger(self.logger_name)
        logger.info("Message with extra data.", key="value", another="data")
        output = mock_stdout.getvalue()
        # The message should not contain the extra kwargs
        self.assertIn("INFO Message with extra data.", output)
        self.assertNotIn("key='value'", output)
        self.assertNotIn("another='data'", output)
        
    @patch('sys.stdout', new_callable=io.StringIO)
    def test_log_level_restriction(self, mock_stdout):
        """
        Test that messages below the set log level are not logged.
        """
        logger = CliLogger(self.logger_name)
        logger.debug("This should not be logged.")
        logger.info("This should be logged.")
        
        output = mock_stdout.getvalue()
        
        self.assertNotIn("This should not be logged.", output)
        self.assertIn("This should be logged.", output)


if __name__ == '__main__':
    unittest.main()
