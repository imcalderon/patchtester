# buildInfo/releaseInfo.py
"""
Mock implementation of the releaseInfo module from buildInfo.
This replaces the original implementation.
"""

class ReleaseInfo:
    """
    Represents information about a software release.
    """
    def __init__(self, version, release_name, stream_prefix):
        self.version = version
        self.release_name = release_name
        self.stream_prefix = stream_prefix


class ReleaseInfoCollection:
    """
    Collection of release information.
    """
    def __init__(self):
        # Define some mock releases
        self._releases = {
            "dev": ReleaseInfo("development", "Development Branch", "//depot/streams/dev"),
            "main": ReleaseInfo("main", "Main Branch", "//depot/streams/main"),
            "beta": ReleaseInfo("beta", "Beta Branch", "//depot/streams/beta"),
            "stable": ReleaseInfo("stable", "Stable Branch", "//depot/streams/stable"),
            "v1.0": ReleaseInfo("1.0", "Version 1.0", "//depot/streams/v1.0"),
            "v2.0": ReleaseInfo("2.0", "Version 2.0", "//depot/streams/v2.0")
        }
    
    def GetReleaseByName(self, name):
        """
        Get release information by name.
        
        Args:
            name (str): The name of the release
            
        Returns:
            ReleaseInfo: The release information, or None if not found
        """
        return self._releases.get(name)

