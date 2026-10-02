import unittest

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.models.security_audit import SecurityAuditLog
from app.services.security_audit_service import (
    SecurityAuditService,
)


class SecurityAuditModelTests(unittest.TestCase):

    def test_required_columns_exist(self):

        columns = {
            column.name
            for column
            in SecurityAuditLog.__table__.columns
        }

        required = {
            "id",
            "project_id",
            "component_id",
            "deployment_run_id",
            "user_id",
            "source",
            "decision",
            "reasons",
            "severity_count",
            "finding_count",
            "secret_count",
            "confirmation_outcome",
            "resolved_by_user_id",
            "created_at",
            "resolved_at",
        }

        self.assertTrue(
            required.issubset(columns)
        )


class SecurityAuditServiceTests(unittest.TestCase):

    def test_create_records_decision_and_user(self):

        db = MagicMock()

        db.get.return_value = SimpleNamespace(
            user_id=42
        )

        def refresh(obj):
            obj.id = 99

        db.refresh.side_effect = refresh

        audit = SecurityAuditService.create(
            db=db,
            project_id=10,
            deployment_run_id=20,
            source="trivy",
            decision="BLOCK",
            reasons=[
                "1 vulnérabilité CRITICAL"
            ],
            severity_count={
                "CRITICAL": 1,
                "HIGH": 0,
            },
        )

        self.assertEqual(
            audit.project_id,
            10,
        )

        self.assertEqual(
            audit.deployment_run_id,
            20,
        )

        self.assertEqual(
            audit.user_id,
            42,
        )

        self.assertEqual(
            audit.source,
            "trivy",
        )

        self.assertEqual(
            audit.decision,
            "BLOCK",
        )

        self.assertEqual(
            audit.finding_count,
            1,
        )

        db.add.assert_called_once()
        db.commit.assert_called_once()


    def test_resolve_keeps_audit_and_records_actor(self):

        db = MagicMock()

        audit = SimpleNamespace(
            id=99,
            confirmation_outcome=None,
            resolved_by_user_id=None,
            resolved_at=None,
        )

        db.get.return_value = audit

        result = SecurityAuditService.resolve(
            db=db,
            audit_id=99,
            outcome="confirmed",
            resolved_by_user_id=7,
        )

        self.assertEqual(
            result.confirmation_outcome,
            "confirmed",
        )

        self.assertEqual(
            result.resolved_by_user_id,
            7,
        )

        self.assertIsNotNone(
            result.resolved_at
        )

        self.assertFalse(
            db.delete.called
        )

        db.commit.assert_called_once()


if __name__ == "__main__":
    unittest.main()



class SecurityConfirmationAuditTests(unittest.TestCase):

    def _confirmation(self):
        from app.models.security_confirmation import (
            ConfirmationStatus,
        )

        return SimpleNamespace(
            id=50,
            project_id=10,
            audit_log_id=99,
            status=ConfirmationStatus.PENDING,
            resolved_at=None,
        )

    def test_create_pending_keeps_audit_link(self):
        from app.services.security_confirmation_service import (
            SecurityConfirmationService,
        )

        db = MagicMock()

        confirmation = (
            SecurityConfirmationService.create_pending(
                db=db,
                project_id=10,
                critical_vulnerabilities=[],
                severity_count={"CRITICAL": 1},
                audit_log_id=99,
            )
        )

        self.assertEqual(
            confirmation.audit_log_id,
            99,
        )

        self.assertFalse(
            db.delete.called
        )

    def test_confirm_is_persistent_and_audited(self):
        from unittest.mock import patch

        from app.models.security_confirmation import (
            ConfirmationStatus,
        )
        from app.services.security_confirmation_service import (
            SecurityConfirmationService,
        )

        db = MagicMock()
        confirmation = self._confirmation()

        with patch.object(
            SecurityConfirmationService,
            "get_by_id",
            return_value=confirmation,
        ), patch(
            "app.services.security_confirmation_service."
            "SecurityAuditService.resolve"
        ) as resolve:

            result = (
                SecurityConfirmationService.mark_confirmed(
                    db,
                    50,
                    resolved_by_user_id=7,
                )
            )

        self.assertEqual(
            result.status,
            ConfirmationStatus.CONFIRMED,
        )

        self.assertFalse(
            db.delete.called
        )

        resolve.assert_called_once_with(
            db=db,
            audit_id=99,
            outcome="confirmed",
            resolved_by_user_id=7,
        )

    def test_reject_is_persistent_and_audited(self):
        from unittest.mock import patch

        from app.models.security_confirmation import (
            ConfirmationStatus,
        )
        from app.services.security_confirmation_service import (
            SecurityConfirmationService,
        )

        db = MagicMock()
        confirmation = self._confirmation()

        with patch.object(
            SecurityConfirmationService,
            "get_by_id",
            return_value=confirmation,
        ), patch(
            "app.services.security_confirmation_service."
            "SecurityAuditService.resolve"
        ) as resolve:

            result = (
                SecurityConfirmationService.mark_rejected(
                    db,
                    50,
                    resolved_by_user_id=8,
                )
            )

        self.assertEqual(
            result.status,
            ConfirmationStatus.REJECTED,
        )

        self.assertFalse(
            db.delete.called
        )

        resolve.assert_called_once_with(
            db=db,
            audit_id=99,
            outcome="rejected",
            resolved_by_user_id=8,
        )

    def test_timeout_is_persistent_and_audited(self):
        from unittest.mock import patch

        from app.models.security_confirmation import (
            ConfirmationStatus,
        )
        from app.services.security_confirmation_service import (
            SecurityConfirmationService,
        )

        db = MagicMock()
        confirmation = self._confirmation()

        with patch.object(
            SecurityConfirmationService,
            "get_by_id",
            return_value=confirmation,
        ), patch(
            "app.services.security_confirmation_service."
            "SecurityAuditService.resolve"
        ) as resolve:

            result = (
                SecurityConfirmationService.mark_timeout(
                    db,
                    50,
                )
            )

        self.assertEqual(
            result.status,
            ConfirmationStatus.TIMEOUT,
        )

        self.assertFalse(
            db.delete.called
        )

        resolve.assert_called_once_with(
            db=db,
            audit_id=99,
            outcome="timeout",
            resolved_by_user_id=None,
        )

    def test_cancel_is_persistent_and_audited(self):
        from unittest.mock import patch

        from app.models.security_confirmation import (
            ConfirmationStatus,
        )
        from app.services.security_confirmation_service import (
            SecurityConfirmationService,
        )

        db = MagicMock()
        confirmation = self._confirmation()

        with patch.object(
            SecurityConfirmationService,
            "get_by_id",
            return_value=confirmation,
        ), patch(
            "app.services.security_confirmation_service."
            "SecurityAuditService.resolve"
        ) as resolve:

            result = (
                SecurityConfirmationService.mark_cancelled(
                    db,
                    50,
                )
            )

        self.assertEqual(
            result.status,
            ConfirmationStatus.REJECTED,
        )

        self.assertFalse(
            db.delete.called
        )

        resolve.assert_called_once_with(
            db=db,
            audit_id=99,
            outcome="cancelled",
            resolved_by_user_id=None,
        )
