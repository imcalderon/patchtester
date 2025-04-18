# jirautils/patch_request.py
"""
Mock implementation of the patch_request module from jirautils.
This replaces the original Pixar-specific implementation.
"""

class PatchRequest:
    """
    Represents a patch request from a ticket system.
    """
    def __init__(self, id, changes=None):
        self.id = id
        self.changes = changes or []


class PatchRequestError(Exception):
    """Exception raised for errors in patch requests."""
    pass


def getVersionPatch(request_id):
    """
    Get a specific patch request by ID.
    
    Args:
        request_id (str): The ID of the patch request
        
    Returns:
        PatchRequest: The patch request object
        
    Raises:
        PatchRequestError: If the request cannot be found
    """
    # Implement a mock version here
    # In a real implementation, this would query a ticket system
    if not request_id or not isinstance(request_id, str):
        raise PatchRequestError(f"Invalid request ID: {request_id}")
    
    # Mock implementation returns a dummy patch request
    return PatchRequest(request_id, ["12345", "67890"])


def getPendingVersionPatches(target_name):
    """
    Get all pending patch requests for a specific target.
    
    Args:
        target_name (str): The name of the target branch
        
    Returns:
        list: List of PatchRequest objects
    """
    # Mock implementation returns a list of dummy patch requests
    return [
        PatchRequest("PATCH-001", ["12345"]),
        PatchRequest("PATCH-002", ["67890"]),
        PatchRequest("PATCH-003", [])  # A pending request with no changes
    ]


def getAcceptedVersionPatches(target_name):
    """
    Get all accepted patch requests for a specific target.
    
    Args:
        target_name (str): The name of the target branch
        
    Returns:
        list: List of PatchRequest objects
    """
    # Mock implementation returns a list of dummy patch requests
    return [
        PatchRequest("PATCH-101", ["12345", "23456"]),
        PatchRequest("PATCH-102", ["34567"]),
        PatchRequest("PATCH-103", ["45678", "56789"])
    ]
