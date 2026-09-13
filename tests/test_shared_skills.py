#!/usr/bin/env python3
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SHARED_SKILLS_DIR = ROOT / "platform" / "shared-skills"


class SharedSkillsTests(unittest.TestCase):
    def test_shared_skills_directory_exists(self):
        self.assertTrue(SHARED_SKILLS_DIR.is_dir())

    def test_all_shared_skills_have_valid_frontmatter_and_content(self):
        skill_dirs = [
            d
            for d in SHARED_SKILLS_DIR.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ]
        self.assertGreater(len(skill_dirs), 0)

        for skill_dir in skill_dirs:
            skill_md = skill_dir / "SKILL.md"
            self.assertTrue(
                skill_md.is_file(),
                f"Missing SKILL.md in {skill_dir.name}",
            )
            content = skill_md.read_text()
            self.assertTrue(
                content.startswith("---"),
                f"{skill_md} must start with YAML frontmatter delimiter '---'",
            )
            parts = content.split("---", 2)
            self.assertGreaterEqual(
                len(parts),
                3,
                f"{skill_md} frontmatter not closed properly with '---'",
            )

            frontmatter = yaml.safe_load(parts[1])
            self.assertIsInstance(
                frontmatter,
                dict,
                f"{skill_md} frontmatter failed to parse as YAML mapping",
            )
            self.assertIn("name", frontmatter)
            self.assertEqual(
                frontmatter["name"],
                skill_dir.name,
                f"Frontmatter name '{frontmatter['name']}' does not match directory '{skill_dir.name}'",
            )
            self.assertIn("description", frontmatter)
            self.assertTrue(
                len(frontmatter["description"].strip()) > 0,
                f"Empty description in {skill_md}",
            )

            body = parts[2].strip()
            self.assertTrue(
                len(body) > 0,
                f"Empty body in {skill_md}",
            )

    def test_matt_pocock_skills_present_and_structured(self):
        expected_skills = {
            "tdd": [
                "Red-Green-Refactor",
                "Phase 1: RED",
                "Phase 2: GREEN",
                "Phase 3: REFACTOR",
                "Boundary",
            ],
            "diagnose": [
                "6-Step Debugging Flow",
                "Reproduce",
                "Minimise",
                "Hypothesise",
                "Instrument",
                "Fix",
                "Regression-test",
            ],
            "grill-me": [
                "Requirements & Architecture Interrogation",
                "Interrogate Scope",
                "Edge Cases",
                "Tradeoffs",
            ],
            "to-prd": [
                "Product Requirement Document Synthesizer",
                "Problem Statement",
                "Goals & Non-Goals",
                "Acceptance Criteria",
            ],
            "improve-architecture": [
                "Anti-Entropy & Refactoring",
                "Separation of Concerns",
                "Single Responsibility",
                "Refactoring Workflow",
            ],
        }

        for skill_name, required_phrases in expected_skills.items():
            skill_path = SHARED_SKILLS_DIR / skill_name / "SKILL.md"
            self.assertTrue(
                skill_path.is_file(),
                f"Expected skill missing: {skill_name}",
            )
            content = skill_path.read_text()
            for phrase in required_phrases:
                self.assertIn(
                    phrase,
                    content,
                    f"Skill '{skill_name}' missing required phrase: '{phrase}'",
                )


if __name__ == "__main__":
    unittest.main()
