"""
Prompt improver plugin — generates LLM recommendations and rewrites system prompts.

For top-N ranked nodes, loads original system prompts, analyzes decision tree
results to generate improvement recommendations, and rewrites prompts
incorporating those recommendations.

The user specifies which label represents "success" (good cluster) via the
success_label config. This is used in the LLM prompts so the model knows
which behavior to reinforce and which to prevent.

Ported from:
- agentops/experiment_pipeline.py lines 632-851 (prompt generation)
"""

import ast as ast_module
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from analytics.base_plugin import AnalyticsPlugin
from .prompt import (
    RECOMMENDATION_SYSTEM_PROMPT,
    RECOMMENDATION_USER_TEMPLATE,
    RECOMMENDATION_SCHEMA,
    PROMPT_REWRITE_SYSTEM_PROMPT,
    PROMPT_REWRITE_USER_TEMPLATE,
)


class PromptImproverPlugin(AnalyticsPlugin):

    def __init__(self):
        self.prompts_dir = ""
        self.top_n = 3
        self.success_label = 1
        self.success_label_name = "SUCCESS"
        self.failure_label_name = "FAILURE"
        self.apply_to_disk = False  # Write improved prompts back to original files
        self._codebase_path = ""
        self._source_info: Dict[str, Dict] = {}  # node_name → Python source info cache

    @property
    def name(self) -> str:
        return "prompt_improver"

    @property
    def description(self) -> str:
        return (
            "Generates LLM-based recommendations and improved system prompts "
            "for top-ranked agent nodes based on decision tree analysis"
        )

    def configure(self, config: Dict[str, Any]):
        self.prompts_dir = config.get("prompts_dir", self.prompts_dir)
        self.top_n = config.get("top_n", self.top_n)
        self.success_label = config.get("success_label", self.success_label)
        self.success_label_name = config.get("success_label_name", self.success_label_name)
        self.failure_label_name = config.get("failure_label_name", self.failure_label_name)
        self.apply_to_disk = config.get("apply_to_disk", self.apply_to_disk)

    async def execute(self, state: "ApplicationState") -> Dict[str, Any]:
        self._codebase_path = getattr(state, "codebase_path", "")

        # Register artifact kinds for experiment pipeline
        from analytics.plugins.trace_analyzer.models import ExperimentArtifact
        state._data_manager.register_artifact_kind("node_ranking", ExperimentArtifact)
        state._data_manager.register_artifact_kind("feature_table", ExperimentArtifact)
        state._data_manager.register_artifact_kind("recommendation", ExperimentArtifact)

        # Load node ranking
        ranking_result = await state.artifacts().kind("node_ranking").get()
        ranking_list = ranking_result.to_list() if ranking_result else []

        if not ranking_list:
            return {
                "status": "skipped",
                "message": "No node_ranking artifacts found",
                "artifacts_produced": 0,
            }

        ranking = ranking_list[0].get("data", {}).get("ranking", [])
        if not ranking:
            return {
                "status": "skipped",
                "message": "Empty node ranking",
                "artifacts_produced": 0,
            }

        # Load feature tables (indexed by node_name)
        ft_result = await state.artifacts().kind("feature_table").get()
        ft_list = ft_result.to_list() if ft_result else []
        ft_by_node = {ft.get("node_name"): ft for ft in ft_list}

        import asyncio

        from utils.llm_service import get_llm_service

        llm = get_llm_service()

        # Determine failure label (opposite of success)
        failure_label = 0 if self.success_label == 1 else 1

        # Phase 1: Select which nodes to process (sequential — needs dedup/early-stop)
        selected_nodes: List[Dict] = []
        improved_paths: set = set()

        for node_info in ranking:
            if len(selected_nodes) >= self.top_n:
                break

            node_name = node_info["node_name"]

            prompt_path = self._find_system_prompt_path(node_name)
            if prompt_path and prompt_path in improved_paths:
                self._log(
                    f"Prompt file '{prompt_path}' already improved by another node, skipping {node_name}.",
                )
                continue

            original_prompt = self._find_system_prompt(node_name)
            if not original_prompt:
                self._log(f"No system prompt found for '{node_name}', skipping.")
                continue

            selected_nodes.append({
                "node_info": node_info,
                "node_name": node_name,
                "original_prompt": original_prompt,
                "prompt_path": prompt_path,
                "feature_data": ft_by_node.get(node_name, {}).get("data", {}),
            })
            if prompt_path:
                improved_paths.add(prompt_path)

        if not selected_nodes:
            return {
                "status": "skipped",
                "message": "No nodes with findable system prompts",
                "artifacts_produced": 0,
            }

        # Phase 2: Process all selected nodes in parallel (LLM calls overlap)
        async def _process_one_node(sel):
            node_name = sel["node_name"]
            original_prompt = sel["original_prompt"]
            cv_f1 = sel["node_info"].get("cv_f1", 0)

            self._log(f"Processing {node_name} (CV F1: {cv_f1:.3f})...")

            recommendations = await self._generate_recommendations(
                original_prompt=original_prompt,
                node_info=sel["node_info"],
                feature_data=sel["feature_data"],
                failure_label=failure_label,
                llm=llm,
            )

            if not recommendations:
                self._log(f"Failed to generate recommendations for {node_name}", level="warning")
                return None

            improved_prompt = await self._rewrite_prompt(
                original_prompt=original_prompt,
                recommendations=recommendations,
                node_name=node_name,
                llm=llm,
            )

            if not improved_prompt:
                self._log(f"Failed to rewrite prompt for {node_name}", level="warning")
                return None

            return {
                "node_name": node_name,
                "original_prompt": original_prompt,
                "recommendations": recommendations,
                "improved_prompt": improved_prompt,
                "cv_f1": cv_f1,
                "prompt_path": sel["prompt_path"],
            }

        results = await asyncio.gather(
            *[_process_one_node(s) for s in selected_nodes],
            return_exceptions=True,
        )

        # Phase 3: Save artifacts and apply to disk (sequential)
        artifacts_produced = 0
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                node_name = selected_nodes[i]["node_name"]
                self._log(f"Error processing {node_name}: {result}", level="error")
                continue
            if result is None:
                continue

            artifact = {
                "name": f"{result['node_name']} recommendations",
                "node_name": result["node_name"],
                "data": {
                    "original_prompt": result["original_prompt"],
                    "recommendations": result["recommendations"],
                    "improved_prompt": result["improved_prompt"],
                    "success_label": self.success_label,
                    "success_label_name": self.success_label_name,
                    "failure_label_name": self.failure_label_name,
                    "cv_f1": result["cv_f1"],
                },
            }
            await state.artifacts().from_plugin(self.name).kind("recommendation").save([artifact])
            artifacts_produced += 1

            if self.apply_to_disk and result["prompt_path"]:
                self._apply_improved_prompt(result["prompt_path"], result["improved_prompt"], state)

            self._log(
                f"Saved recommendation for {result['node_name']} "
                f"({len(result['improved_prompt'])} chars improved prompt)"
            )

        return {
            "status": "success" if artifacts_produced > 0 else "skipped",
            "artifacts_produced": artifacts_produced,
            "prompts_improved": artifacts_produced,
        }

    # ── System Prompt Loading ─────────────────────────────────────

    def _find_system_prompt_path(self, node_name: str) -> Optional[str]:
        """Find the filesystem path of a system prompt for a node.

        Priority:
        1. .txt file in prompts_dir (system_prompt_{name}.txt etc.)
        2. Python source file in codebase containing a prompt variable
        """
        # Priority 1: .txt file in prompts_dir
        txt_path = self._find_txt_prompt_path(node_name)
        if txt_path:
            return txt_path

        # Priority 2: Python source in codebase
        if node_name not in self._source_info:
            source = self._find_prompt_in_source(node_name)
            self._source_info[node_name] = source  # cache (even if None)

        source_info = self._source_info.get(node_name)
        if source_info:
            return source_info["path"]

        return None

    def _find_txt_prompt_path(self, node_name: str) -> Optional[str]:
        """Find a .txt prompt file in prompts_dir."""
        if not self.prompts_dir:
            return None

        candidates = [node_name]
        if "." in node_name:
            candidates.append(node_name.rsplit(".", 1)[0])

        for name in candidates:
            patterns = [
                f"system_prompt_{name}.txt",
                f"prompt_{name}.txt",
                f"{name}_prompt.txt",
                f"{name}.txt",
            ]
            for pattern in patterns:
                path = os.path.join(self.prompts_dir, pattern)
                if os.path.exists(path):
                    return path
        return None

    def _find_system_prompt(self, node_name: str) -> Optional[str]:
        """Find and load original system prompt for a node."""
        # Try .txt file first
        txt_path = self._find_txt_prompt_path(node_name)
        if txt_path:
            with open(txt_path) as f:
                return f.read()

        # Try Python source (use cache from _find_system_prompt_path)
        source_info = self._source_info.get(node_name)
        if source_info:
            return source_info["content"]

        # Search if not cached yet
        source_info = self._find_prompt_in_source(node_name)
        if source_info:
            self._source_info[node_name] = source_info
            return source_info["content"]

        return None

    # Directories to skip when searching for prompts in Python source
    _SKIP_DIRS = {".venv", "venv", "node_modules", "__pycache__", ".git", ".tox", ".eggs", "dist", "build"}

    def _find_prompt_in_source(self, node_name: str) -> Optional[Dict]:
        """Search Python source files in codebase for system prompt variables.

        Looks for variable assignments like SYSTEM_PROMPT = "..." where the
        variable name suggests a system prompt (e.g. contains 'system' and 'prompt').
        Skips virtual environments and build directories.

        Returns dict with: path, content, var_name, is_python.
        """
        if not self._codebase_path:
            return None

        candidates = []
        codebase = Path(self._codebase_path)

        for py_file in self._iter_source_files(codebase):
            try:
                source = py_file.read_text()
                tree = ast_module.parse(source)
            except Exception:
                continue

            for node in ast_module.walk(tree):
                if not isinstance(node, ast_module.Assign):
                    continue
                for target in node.targets:
                    if not isinstance(target, ast_module.Name):
                        continue
                    name_lower = target.id.lower()
                    # Must look like a system prompt variable, not just any var with "prompt" in it
                    if not self._is_prompt_variable(name_lower):
                        continue
                    # Extract string value (must be a real prompt, not a short constant)
                    if isinstance(node.value, ast_module.Constant) and isinstance(
                        node.value.value, str
                    ):
                        value = node.value.value
                        if len(value) < 10:  # Skip trivially short strings
                            continue
                        candidates.append({
                            "path": str(py_file),
                            "content": value,
                            "var_name": target.id,
                            "is_python": True,
                        })

        if not candidates:
            return None

        # Try to match by node name → filename
        node_base = node_name.lower().split(".")[0]
        for c in candidates:
            file_stem = Path(c["path"]).stem.lower()
            if node_base in file_stem or file_stem in node_base:
                return c

        # Single candidate — use it
        if len(candidates) == 1:
            return candidates[0]

        self._log(
            f"Found {len(candidates)} prompt variables in source but couldn't match to '{node_name}': "
            f"{[c['var_name'] + ' in ' + Path(c['path']).name for c in candidates]}",
            level="warning",
        )
        return None

    def _iter_source_files(self, root: Path):
        """Walk .py files, skipping virtual environments and build dirs."""
        for child in sorted(root.iterdir()):
            if child.name in self._SKIP_DIRS:
                continue
            if child.is_dir():
                yield from self._iter_source_files(child)
            elif child.suffix == ".py":
                yield child

    @staticmethod
    def _is_prompt_variable(name_lower: str) -> bool:
        """Check if a variable name looks like a system prompt assignment."""
        # Match patterns like: SYSTEM_PROMPT, system_prompt, SYS_PROMPT, DEFAULT_SYSTEM_MESSAGE
        if "system" in name_lower and ("prompt" in name_lower or "message" in name_lower):
            return True
        # Match explicit prompt-named vars like AGENT_PROMPT, MY_PROMPT
        if name_lower.endswith("_prompt") or name_lower.startswith("prompt_"):
            return True
        return False

    # ── Recommendation Generation ─────────────────────────────────

    async def _generate_recommendations(
        self,
        original_prompt: str,
        node_info: Dict,
        feature_data: Dict,
        failure_label: int,
        llm,
    ) -> Optional[Dict]:
        """Generate analysis recommendations via LLM."""
        feature_descriptions = feature_data.get("feature_descriptions", {})
        features_per_trace = feature_data.get("features_per_trace", [])
        tree_rules = feature_data.get("tree_rules", node_info.get("tree_rules", ""))
        feature_importance = feature_data.get(
            "feature_importance", node_info.get("feature_importance", [])
        )

        # Build feature descriptions text
        feat_desc_text = ""
        for feat_name, feat_desc in feature_descriptions.items():
            feat_desc_text += f"**{feat_name}**: {feat_desc}\n"

        # Build feature importance text
        feat_imp_text = ""
        for feat in (feature_importance or [])[:10]:
            feat_imp_text += f"- {feat['feature']}: {feat['importance']:.3f}\n"

        # Build success/failure examples
        success_examples = [
            r for r in features_per_trace if r.get("cluster_label") == self.success_label
        ]
        failure_examples = [
            r for r in features_per_trace if r.get("cluster_label") == failure_label
        ]

        success_text = self._format_examples(success_examples[:3], self.success_label_name)
        failure_text = self._format_examples(failure_examples[:5], self.failure_label_name)

        prompt = RECOMMENDATION_USER_TEMPLATE.format(
            success_label_name=self.success_label_name,
            success_label=self.success_label,
            failure_label_name=self.failure_label_name,
            failure_label=failure_label,
            original_prompt=original_prompt[:4000],
            feature_descriptions_text=feat_desc_text,
            tree_rules=tree_rules[:1500],
            feature_importance_text=feat_imp_text,
            success_examples_text=success_text,
            failure_examples_text=failure_text,
        )

        try:
            response = await llm.call_llm(
                user_prompt=prompt,
                system_prompt=RECOMMENDATION_SYSTEM_PROMPT,
                schema=RECOMMENDATION_SCHEMA,
                attributes={"temperature": 0, "max_tokens": 4096},
            )

            data = json.loads(response.content)

            # Normalize fields that might be dicts instead of lists
            for key in ["critical_issues", "success_patterns"]:
                val = data.get(key, [])
                if isinstance(val, dict):
                    data[key] = [f"{k}: {v}" for k, v in val.items()]

            return {
                "critical_issues": data.get("critical_issues", []),
                "success_patterns": data.get("success_patterns", []),
                "prompt_additions": data.get("prompt_additions", []),
                "prompt_warnings": data.get("prompt_warnings", []),
                "example_good_behavior": data.get("example_good_behavior", ""),
                "example_bad_behavior": data.get("example_bad_behavior", ""),
            }
        except Exception as e:
            self._log(f"Recommendation generation failed: {e}", level="error")
            return None

    @staticmethod
    def _format_examples(examples: List[Dict], label_name: str) -> str:
        """Format trace examples for the analysis prompt."""
        if not examples:
            return f"No {label_name} examples available.\n"

        text = ""
        for idx, row in enumerate(examples):
            text += f"\n### {label_name} Example {idx + 1}:\n"
            for col, val in row.items():
                if col != "cluster_label" and str(val) != "none":
                    text += f"  - {col}: {val}\n"
        return text

    # ── Apply to Disk (code_modifier pattern) ───────────────────

    def _apply_improved_prompt(self, prompt_path: str, improved_prompt: str, state) -> None:
        """Write improved prompt back to disk with backup. Follows code_modifier pattern."""
        original_path = Path(prompt_path)

        # Create backup directory in session output
        backup_dir = Path(state.output_dir) / "prompt_backups" if hasattr(state, "output_dir") and state.output_dir else original_path.parent / ".prompt_backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        # Backup original (timestamped, like code_modifier)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{original_path.name}.{timestamp}.bak"
        backup_path = backup_dir / backup_name

        try:
            shutil.copy2(original_path, backup_path)
            self._log(f"Backed up {original_path.name} → {backup_path}")

            if prompt_path.endswith(".py"):
                self._apply_to_python_source(original_path, improved_prompt)
            else:
                original_path.write_text(improved_prompt)
                self._log(f"Applied improved prompt to {original_path}")
        except Exception as e:
            # Restore from backup on failure
            if backup_path.exists():
                shutil.copy2(backup_path, original_path)
            self._log(f"Failed to apply prompt to {original_path}: {e}", level="error")

    def _apply_to_python_source(self, file_path: Path, improved_prompt: str) -> None:
        """Replace a prompt string literal in a Python source file."""
        # Find the cached source info for this file
        source_info = None
        for info in self._source_info.values():
            if info and info.get("path") == str(file_path):
                source_info = info
                break

        if not source_info:
            self._log(f"No source info cached for {file_path}", level="error")
            return

        source = file_path.read_text()
        var_name = source_info["var_name"]

        # Re-parse AST to find the exact source segment of the string literal
        try:
            tree = ast_module.parse(source)
        except SyntaxError as e:
            self._log(f"Failed to parse {file_path}: {e}", level="error")
            return

        for node in ast_module.walk(tree):
            if not isinstance(node, ast_module.Assign):
                continue
            for target in node.targets:
                if isinstance(target, ast_module.Name) and target.id == var_name:
                    old_segment = ast_module.get_source_segment(source, node.value)
                    if old_segment:
                        new_literal = f'"""\\\n{improved_prompt}"""'
                        new_source = source.replace(old_segment, new_literal, 1)
                        file_path.write_text(new_source)
                        self._log(f"Applied improved prompt to {file_path} ({var_name})")
                        return

        self._log(f"Could not locate {var_name} string literal in {file_path}", level="error")

    # ── Prompt Rewriting ──────────────────────────────────────────

    async def _rewrite_prompt(
        self,
        original_prompt: str,
        recommendations: Dict,
        node_name: str,
        llm,
    ) -> Optional[str]:
        """Rewrite the original system prompt incorporating recommendations."""
        issues_text = "\n".join(f"- {x}" for x in recommendations.get("critical_issues", []))
        additions_text = "\n".join(f"- {x}" for x in recommendations.get("prompt_additions", []))
        warnings_text = "\n".join(f"- {x}" for x in recommendations.get("prompt_warnings", []))
        good = recommendations.get("example_good_behavior", "(none)")
        bad = recommendations.get("example_bad_behavior", "(none)")

        prompt = PROMPT_REWRITE_USER_TEMPLATE.format(
            original_prompt=original_prompt,
            issues_text=issues_text or "(none identified)",
            additions_text=additions_text or "(none identified)",
            warnings_text=warnings_text or "(none identified)",
            good_example=good,
            bad_example=bad,
        )

        try:
            response = await llm.call_llm(
                user_prompt=prompt,
                system_prompt=PROMPT_REWRITE_SYSTEM_PROMPT,
                attributes={"temperature": 0.3, "max_tokens": 8192},
            )

            improved = response.content.strip()

            # Strip markdown code fences if LLM wraps the output
            if improved.startswith("```"):
                lines = improved.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                improved = "\n".join(lines)

            # Strip leaked template sections the LLM may have echoed back
            leaked_markers = [
                "## RECOMMENDATIONS TO INCORPORATE",
                "=== ANALYSIS FINDINGS",
                "## RULES FOR REWRITING",
                "=== END OF ANALYSIS",
                "Now return ONLY the complete",
                "Critical issues causing failures",
                "Additions to make",
                "Warnings / constraints",
                "Warnings / Constraints",
                "Example of good behavior:",
                "Example of bad behavior:",
                "Example of Good Behavior",
                "Example of Bad Behavior",
            ]
            for marker in leaked_markers:
                idx = improved.find(marker)
                if idx > 0:
                    improved = improved[:idx].rstrip()
                    self._log(f"  [{node_name}] Stripped leaked template content from LLM output")
                    break

            return improved
        except Exception as e:
            self._log(f"Prompt rewriting failed for {node_name}: {e}", level="error")
            return None
