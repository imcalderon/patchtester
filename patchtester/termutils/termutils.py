# termutils.py
"""
Mock implementation of the termutils module.
This replaces the original implementation.
"""

import sys

def AskYesNo(prompt):
    """
    Ask the user a yes/no question.
    
    Args:
        prompt (str): The prompt to display
        
    Returns:
        bool: True if the user answered yes, False otherwise
    """
    while True:
        sys.stdout.write(f"{prompt} [y/n]: ")
        answer = input().lower()
        if answer in ('y', 'yes'):
            return True
        elif answer in ('n', 'no'):
            return False
        else:
            sys.stdout.write("Please respond with 'yes' or 'no' (or 'y' or 'n').\n")
