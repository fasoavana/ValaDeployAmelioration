"""Validation syntaxique partagée des références d'images, sans appel Docker."""
import ipaddress
import re

_COMPONENT = r"[a-z0-9]+(?:(?:[._]|__|-+)[a-z0-9]+)*"
_PATH = re.compile(rf"{_COMPONENT}(?:/{_COMPONENT})*")
_TAG = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}")
_HOST = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)*")


def validate_image_reference(value: str) -> str:
    message = ("Référence d'image Docker invalide. Utilisez un nom de dépôt en "
               "minuscules, sans espace, par exemple postgres:15-alpine "
               "ou registry.example.com:5000/equipe/application:v1.")
    if not isinstance(value, str) or not value or re.search(r"\s", value):
        raise ValueError(message)
    name, sep, digest = value.partition("@")
    if sep:
        algorithm, colon, encoded = digest.partition(":")
        lengths = {"sha256": 64, "sha384": 96, "sha512": 128}
        if not colon or algorithm not in lengths or not re.fullmatch(r"[a-fA-F0-9]+", encoded) or len(encoded) != lengths[algorithm]:
            raise ValueError(message)
    # Un ':' après le dernier '/' est un tag (le port du registre est avant).
    if name.rfind(":") > name.rfind("/"):
        name, tag = name.rsplit(":", 1)
        if not _TAG.fullmatch(tag):
            raise ValueError(message)
    if len(name) > 255:
        raise ValueError(message)
    path = name
    if "/" in name:
        first, rest = name.split("/", 1)
        if "." in first or ":" in first or first == "localhost" or first != first.lower():
            host = first
            if host.startswith("["):
                end = host.find("]")
                try:
                    ipaddress.IPv6Address(host[1:end])
                except ValueError:
                    raise ValueError(message) from None
                port = host[end + 1:]
                if port and not re.fullmatch(r":[0-9]+", port):
                    raise ValueError(message)
            else:
                host, colon, port = host.partition(":")
                if not _HOST.fullmatch(host) or (colon and not re.fullmatch(r"[0-9]+", port)):
                    raise ValueError(message)
            path = rest
    if not _PATH.fullmatch(path):
        raise ValueError(message)
    return value
