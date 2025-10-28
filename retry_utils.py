import time
import logging
import functools

def retry_network_operation(max_retries=3, retry_delay=5, allowed_exceptions=None):
    """
    A decorator to retry network operations that might fail temporarily.

    Args:
        max_retries (int): Maximum number of retry attempts
        retry_delay (int): Delay between retries in seconds
        allowed_exceptions (tuple): Exceptions that should trigger a retry

    Returns:
        The decorated function
    """
    if allowed_exceptions is None:
        allowed_exceptions = (Exception,)

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except allowed_exceptions as e:
                    last_exception = e
                    if attempt < max_retries - 1:  # Don't sleep on the last attempt
                        sleep_time = retry_delay * (2 ** attempt)  # Exponential backoff
                        logging.warning(
                            f"Attempt {attempt + 1}/{max_retries} failed: {e}. "
                            f"Retrying in {sleep_time} seconds..."
                        )
                        time.sleep(sleep_time)
                    else:
                        logging.error(f"All {max_retries} attempts failed.")

            # If we get here, all retries have failed
            raise last_exception
        return wrapper
    return decorator
