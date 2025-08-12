import logging

def app_logger(log_type, message, array=[]):

    logger = logging.getLogger('myapp')

    if log_type == 1:
        ## Format as template literals
        logger.info(f'{message}: {array}')

    else:
        logger.debug(f'{message}: {array}')

    return