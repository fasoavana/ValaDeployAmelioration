from dataclasses import dataclass, field, replace


@dataclass(frozen=True)
class SecurityProfile:
    name: str
    mem_limit: str | int | None = None
    nano_cpus: int | None = None
    pids_limit: int | None = None

    cap_drop: tuple[str, ...] = field(default_factory=tuple)
    cap_add: tuple[str, ...] = field(default_factory=tuple)
    security_opt: tuple[str, ...] = field(default_factory=tuple)

    read_only: bool = False
    tmpfs: dict[str, str] | None = None

    def docker_kwargs(self) -> dict:
        kwargs = {}

        if self.mem_limit is not None:
            kwargs["mem_limit"] = self.mem_limit

        if self.nano_cpus is not None:
            kwargs["nano_cpus"] = self.nano_cpus

        if self.pids_limit is not None:
            kwargs["pids_limit"] = self.pids_limit

        if self.cap_drop:
            kwargs["cap_drop"] = list(self.cap_drop)

        if self.cap_add:
            kwargs["cap_add"] = list(self.cap_add)

        if self.security_opt:
            kwargs["security_opt"] = list(self.security_opt)

        if self.read_only:
            kwargs["read_only"] = True

        if self.tmpfs:
            kwargs["tmpfs"] = dict(self.tmpfs)

        return kwargs


# Phase A + B
STANDARD_PROFILE = SecurityProfile(
    name="standard",

    # Limitation des ressources
    mem_limit="512m",
    nano_cpus=1_000_000_000,
    pids_limit=100,

    # Réduction des privilèges
    cap_drop=("ALL",),

    # Ensemble restreint réintroduit pour compatibilité runtime.
    cap_add=(
        "CHOWN",
        "DAC_OVERRIDE",
        "SETUID",
        "SETGID",
    ),

    security_opt=("no-new-privileges:true",),
)


# Phase C : React/Vite + Nginx
REACT_VITE_PROFILE = replace(
    STANDARD_PROFILE,
    name="react-vite",
    read_only=True,
    tmpfs={
        "/var/cache/nginx":
            "rw,nosuid,nodev,noexec,size=64m,uid=101,gid=101,mode=0755",
        "/run":
            "rw,nosuid,nodev,noexec,size=16m,uid=101,gid=101,mode=0755",
        "/tmp": "rw,nosuid,nodev,size=64m,mode=1777",
    },
)


# Phase C : Laravel monolith + Nginx + PHP-FPM
LARAVEL_MONOLITH_PROFILE = replace(
    STANDARD_PROFILE,
    name="laravel-monolith",
    read_only=True,
    tmpfs={
        "/run":
            "rw,nosuid,nodev,noexec,size=16m,uid=10001,gid=10001,mode=0755",
        "/tmp":
            "rw,nosuid,nodev,size=64m,mode=1777",

        # Nginx exécuté avec l'utilisateur valadeploy
        "/var/lib/nginx":
            "rw,nosuid,nodev,noexec,size=64m,uid=10001,gid=10001,mode=0755",
        "/var/log/nginx":
            "rw,nosuid,nodev,noexec,size=16m,uid=10001,gid=10001,mode=0755",

        # Laravel
        "/var/www/html/storage/framework":
            "rw,nosuid,nodev,noexec,size=128m,uid=10001,gid=10001,mode=0775",
        "/var/www/html/storage/logs":
            "rw,nosuid,nodev,noexec,size=64m,uid=10001,gid=10001,mode=0775",
        "/var/www/html/bootstrap/cache":
            "rw,nosuid,nodev,noexec,size=32m,uid=10001,gid=10001,mode=0775",
    },
)


def get_security_profile(project_type):
    """
    Retourne le profil validé pour le runtime détecté.

    Les technologies qui n'ont pas encore été validées en read-only
    conservent STANDARD_PROFILE : elles bénéficient donc déjà des
    Phases A et B sans activation prématurée du read_only.
    """
    type_name = getattr(project_type, "name", str(project_type)).upper()

    if type_name == "REACT_VITE":
        return REACT_VITE_PROFILE

    if type_name == "LARAVEL_MONOLITH":
        return LARAVEL_MONOLITH_PROFILE

    return STANDARD_PROFILE

def get_runtime_port(project_type, configured_port: int) -> int:
    """Retourne le port interne réellement utilisé par le runtime généré."""
    type_name = getattr(project_type, "name", str(project_type)).upper()

    if type_name == "REACT_VITE":
        return 8080

    if type_name in {"LARAVEL", "LARAVEL_MONOLITH"}:
        return 8000

    return configured_port
