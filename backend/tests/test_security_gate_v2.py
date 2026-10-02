import unittest

from app.services.security_gate import (
    GateDecision,
    SecurityGatePolicy,
    evaluate_gitleaks,
    evaluate_trivy,
)


def make_scan(*vulnerabilities):
    grouped = {
        "CRITICAL": [],
        "HIGH": [],
        "MEDIUM": [],
        "LOW": [],
        "UNKNOWN": [],
    }

    counts = {}

    for vuln in vulnerabilities:
        severity = vuln["severity"]
        grouped.setdefault(severity, []).append(vuln)
        counts[severity] = counts.get(severity, 0) + 1

    return {
        "severity_count": counts,
        "vulnerabilities": grouped,
    }


def vuln(severity, fixed=False):
    return {
        "id": f"CVE-TEST-{severity}",
        "package": "demo",
        "installed_version": "1.0",
        "fixed_version": "1.1" if fixed else "",
        "fixed": fixed,
        "severity": severity,
    }


class SecurityGateV2Tests(unittest.TestCase):

    def test_clean_scan_is_pass(self):
        result = evaluate_trivy(
            make_scan(),
            SecurityGatePolicy(
                block_on_critical=True,
                block_on_high=True,
            ),
        )

        self.assertEqual(result.decision, GateDecision.PASS)
        self.assertFalse(result.blocking)

    def test_critical_fixable_is_block(self):
        result = evaluate_trivy(
            make_scan(vuln("CRITICAL", fixed=True)),
            SecurityGatePolicy(
                block_on_critical=True,
                block_on_high=True,
            ),
        )

        self.assertEqual(result.decision, GateDecision.BLOCK)
        self.assertTrue(result.blocking)

    def test_critical_non_fixable_is_also_block(self):
        result = evaluate_trivy(
            make_scan(vuln("CRITICAL", fixed=False)),
            SecurityGatePolicy(
                block_on_critical=True,
                block_on_high=True,
            ),
        )

        self.assertEqual(result.decision, GateDecision.BLOCK)
        self.assertTrue(result.blocking)

    def test_high_is_block_when_policy_enabled(self):
        result = evaluate_trivy(
            make_scan(vuln("HIGH", fixed=True)),
            SecurityGatePolicy(
                block_on_critical=True,
                block_on_high=True,
            ),
        )

        self.assertEqual(result.decision, GateDecision.BLOCK)

    def test_high_is_warn_when_policy_disabled(self):
        result = evaluate_trivy(
            make_scan(vuln("HIGH", fixed=True)),
            SecurityGatePolicy(
                block_on_critical=True,
                block_on_high=False,
            ),
        )

        self.assertEqual(result.decision, GateDecision.WARN)
        self.assertFalse(result.blocking)

    def test_gitleaks_detection_is_block(self):
        result = evaluate_gitleaks(1)

        self.assertEqual(result.decision, GateDecision.BLOCK)
        self.assertTrue(result.blocking)

    def test_gitleaks_clean_is_pass(self):
        result = evaluate_gitleaks(0)

        self.assertEqual(result.decision, GateDecision.PASS)
        self.assertFalse(result.blocking)


if __name__ == "__main__":
    unittest.main()



class SecurityGateScannerIntegrationTests(unittest.TestCase):

    def _fake_trivy(self, vulnerabilities):
        import json
        from unittest.mock import MagicMock

        process = MagicMock()
        process.returncode = 0
        process.stderr = ""
        process.stdout = json.dumps({
            "Results": [{
                "Target": "fake:test",
                "Vulnerabilities": vulnerabilities,
            }]
        })

        return process

    def test_scan_high_is_block(self):
        from unittest.mock import patch
        from app.services.scan_service import scan_image

        process = self._fake_trivy([{
            "VulnerabilityID": "CVE-TEST-HIGH",
            "PkgName": "demo",
            "InstalledVersion": "1.0",
            "FixedVersion": "1.1",
            "Severity": "HIGH",
            "Title": "HIGH test",
        }])

        with patch(
            "app.services.scan_service.subprocess.run",
            return_value=process,
        ):
            result = scan_image("fake:test")

        self.assertEqual(result["decision"], "BLOCK")
        self.assertTrue(result["blocking"])
        self.assertEqual(
            len(result["blocking_findings"]),
            1,
        )

    def test_scan_critical_without_fix_is_block(self):
        from unittest.mock import patch
        from app.services.scan_service import scan_image

        process = self._fake_trivy([{
            "VulnerabilityID": "CVE-TEST-CRITICAL",
            "PkgName": "demo",
            "InstalledVersion": "1.0",
            "FixedVersion": "",
            "Severity": "CRITICAL",
            "Title": "CRITICAL no fix",
        }])

        with patch(
            "app.services.scan_service.subprocess.run",
            return_value=process,
        ):
            result = scan_image("fake:test")

        self.assertEqual(result["decision"], "BLOCK")
        self.assertTrue(result["blocking"])

    def test_gitleaks_does_not_store_raw_secret(self):
        import json
        from unittest.mock import MagicMock, patch

        from app.services.scan_service import detect_secret

        fake_secret = "FAKE_SECRET_MUST_NOT_BE_STORED"

        report = [{
            "RuleID": "test-rule",
            "Description": "Secret fictif",
            "File": "config/test.env",
            "StartLine": 1,
            "Secret": fake_secret,
        }]

        def fake_run(cmd, *args, **kwargs):
            report_path = None

            for i, value in enumerate(cmd):
                if value == "--report-path":
                    report_path = cmd[i + 1]
                    break

                if (
                    isinstance(value, str)
                    and value.startswith("--report-path=")
                ):
                    report_path = value.split("=", 1)[1]
                    break

            if not report_path:
                raise RuntimeError(
                    "report-path Gitleaks introuvable"
                )

            with open(
                report_path,
                "w",
                encoding="utf-8",
            ) as handle:
                json.dump(report, handle)

            process = MagicMock()
            process.returncode = 0
            process.stderr = ""
            process.stdout = ""

            return process

        with patch(
            "app.services.scan_service.subprocess.run",
            side_effect=fake_run,
        ):
            result = detect_secret("/tmp/fake-project")

        self.assertEqual(result["decision"], "BLOCK")
        self.assertEqual(result["secret_count"], 1)

        self.assertNotIn(
            "value",
            result["secret_found"],
        )

        self.assertTrue(
            result["secret_found"]["value_redacted"]
        )

        self.assertNotIn(
            fake_secret,
            json.dumps(result),
        )

    def test_clean_gitleaks_is_pass(self):
        import json
        from unittest.mock import MagicMock, patch

        from app.services.scan_service import detect_secret

        def fake_run(cmd, *args, **kwargs):
            report_path = None

            for i, value in enumerate(cmd):
                if value == "--report-path":
                    report_path = cmd[i + 1]
                    break

            if not report_path:
                raise RuntimeError(
                    "report-path Gitleaks introuvable"
                )

            with open(
                report_path,
                "w",
                encoding="utf-8",
            ) as handle:
                json.dump([], handle)

            process = MagicMock()
            process.returncode = 0
            process.stderr = ""
            process.stdout = ""

            return process

        with patch(
            "app.services.scan_service.subprocess.run",
            side_effect=fake_run,
        ):
            result = detect_secret("/tmp/fake-project")

        self.assertEqual(result["decision"], "PASS")
        self.assertFalse(result["blocking"])
        self.assertEqual(result["secret_count"], 0)
        self.assertIsNone(result["secret_found"])
