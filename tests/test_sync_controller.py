#!/usr/bin/env python3
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SYNC_SCRIPT = ROOT / "platform" / "scripts" / "sync-controller.sh"
RELEASE = "v0.1.0-alpha.4"


class ControllerSyncTests(unittest.TestCase):
    def create_repository(self, directory):
        repository = directory / "repository"
        release_notes = (
            repository / "platform" / "releases" / f"{RELEASE}.md"
        )
        skill = (
            repository
            / "platform"
            / "shared-skills"
            / "example"
            / "SKILL.md"
        )
        plugin_manifest = (
            repository
            / "platform"
            / "dashboard-plugins"
            / "aidee-fleet"
            / "dashboard"
            / "manifest.json"
        )
        onboarding_plugin = (
            repository
            / "platform"
            / "hermes-plugins"
            / "aidee-onboarding"
            / "plugin.yaml"
        )
        release_notes.parent.mkdir(parents=True)
        skill.parent.mkdir(parents=True)
        plugin_manifest.parent.mkdir(parents=True)
        onboarding_plugin.parent.mkdir(parents=True)
        release_notes.write_text("# Test release\n")
        skill.write_text("---\nname: example\ndescription: Test skill\n---\n")
        plugin_manifest.write_text("{}\n")
        onboarding_plugin.write_text("name: aidee-onboarding\n")

        commands = [
            ["git", "init", "-b", "main", str(repository)],
            ["git", "-C", str(repository), "config", "user.name", "Aidee Test"],
            [
                "git",
                "-C",
                str(repository),
                "config",
                "user.email",
                "test@example.invalid",
            ],
            ["git", "-C", str(repository), "add", "."],
            ["git", "-C", str(repository), "commit", "-m", "test release"],
            ["git", "-C", str(repository), "tag", RELEASE],
        ]
        for command in commands:
            subprocess.run(command, check=True, capture_output=True)
        return repository

    def run_sync(self, repository, hermes_home, *arguments):
        environment = {
            **os.environ,
            "AIDEE_REPOSITORY": repository.as_uri(),
            "HERMES_HOME": str(hermes_home),
            "HOME": str(hermes_home.parent),
        }
        return subprocess.run(
            ["bash", str(SYNC_SCRIPT), "--release", RELEASE, *arguments],
            env=environment,
            capture_output=True,
            text=True,
        )

    def test_preview_then_approved_apply(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            repository = self.create_repository(directory)
            hermes_home = directory / "home" / ".hermes"

            preview = self.run_sync(
                repository,
                hermes_home,
                "--preview",
            )
            self.assertEqual(preview.returncode, 0, preview.stderr)
            self.assertIn("Preview complete", preview.stdout)
            self.assertFalse(
                (hermes_home / "aidee-upstream" / "SYNCED_RELEASE").exists()
            )

            unapproved = self.run_sync(
                repository,
                hermes_home,
                "--apply",
            )
            self.assertNotEqual(unapproved.returncode, 0)

            legacy_plugin = hermes_home / "plugins/aidee-fleet"
            legacy_plugin.mkdir(parents=True)
            (legacy_plugin / "legacy-marker").write_text("preserved\n")
            applied = self.run_sync(
                repository,
                hermes_home,
                "--apply",
                "--approved",
            )
            self.assertEqual(applied.returncode, 0, applied.stderr)
            self.assertEqual(
                (
                    hermes_home / "aidee-upstream" / "SYNCED_RELEASE"
                ).read_text().strip(),
                RELEASE,
            )
            self.assertTrue(
                (hermes_home / "skills" / "example").is_symlink()
            )
            self.assertTrue(
                (hermes_home / "plugins/aidee-fleet").is_symlink()
            )
            self.assertTrue(
                (hermes_home / "plugins/aidee-onboarding").is_symlink()
            )
            self.assertEqual(
                (
                    hermes_home
                    / "plugins/aidee-fleet.pre-versioned-sync/legacy-marker"
                ).read_text(),
                "preserved\n",
            )

            versioned_plugin = hermes_home / "plugins/aidee-fleet"
            versioned_plugin.unlink()
            shutil.copytree(
                repository / "platform/dashboard-plugins/aidee-fleet",
                versioned_plugin,
            )
            cache = versioned_plugin / "dashboard/__pycache__"
            cache.mkdir()
            (cache / "plugin_api.cpython-test.pyc").write_bytes(b"generated")
            retried = self.run_sync(
                repository,
                hermes_home,
                "--apply",
                "--approved",
            )
            self.assertEqual(retried.returncode, 0, retried.stderr)
            self.assertTrue(versioned_plugin.is_symlink())

    def test_apply_runs_fleet_assistants_sync(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            repository = self.create_repository(directory)
            hermes_home = directory / "home" / ".hermes"

            sync_marker = directory / "fleet_synced.marker"
            tool = (
                repository
                / "platform"
                / "controller-tools"
                / "sync-fleet-assistants.py"
            )
            tool.parent.mkdir(parents=True, exist_ok=True)
            tool.write_text(
                "#!/usr/bin/env python3\n"
                "import sys\n"
                f"open(r'{sync_marker}', 'w').write('synced ' + ' '.join(sys.argv[1:]))\n"
            )
            tool.chmod(0o755)

            subprocess.run(
                ["git", "-C", str(repository), "add", "."], check=True, capture_output=True
            )
            subprocess.run(
                ["git", "-C", str(repository), "commit", "-m", "add sync tool"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(repository), "tag", "-f", RELEASE],
                check=True,
                capture_output=True,
            )

            applied = self.run_sync(
                repository,
                hermes_home,
                "--apply",
                "--approved",
            )
            self.assertEqual(applied.returncode, 0, applied.stderr)
            self.assertTrue(sync_marker.exists())
            self.assertEqual(sync_marker.read_text().strip(), "synced --approved")


if __name__ == "__main__":
    unittest.main()
