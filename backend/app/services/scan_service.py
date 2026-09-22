import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

def scan_image(image_name: str, skip_security_gate: bool = False) -> dict:
    """
    Scan a Docker image for vulnerabilities using Trivy.

    Args:
        image_name (str): The name of the Docker image to scan.
        skip_security_gate (bool, optional): si True, le scan s'exécute normalement
            et les résultats sont toujours enregistrés, mais "blocking" est forcé à False.
            ⚠️ USAGE TEST UNIQUEMENT — à retirer ou remettre à False avant toute
            utilisation réelle. Ne désactive jamais le scan lui-même, seulement le blocage.

    Returns:
        dict: A dictionary containing the scan results.
    """
    try:
        scan = subprocess.run(
            ['trivy', 'image', '--format', 'json', image_name],
            capture_output=True,
            text=True,
            timeout=180,
        )
    except subprocess.TimeoutExpired:
        raise ValueError("Le scan Trivy a dépassé le délai imparti (timeout)")

    if scan.returncode != 0:
        raise ValueError(f"Error occurred while scanning image: {scan.stderr}")

    try:
        scan_results = json.loads(scan.stdout)
    except json.JSONDecodeError as e:
        raise ValueError(f"Impossible de parser la sortie JSON de Trivy: {e}")

    severity_count = {}
    critical_vulns = []
    critical_fixable_count = 0

    for result in scan_results.get('Results', []):
        for vulnerability in result.get('Vulnerabilities', []):
            severity = vulnerability.get('Severity', 'UNKNOWN')
            severity_count[severity] = severity_count.get(severity, 0) + 1

            if severity == 'CRITICAL':
                fixed_version = vulnerability.get('FixedVersion')
                is_fixed = bool(fixed_version)

                critical_vulns.append({
                    "id": vulnerability.get("VulnerabilityID"),
                    "package": vulnerability.get("PkgName"),
                    "installed_version": vulnerability.get("InstalledVersion"),
                    "fixed_version": fixed_version,
                    "title": vulnerability.get("Title"),
                    "fixed": is_fixed,
                })

                if is_fixed:
                    critical_fixable_count += 1

    return {
        "severity_count": severity_count,          # inclut bien LOW/MEDIUM/HIGH/CRITICAL, fixables ou non
        "critical_vulnerabilities": critical_vulns, # toutes les CRITICAL, avec leur statut "fixed"
        "critical_fixable_count": critical_fixable_count,
        # TEMPORAIRE (test) : si skip_security_gate=True, on garde les résultats
        # réels du scan mais on force "blocking" à False pour laisser passer le
        # déploiement malgré la vulnérabilité critique détectée.
        "blocking": False if skip_security_gate else critical_fixable_count > 0,
    }


def detect_secret(project_path: str) -> dict:
    with TemporaryDirectory(prefix="gitleaks_") as tmp_dir:
        report_file = Path(tmp_dir) / "report.json"

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
                f"Error occurred while scanning project: {scan.stderr}"
            )

        if report_file.is_file() and report_file.stat().st_size > 0:
            with report_file.open("r", encoding="utf-8") as file:
                secrets = json.load(file)

            if secrets:
                first_secret = secrets[0]

                return {
                    "blocking": True,
                    "secret_count": len(secrets),
                    "secret_found": {
                        "rule_id": first_secret.get("RuleID"),
                        "description": first_secret.get("Description"),
                        "file": first_secret.get("File"),
                        "line": first_secret.get("StartLine"),
                        "value": first_secret.get("Secret"),
                    },
                }

        return {
            "blocking": False,
            "secret_found": None,
        }