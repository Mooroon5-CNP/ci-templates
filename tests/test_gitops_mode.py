"""Exercise the reusable workflow's publication decisions without cloud writes."""

import ast
import itertools
from pathlib import Path
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = yaml.load(
    (ROOT / ".github/workflows/pipeline.yml").read_text(), Loader=yaml.BaseLoader
)
PROMOTIONS = ("update-config-dev", "update-config-prod", "update-config-aws")


def decision(job, *, mode="pipeline", branch="main", cloud="gcp", scan="success"):
    """Interpret the expression subset used by these job gates, rejecting others."""
    expression = WORKFLOW["jobs"][job]["if"].removeprefix("${{").removesuffix("}}")
    for token, value in {
        "inputs.gitops_mode": mode,
        "github.ref": "refs/heads/" + branch,
        "inputs.target_cloud": cloud,
        "needs.scan-image.result": scan,
    }.items():
        expression = expression.replace(token, repr(value))
    expression = expression.replace("&&", " and ").replace("||", " or ").strip()
    tree = ast.parse(expression, mode="eval")
    allowed = (
        ast.Expression, ast.BoolOp, ast.And, ast.Or,
        ast.Compare, ast.Eq, ast.NotEq, ast.Constant,
    )
    if any(not isinstance(node, allowed) for node in ast.walk(tree)):
        raise AssertionError("Unsupported workflow gate: " + expression)
    return eval(compile(tree, "workflow gate", "eval"), {"__builtins__": {}})


class GitOpsModeTests(unittest.TestCase):
    def test_existing_callers_default_to_pipeline_publication(self):
        setting = WORKFLOW["on"]["workflow_call"]["inputs"]["gitops_mode"]
        self.assertEqual(setting["type"], "string")
        self.assertEqual(setting["required"], "false")
        self.assertEqual(setting["default"], "pipeline")

    def test_portal_or_invalid_mode_never_writes_gitops(self):
        for job, mode, branch, cloud, scan in itertools.product(
            PROMOTIONS, ("portal", "invalid", ""),
            ("main", "prod", "feature"), ("gcp", "aws", "both"),
            ("success", "failure", "cancelled"),
        ):
            with self.subTest(job=job, mode=mode, branch=branch, cloud=cloud, scan=scan):
                self.assertFalse(decision(job, mode=mode, branch=branch, cloud=cloud, scan=scan))

    def test_legacy_promotion_matrix_is_preserved(self):
        for branch, cloud in itertools.product(("main", "prod", "feature"), ("gcp", "aws", "both")):
            expected = {
                "update-config-dev": branch == "main" and cloud != "aws",
                "update-config-prod": branch == "prod" and cloud != "aws",
                "update-config-aws": branch == "main" and cloud != "gcp",
            }
            for job, wanted in expected.items():
                with self.subTest(job=job, branch=branch, cloud=cloud):
                    self.assertEqual(decision(job, branch=branch, cloud=cloud), wanted)

    def test_failed_scan_blocks_legacy_publication(self):
        for job, branch, cloud in itertools.product(PROMOTIONS, ("main", "prod"), ("gcp", "aws", "both")):
            self.assertFalse(decision(job, branch=branch, cloud=cloud, scan="failure"))
            self.assertEqual(WORKFLOW["jobs"][job]["needs"], ["scan-image"])

    def test_portal_mode_retains_build_and_security_checks(self):
        for name in ("lint", "lint-hadolint", "test", "scan-secrets", "scan-deps", "build", "scan-image"):
            self.assertIn(name, WORKFLOW["jobs"])
            self.assertNotIn("gitops_mode", WORKFLOW["jobs"][name].get("if", ""))
        self.assertEqual(set(WORKFLOW["jobs"]["build"]["needs"]), {"scan-secrets", "scan-deps"})
        self.assertEqual(WORKFLOW["jobs"]["scan-image"]["needs"], ["build"])
        scan = "\n".join(step.get("run", "") for step in WORKFLOW["jobs"]["scan-image"]["steps"])
        self.assertIn("--exit-code 1", scan)
        self.assertIn("--severity CRITICAL", scan)

    def test_legacy_prod_gate_is_unchanged(self):
        self.assertEqual(WORKFLOW["jobs"]["update-config-prod"]["environment"], "production")


if __name__ == "__main__":
    unittest.main()
