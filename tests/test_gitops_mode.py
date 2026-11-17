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

    def test_image_digest_is_exported_from_the_build_without_changing_publication_gates(self):
        self.assertEqual(WORKFLOW['on']['workflow_call']['outputs']['image_digest']['value'], '${{ jobs.build.outputs.image_digest }}')
        # The digest comes from the build, or from the image already pushed for this commit (re-run).
        self.assertEqual(WORKFLOW['jobs']['build']['outputs']['image_digest'],
                         '${{ steps.image.outputs.digest || steps.existing.outputs.digest }}')
        self.assertEqual(len([step for step in WORKFLOW['jobs']['build']['steps'] if step.get('id') == 'image']), 1)

    def test_a_rerun_reuses_the_pushed_image_instead_of_rebuilding(self):
        # ECR tags are immutable and the failover needs one digest in both registries: a re-run of the
        # same commit must reuse the pushed image, never rebuild it.
        steps = {step.get('id') or step.get('name'): step for step in WORKFLOW['jobs']['build']['steps']}
        self.assertEqual(steps['existing']['if'], "inputs.target_cloud != 'gcp'")
        self.assertIn('describe-images', steps['existing']['run'])
        self.assertIn('ImageNotFoundException', steps['existing']['run'])
        self.assertEqual(steps['image']['if'], "steps.existing.outputs.digest == ''")
        point = steps['Point the Artifact Registry tag to the reused image']
        self.assertIn("inputs.target_cloud != 'aws'", point['if'])
        self.assertEqual(point['env']['EXPECTED'], '${{ steps.existing.outputs.digest }}')
        self.assertIn('${EXPECTED}', point['run'])
        self.assertIn('image_summary.digest', point['run'])
        self.assertIn('--image-tag-mutability IMMUTABLE', steps['ECR login + ensure repo']['run'])

    def test_build_is_serialized_per_commit(self):
        conc = WORKFLOW['jobs']['build']['concurrency']
        self.assertIn('github.sha', conc['group'])
        self.assertIn('inputs.app_name', conc['group'])
        # BaseLoader keeps scalars as strings (see gitops_mode 'required').
        self.assertEqual(conc['cancel-in-progress'], 'false')

    def test_security_tools_are_pinned_by_version_and_digest(self):
        import re
        for name in ('pipeline.yml', 'pipeline-azure.yml'):
            text = (ROOT / ".github" / "workflows" / name).read_text()
            self.assertNotRegex(text, r'(trivy|gitleaks|hadolint):latest')
            for tool in ('aquasec/trivy', 'zricethezav/gitleaks', 'hadolint/hadolint'):
                refs = re.findall(re.escape(tool) + r':[^\s]+', text)
                self.assertTrue(refs, f'{tool} absent de {name}')
                for ref in refs:
                    self.assertRegex(ref, r'@sha256:[a-f0-9]{64}$', f'{ref} non épinglé par empreinte dans {name}')

    def test_legacy_prod_gate_is_unchanged(self):
        self.assertEqual(WORKFLOW["jobs"]["update-config-prod"]["environment"], "production")


if __name__ == "__main__":
    unittest.main()
