from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class GateDecision(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    BLOCK = "BLOCK"


@dataclass(frozen=True)
class SecurityGatePolicy:
    """
    Politique de décision du Security Gate v2.

    Les niveaux CRITICAL et HIGH sont configurables conformément
    au cahier des charges.
    """
    block_on_critical: bool = True
    block_on_high: bool = True

    @classmethod
    def from_settings(cls) -> "SecurityGatePolicy":
        from app.core.config import settings

        return cls(
            block_on_critical=settings.BLOCK_ON_CRITICAL,
            block_on_high=settings.BLOCK_ON_HIGH,
        )


@dataclass
class GateResult:
    decision: GateDecision
    reasons: list[str] = field(default_factory=list)
    blocking_findings: list[dict[str, Any]] = field(default_factory=list)
    warning_findings: list[dict[str, Any]] = field(default_factory=list)

    @property
    def blocking(self) -> bool:
        return self.decision == GateDecision.BLOCK

    def to_dict(self) -> dict:
        return {
            "decision": self.decision.value,
            "blocking": self.blocking,
            "reasons": list(self.reasons),
            "blocking_findings": list(self.blocking_findings),
            "warning_findings": list(self.warning_findings),
        }


def evaluate_trivy(
    scan_result: dict,
    policy: SecurityGatePolicy | None = None,
) -> GateResult:
    """
    Transforme les résultats Trivy en décision PASS / WARN / BLOCK.

    Politique actuelle :
    - CRITICAL -> BLOCK si BLOCK_ON_CRITICAL=true, sinon WARN
    - HIGH     -> BLOCK si BLOCK_ON_HIGH=true, sinon WARN
    - aucune CRITICAL/HIGH -> PASS

    Le caractère patchable ou non-patchable n'est volontairement
    pas utilisé pour ignorer une vulnérabilité.
    """
    policy = policy or SecurityGatePolicy.from_settings()

    grouped = scan_result.get("vulnerabilities") or {}

    critical = list(grouped.get("CRITICAL") or [])
    high = list(grouped.get("HIGH") or [])

    blocking_findings: list[dict[str, Any]] = []
    warning_findings: list[dict[str, Any]] = []
    reasons: list[str] = []

    if critical:
        if policy.block_on_critical:
            blocking_findings.extend(critical)
            reasons.append(
                f"{len(critical)} vulnérabilité(s) CRITICAL "
                "détectée(s) : politique BLOCK_ON_CRITICAL=true"
            )
        else:
            warning_findings.extend(critical)
            reasons.append(
                f"{len(critical)} vulnérabilité(s) CRITICAL "
                "détectée(s) : politique BLOCK_ON_CRITICAL=false"
            )

    if high:
        if policy.block_on_high:
            blocking_findings.extend(high)
            reasons.append(
                f"{len(high)} vulnérabilité(s) HIGH "
                "détectée(s) : politique BLOCK_ON_HIGH=true"
            )
        else:
            warning_findings.extend(high)
            reasons.append(
                f"{len(high)} vulnérabilité(s) HIGH "
                "détectée(s) : politique BLOCK_ON_HIGH=false"
            )

    if blocking_findings:
        decision = GateDecision.BLOCK
    elif warning_findings:
        decision = GateDecision.WARN
    else:
        decision = GateDecision.PASS
        reasons.append(
            "Aucune vulnérabilité CRITICAL ou HIGH nécessitant une action."
        )

    return GateResult(
        decision=decision,
        reasons=reasons,
        blocking_findings=blocking_findings,
        warning_findings=warning_findings,
    )


def evaluate_gitleaks(secret_count: int) -> GateResult:
    """
    Toute détection Gitleaks produit une décision BLOCK.

    Cette fonction ne reçoit et ne conserve jamais la valeur brute
    d'un secret.
    """
    count = max(int(secret_count or 0), 0)

    if count > 0:
        return GateResult(
            decision=GateDecision.BLOCK,
            reasons=[
                f"{count} secret(s) détecté(s) par Gitleaks."
            ],
        )

    return GateResult(
        decision=GateDecision.PASS,
        reasons=["Aucun secret détecté par Gitleaks."],
    )
