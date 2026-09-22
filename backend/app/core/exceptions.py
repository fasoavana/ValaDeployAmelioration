class SecretLeakError(Exception):
    pass

class DetectionError(Exception):
    pass

class BuildError(Exception):
    pass

class DeployError(Exception):
    pass

class ContainerNotFoundError(Exception):
    """Levée quand le conteneur Docker n'existe pas (plus)."""
    pass


class VulnerabilityError(Exception):
    def __init__(self, message, vulnerabilities):
        super().__init__(message)
        self.vulnerabilities = vulnerabilities