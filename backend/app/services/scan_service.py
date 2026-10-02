# app/services/scan_service.py

import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from app.services.security_gate import (
    GateDecision,
    evaluate_gitleaks,
    evaluate_trivy,
)


def scan_image(
    image_name: str,
    skip_security_gate: bool = False,
) -> dict:
    """
    Scan a Docker image for vulnerabilities using Trivy.

    Security Gate v2 :
    - le scan est toujours exécuté ;
    - les résultats Trivy sont conservés ;
    - une décision explicite PASS / WARN / BLOCK est produite ;
    - skip_security_gate ne désactive jamais le scan, il transforme
      uniquement un BLOCK en WARN pour les usages internes prévus.
    """
    try:
        scan = subprocess.run(
            [
                "trivy",
                "image",
                "--format",
                "json",
                image_name,
            ],
            capture_output=True,
            text=True,
            timeout=180,
        )
    except subprocess.TimeoutExpired:
        raise ValueError(
            "Le scan Trivy a dépassé le délai imparti (timeout)"
        )

    if scan.returncode != 0:
        raise ValueError(
            f"Error occurred while scanning image: {scan.stderr}"
        )

    try:
        scan_results = json.loads(scan.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Impossible de parser la sortie JSON de Trivy: {exc}"
        )

    severity_order = [
        "CRITICAL",
        "HIGH",
        "MEDIUM",
        "LOW",
        "UNKNOWN",
    ]

    severity_count = {}
    grouped = {
        severity: []
        for severity in severity_order
    }

    critical_vulns = []
    critical_fixable_count = 0

    for result in scan_results.get("Results", []):
        origin = (
            "system"
            if result.get("Class") == "os-pkgs"
            else "app"
        )

        target = result.get("Target")

        for vulnerability in result.get(
            "Vulnerabilities",
            [],
        ):
            severity = vulnerability.get(
                "Severity",
                "UNKNOWN",
            )

            severity_count[severity] = (
                severity_count.get(severity, 0) + 1
            )

            fixed_version = vulnerability.get(
                "FixedVersion"
            )

            entry = {
                "id": vulnerability.get(
                    "VulnerabilityID"
                ),
                "package": vulnerability.get(
                    "PkgName"
                ),
                "installed_version": vulnerability.get(
                    "InstalledVersion"
                ),
                "fixed_version": fixed_version,
                "title": vulnerability.get("Title"),
                "fixed": bool(fixed_version),
                "severity": severity,
                "origin": origin,
                "target": target,
            }

            grouped.setdefault(
                severity,
                [],
            ).append(entry)

            # Conservé pour compatibilité avec l'interface
            # et les données déjà utilisées par ValaDeploy.
            if severity == "CRITICAL":
                critical_vulns.append(entry)

                if entry["fixed"]:
                    critical_fixable_count += 1

    # Patchables d'abord, puis nom du paquet.
    for vulnerabilities in grouped.values():
        vulnerabilities.sort(
            key=lambda vuln: (
                not vuln["fixed"],
                vuln["package"] or "",
            )
        )

    result = {
        "severity_count": severity_count,
        "vulnerabilities": grouped,
        "critical_vulnerabilities": critical_vulns,
        "critical_fixable_count": (
            critical_fixable_count
        ),
    }

    # ========================================================
    # SECURITY GATE V2
    # ========================================================

    gate_result = evaluate_trivy(result)

    result.update(
        gate_result.to_dict()
    )

    # Compatibilité avec le paramètre historique.
    # Le scan reste effectué et enregistré.
    # Seule la décision BLOCK devient WARN.
    if (
        skip_security_gate
        and result["decision"]
        == GateDecision.BLOCK.value
    ):
        result["decision"] = GateDecision.WARN.value
        result["blocking"] = False

        result["warning_findings"] = [
            *result.get(
                "warning_findings",
                [],
            ),
            *result.get(
                "blocking_findings",
                [],
            ),
        ]

        result["blocking_findings"] = []

        result["reasons"].append(
            "Security Gate ignoré explicitement : "
            "la décision BLOCK est convertie en WARN."
        )

    return result


def detect_secret(project_path: str) -> dict:
    """
    Analyse un dépôt avec Gitleaks.

    Security Gate v2 :
    la valeur brute d'un secret détecté n'est jamais retournée
    ni destinée à être persistée par ValaDeploy.
    """
    with TemporaryDirectory(
        prefix="gitleaks_"
    ) as tmp_dir:
        report_file = (
            Path(tmp_dir) / "report.json"
        )

        cmd = [
            "gitleaks",
            "detect",
            "--source",
            str(project_path),
            "--report-format",
            "json",
            "--report-path",
            str(report_file),
            "--exit-code=0",
        ]

        scan = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )

        if scan.returncode != 0:
            raise ValueError(
                "Error occurred while scanning project: "
                f"{scan.stderr}"
            )

        if (
            report_file.is_file()
            and report_file.stat().st_size > 0
        ):
            with report_file.open(
                "r",
                encoding="utf-8",
            ) as file:
                secrets = json.load(file)

            if secrets:
                first_secret = secrets[0]

                gate_result = evaluate_gitleaks(
                    len(secrets)
                )

                return {
                    **gate_result.to_dict(),
                    "secret_count": len(secrets),

                    # On conserve uniquement les métadonnées
                    # nécessaires pour comprendre et corriger
                    # la détection.
                    "secret_found": {
                        "rule_id": first_secret.get(
                            "RuleID"
                        ),
                        "description": first_secret.get(
                            "Description"
                        ),
                        "file": first_secret.get(
                            "File"
                        ),
                        "line": first_secret.get(
                            "StartLine"
                        ),

                        # La valeur réelle n'est volontairement
                        # ni retournée ni persistée.
                        "value_redacted": True,
                    },
                }

        gate_result = evaluate_gitleaks(0)

        return {
            **gate_result.to_dict(),
            "secret_count": 0,
            "secret_found": None,
        }
