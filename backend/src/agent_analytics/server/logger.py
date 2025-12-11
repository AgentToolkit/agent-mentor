import logging

def setup_logger():
    # Create logger
    logger = logging.getLogger('agent-analytics')
    logger.setLevel(logging.INFO)
    
    # Adding local handler
    if not logger.handlers:
        # Create console handler and set level
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        
        # Add handler to logger
        logger.addHandler(console_handler)
    
    return logger

# Create and configure logger
logger = setup_logger()