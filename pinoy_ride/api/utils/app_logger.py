import logging
import json

def app_logger(log_type, message, array=[]):

    logger = logging.getLogger('myapp')

    # if log_type == 1:
    #     ## Format as template literals
    #     logger.info(f'{message}: {array}')

    # else:
    #     logger.debug(f'{message}: {array}')


    # Create readable line separators for clarity
    line = "=" * 80
    
    # Format message block
    if array is not None and isinstance(array, (dict, list)):
        try:
            formatted_data = json.dumps(array, indent=2, ensure_ascii=False)
        except Exception:
            formatted_data = str(array)
    else:
        formatted_data = str(array) if array else ""

    # Choose log level
    log_func = logger.info if log_type == 1 else logger.debug

    log_func(f"\n{line}\n {message}\n{line}\n{formatted_data}\n{line}\n")

    return