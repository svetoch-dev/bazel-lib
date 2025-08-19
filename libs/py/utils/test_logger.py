import unittest
import logging
import sys
import io
import json

from tiny_json_log import JSONFormatter
from libs.py.utils.logger import CliLogger, JsonLogger, RootLogger
from libs.py.settings import LOG_LEVEL


class LoggerMixin:
    logger_name = "test_logger"
    handler = None
    formatter = None
    logger_type = None

    def setLogger(self):
        raise NotImplementedError("setLogger is not implemented")

    def getRecord(self):
        raise NotImplementedError("getRecord is not implemented")

    def debug(self):
        self.logger.logger.setLevel(logging.DEBUG)
        self.logger.debug("message")
        return self.getRecord()

    def info(self):
        self.logger.info("message")
        return self.getRecord()

    def warning(self):
        self.logger.warning("message")
        return self.getRecord()

    def error(self):
        self.logger.error("message")
        return self.getRecord()

    def extra_kwargs(self):
        self.logger.info("Message with extra data.", key="value", another="data")
        return self.getRecord()

    def level_restrictions(self):
        self.logger.debug("This should not be logged.")
        self.logger.info("This should be logged.")
        return self.getRecord()

    def logger_initialization(self, propagate=False):
        logger_instance = self.logger.logger
        self.assertIsInstance(self.logger, self.logger_type)
        self.assertIsInstance(logger_instance, logging.Logger)
        self.assertEqual(logger_instance.name, self.logger_name)
        self.assertEqual(logger_instance.propagate, propagate)
        self.assertEqual(logger_instance.level, logging.INFO)

        handler = logger_instance.handlers[0]
        self.assertIsInstance(handler, self.handler)
        self.assertIsInstance(handler.formatter, self.formatter)


class StreamLoggerMixin(LoggerMixin):
    handler = logging.StreamHandler
    logger_type = None

    def getRecord(self):
        return self.mock_stdout.getvalue()

    def setUp(self):
        """
        This method is called before each test.
        It sets up a StringIO object to capture stderr,stdout logger instance.
        """
        self.mock_stderr = io.StringIO()
        self.mock_stdout = io.StringIO()
        sys.stderr = self.mock_stderr
        sys.stdout = self.mock_stdout

        self.setLogger()

    def tearDown(self):
        """
        This method is called after each test.
        It restores the original stderr, stdout.
        """
        self.mock_stderr.close()
        self.mock_stdout.close()
        sys.stderr = sys.__stderr__
        sys.stdout = sys.__stdout__


class TestStreamCliLogger(StreamLoggerMixin, unittest.TestCase):
    logger_name = "test_stream_cli_logger"
    formatter = logging.Formatter
    logger_type = CliLogger

    def setLogger(self):
        self.logger = CliLogger(self.logger_name)

    def test_logger_initialization(self):
        """
        Test if the Logger is initialized correctly.
        """
        self.logger_initialization()

    def test_debug_logging(self):
        """
        Test if debug messages are logged and have the correct format.
        """

        output = self.debug()
        # Note: The `asctime` part of the format is variable, so we check for
        # the constant parts of the message.
        self.assertRegex(output, r".* DEBUG message")

    def test_info_logging(self):
        """
        Test if info messages are logged correctly.
        """
        output = self.info()
        self.assertRegex(output, r".* INFO message")

    def test_warning_logging(self):
        """
        Test if warning messages are logged correctly.
        """
        output = self.warning()
        self.assertRegex(output, r".* WARNING message")

    def test_error_logging(self):
        """
        Test if error messages are logged correctly.
        """
        output = self.error()
        self.assertRegex(output, r".* ERROR message")

    def test_logging_with_extra_kwargs(self):
        """
        Test that extra keyword arguments are handled correctly (or ignored).
        """
        output = self.extra_kwargs()
        # The message should not contain the extra kwargs
        self.assertIn("INFO Message with extra data.", output)
        self.assertNotIn("key='value'", output)
        self.assertNotIn("another='data'", output)

    def test_log_level_restriction(self):
        """
        Test that messages below the set log level are not logged.
        """
        output = self.level_restrictions()

        self.assertNotIn("This should not be logged.", output)
        self.assertIn("This should be logged.", output)


class TestStreamJsonLogger(StreamLoggerMixin, unittest.TestCase):
    logger_name = "test_stream_json_logger"
    formatter = JSONFormatter
    logger_type = JsonLogger

    def setLogger(self):
        self.logger = JsonLogger(self.logger_name)

    def test_logger_initialization(self):
        """
        Test if the Logger is initialized correctly.
        """
        self.logger_initialization()

    def test_debug_logging(self):
        """
        Test if debug messages are logged and have the correct format.
        """

        output = json.loads(self.debug())
        self.assertEqual(output["severity"], "DEBUG")
        self.assertEqual(output["src"], self.logger_name)
        self.assertEqual("message", output["message"])

    def test_info_logging(self):
        """
        Test if info messages are logged correctly.
        """
        output = json.loads(self.info())
        self.assertEqual(output["severity"], "INFO")
        self.assertEqual(output["src"], self.logger_name)
        self.assertEqual("message", output["message"])

    def test_warning_logging(self):
        """
        Test if warning messages are logged correctly.
        """
        output = json.loads(self.warning())
        self.assertEqual(output["severity"], "WARNING")
        self.assertEqual(output["src"], self.logger_name)
        self.assertEqual("message", output["message"])

    def test_error_logging(self):
        """
        Test if error messages are logged correctly.
        """
        output = json.loads(self.error())
        self.assertEqual(output["severity"], "ERROR")
        self.assertEqual(output["src"], self.logger_name)
        self.assertEqual("message", output["message"])

    def test_logging_with_extra_kwargs(self):
        """
        Test that extra keyword arguments are handled correctly (or ignored).
        """
        output = json.loads(self.extra_kwargs())
        # The message should contain the extra kwargs
        self.assertEqual("value", output["key"])
        self.assertEqual("data", output["another"])

    def test_log_level_restriction(self):
        """
        Test that messages below the set log level are not logged.
        """
        output = json.loads(self.level_restrictions())

        self.assertNotEqual("This should not be logged.", output["message"])
        self.assertEqual("This should be logged.", output["message"])


class TestRootStreamLogger(TestStreamJsonLogger):
    logger_name = "root"
    logger_type = RootLogger

    def setLogger(self):
        self.logger = RootLogger()
        self.none_root_logger = logging.getLogger("test_root_stream_logger")

    def test_logger_initialization(self):
        """
        Test if the Logger is initialized correctly.
        """
        self.logger_initialization(propagate=True)
        self.none_root_logger.info("message")

    def test_none_root_logger(self):
        """
        Test that logs are logged in proper format for none root loggers
        """
        self.none_root_logger.info("message")
        output = json.loads(self.mock_stdout.getvalue())
        self.assertEqual(output["severity"], "INFO")
        self.assertEqual(output["src"], "test_root_stream_logger")
        self.assertEqual("message", output["message"])

    def test_logging_with_extra_kwargs(self):
        """
        Test that extra keyword arguments are handled correctly (or ignored).
        """
        output = json.loads(self.extra_kwargs())
        # The message should not contain the extra kwargs
        self.assertFalse("key" in output.keys())
        self.assertFalse("another" in output.keys())


if __name__ == "__main__":
    unittest.main()
