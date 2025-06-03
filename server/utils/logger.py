import logging
import os

def setup_logger(name, log_file, level=logging.INFO, console_output=True, console_level=logging.INFO):
    """
    Sets up a logger with a file handler and an optional console handler.

    Args:
        name (str): The name of the logger.
        log_file (str): The path to the log file.
        level (int): The minimum level of messages to log to the file (e.g., logging.INFO, logging.DEBUG).
        console_output (bool): Whether to also output logs to the console.
        console_level (int): The minimum level of messages to log to the console.
    """
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Create logs directory if it doesn't exist
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    handler = logging.FileHandler(log_file)
    handler.setFormatter(formatter)
    handler.setLevel(level) # Set level for the file handler

    logger = logging.getLogger(name)
    logger.setLevel(level) # Set overall logger level (should be lowest of all handlers)

    # Ensure no duplicate handlers if function is called multiple times for the same logger name
    if not logger.handlers:
        logger.addHandler(handler)

        if console_output:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            console_handler.setLevel(console_level) # Set level for console output
            logger.addHandler(console_handler)

    return logger

# Example usage (for testing this module directly)
if __name__ == "__main__":
    test_logger = setup_logger('test_logger', 'test.log', level=logging.DEBUG)
    test_logger.debug("This is a debug message.")
    test_logger.info("This is an info message.")
    test_logger.warning("This is a warning message.")
    test_logger.error("This is an error message.")
    test_logger.critical("This is a critical message.")