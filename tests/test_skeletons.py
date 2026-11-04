"""Structure and contract tests for skeletons/ (run by the repo's own CI).

These are fast static checks. The full lint/test/build/run/scan of each
skeleton is skeletons/verify.py (needs Docker).
"""

import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SKELETONS = ROOT / "skeletons"
PIPELINE = ROOT / ".github" / "workflows" / "pipeline.yml"
LANGS = ["node", "python", "go", "java", "cpp", "fullstack"]

# Same marker files as detect_lang() in pipeline.yml, per skeleton layout.
MARKERS = {
    "node": ["package.json"], "python": ["requirements.txt"], "go": ["go.mod"],
    "java": ["pom.xml"], "cpp": ["CMakeLists.txt"],
    "fullstack": ["web/package.json", "api/requirements.txt"],
}
ALLOWED_TOKENS = {"{{APP_NAME}}", "{{APP_PORT}}"}
SECRET_PATTERNS = [
    r"AKIA[0-9A-Z]{16}", r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----",
    r"gh[pousr]_[A-Za-z0-9]{30,}", r"AIza[0-9A-Za-z_\-]{35}", r"xox[baprs]-[0-9A-Za-z-]{10,}",
]
SKIP_DIRS = {"node_modules", "target", "build", "dist", "__pycache__"}


def files(lang):
    base = SKELETONS / lang
    return [p for p in base.rglob("*") if p.is_file() and not (SKIP_DIRS & set(p.relative_to(base).parts))]


def text(path):
    return path.read_text(encoding="utf-8")


class SkeletonLayout(unittest.TestCase):
    def test_every_language_has_a_skeleton_and_nothing_else_is_unlisted(self):
        present = sorted(p.name for p in SKELETONS.iterdir() if p.is_dir() and p.name != "_common")
        self.assertEqual(present, sorted(LANGS))

    def test_common_readme_carries_the_platform_contract(self):
        readme = text(SKELETONS / "_common" / "README.md")
        for needle in ("{{APP_NAME}}", "{{APP_PORT}}", "/healthz", "/ready", "`main`", "`prod`", "ci.yml"):
            self.assertIn(needle, readme)

    def test_documented_tokens_are_the_only_ones_used(self):
        for lang in LANGS + ["_common"]:
            for path in files(lang):
                for token in re.findall(r"\{\{[^}]*\}\}", text(path)):
                    self.assertIn(token, ALLOWED_TOKENS, f"{path.relative_to(ROOT)}: unsupported token {token}")

    def test_no_example_name_leaked_from_test_apps(self):
        for lang in LANGS:
            for path in files(lang):
                self.assertNotIn("cnp-test-", text(path), f"{path.relative_to(ROOT)} still contains cnp-test-*")

    def test_no_workflow_is_shipped_ci_yml_comes_from_the_portal_onboarding(self):
        for lang in LANGS + ["_common"]:
            self.assertFalse((SKELETONS / lang / ".github").exists(), f"{lang}/.github must not exist")

    def test_no_secret_in_any_skeleton(self):
        for lang in LANGS + ["_common"]:
            for path in files(lang):
                if path.name == "package-lock.json":
                    continue
                content = text(path)
                for pattern in SECRET_PATTERNS:
                    self.assertIsNone(re.search(pattern, content), f"{path.relative_to(ROOT)} matches {pattern}")

    def test_no_build_artifact_committed(self):
        for lang in LANGS:
            for part in (SKELETONS / lang).rglob("*"):
                self.assertNotIn(part.name, {"node_modules", "target", "__pycache__", ".env"}, str(part))


class SkeletonContract(unittest.TestCase):
    def test_marker_files_match_what_detect_stack_looks_for(self):
        detect = text(PIPELINE)
        for lang, markers in MARKERS.items():
            for marker in markers:
                self.assertTrue((SKELETONS / lang / marker).is_file(), f"{lang}: missing {marker}")
                self.assertIn(Path(marker).name, detect, f"pipeline.yml no longer detects {marker}")

    def test_fullstack_parts_are_top_level_directories_only(self):
        self.assertFalse((SKELETONS / "fullstack" / "package.json").exists())
        for part in ("web", "api"):
            self.assertTrue((SKELETONS / "fullstack" / part).is_dir())

    def test_node_skeletons_ship_their_lockfile_because_the_ci_requires_it(self):
        self.assertTrue((SKELETONS / "node" / "package-lock.json").is_file())
        self.assertTrue((SKELETONS / "fullstack" / "web" / "package-lock.json").is_file())

    def test_every_dockerfile_follows_the_platform_rules(self):
        for lang in LANGS:
            docker = text(SKELETONS / lang / "Dockerfile")
            self.assertRegex(docker, r"(?m)^USER 1000$", f"{lang}: must run as non-root")
            self.assertRegex(docker, r"(?m)^EXPOSE \{\{APP_PORT\}\}$", f"{lang}: EXPOSE must use the portal port")
            self.assertIn("ENV PORT={{APP_PORT}}", docker, f"{lang}: PORT must match the portal port")
            self.assertRegex(docker, r'(?m)^HEALTHCHECK .*CMD \[', f"{lang}: HEALTHCHECK must be JSON form (hadolint DL3025)")
            self.assertIn("/healthz", docker)
            self.assertNotRegex(docker, r"(?m)^FROM .*:latest", f"{lang}: base image must be pinned")

    def test_apps_answer_healthz_and_ready(self):
        sources = {
            "node": "src/app.js", "python": "app.py", "go": "main.go",
            "java": "src/main/java/cnp/test/App.java", "cpp": "src/routes.cpp", "fullstack": "api/server.py",
        }
        for lang, source in sources.items():
            code = text(SKELETONS / lang / source)
            self.assertIn("/healthz", code, f"{lang}: no /healthz")
            self.assertIn("/ready", code, f"{lang}: no /ready")

    def test_every_skeleton_ships_a_test_and_a_lint_or_compile_step(self):
        expect = {
            "node": ["test/app.test.js", ".eslintrc.json"], "python": ["tests/test_app.py", ".flake8"],
            "go": ["main_test.go"], "java": ["src/test/java/cnp/test/AppTest.java"],
            "cpp": ["tests/routes_test.cpp"], "fullstack": ["api/tests/test_server.py", "web/test/render.test.js", "web/.eslintrc.json", "api/.flake8"],
        }
        for lang, paths in expect.items():
            for rel in paths:
                self.assertTrue((SKELETONS / lang / rel).is_file(), f"{lang}: missing {rel}")


class VerifyScriptStaysInSyncWithPipeline(unittest.TestCase):
    def test_commands_run_by_verify_py_are_still_in_pipeline_yml(self):
        pipeline = " ".join(text(PIPELINE).split())
        for needle in ("npm run lint", "flake8 .", "go vet ./...", "go test ./...", "mvn -q -B compile",
                       "mvn -q -B test", "cppcheck --error-exitcode=1 --quiet .", "cmake -B build",
                       "ctest --test-dir build --output-on-failure", "pytest", "hadolint/hadolint:v2.14.0-alpine"):
            self.assertIn(needle, pipeline, f"verify.py mirrors a command no longer in pipeline.yml: {needle}")

    def test_pipeline_is_valid_yaml_with_a_detect_script(self):
        jobs = yaml.safe_load(text(PIPELINE))["jobs"]
        self.assertTrue(any(s.get("id") == "detect" for s in jobs["detect-stack"]["steps"]))


if __name__ == "__main__":
    unittest.main()
