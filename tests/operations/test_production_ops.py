from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from infra.production.ops import build_command


class ProductionOperationsTest(unittest.TestCase):
    def test_stop_preserves_named_volumes(self) -> None:
        commands = build_command("stop", project_name="stwi-prod")
        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[0][-1], "down")
        self.assertNotIn("--volumes", commands[0])
        self.assertNotIn("-v", commands[0])

    def test_restore_verification_requires_explicit_approval(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            with self.assertRaisesRegex(ValueError, "explicit --approved"):
                build_command(
                    "restore-verify",
                    project_name="stwi-restore-check",
                    restore_source=source,
                    approved=False,
                )

    def test_rollback_requires_explicit_approval(self) -> None:
        with self.assertRaisesRegex(ValueError, "explicit --approved"):
            build_command(
                "rollback",
                project_name="stwi-prod",
                approved=False,
            )

    def test_migration_requires_explicit_approval(self) -> None:
        with self.assertRaisesRegex(ValueError, "explicit --approved"):
            build_command(
                "migration",
                project_name="stwi-prod",
                approved=False,
            )

    def test_migration_invokes_admin_only_apply_action(self) -> None:
        commands = build_command(
            "migration",
            project_name="stwi-prod",
            approved=True,
        )
        command = commands[0]
        rendered = " ".join(command)
        self.assertIn("stwi.production_migrate apply --approved", rendered)
        self.assertIn("stwi-migrate", command)
        self.assertNotIn("STWI_TSDB_DSN", command)

    def test_backup_commands_are_bounded_and_non_destructive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            commands = build_command(
                "backup",
                project_name="stwi-prod",
                backup_dir=Path(temporary),
            )
        self.assertGreaterEqual(len(commands), 3)
        for command in commands:
            rendered = " ".join(command).lower()
            self.assertNotIn(" rm ", f" {rendered} ")
            self.assertNotIn("down --volumes", rendered)
            self.assertNotIn("down -v", rendered)

    def test_backup_uses_container_database_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            commands = build_command(
                "backup",
                project_name="stwi-prod",
                backup_dir=Path(temporary),
            )
        database_command = " ".join(commands[0])
        self.assertIn("$POSTGRES_USER", database_command)
        self.assertIn("$POSTGRES_DB", database_command)
        self.assertNotIn("--username stwi_admin stwi", database_command)

    def test_project_name_is_allowlisted(self) -> None:
        for project_name in ("STWI", "../stwi", "stwi_prod", "a"):
            with self.subTest(project_name=project_name):
                with self.assertRaisesRegex(ValueError, "project name"):
                    build_command("preflight", project_name=project_name)

    def test_unknown_action_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported action"):
            build_command("delete", project_name="stwi-prod")

    def test_preflight_checks_static_contract_before_compose(self) -> None:
        commands = build_command("preflight", project_name="stwi-prod")
        self.assertIn("validate_production_deployment.py", " ".join(commands[0]))
        self.assertEqual(commands[1][-2:], ["config", "--quiet"])

    def test_restore_uses_distinct_verification_project(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            commands = build_command(
                "restore-verify",
                project_name="stwi-restore-check",
                restore_source=Path(temporary),
                approved=True,
            )
        rendered = " ".join(commands[0])
        self.assertIn("stwi-restore-check", rendered)
        self.assertNotIn("stwi-prod", rendered)


if __name__ == "__main__":
    unittest.main()
