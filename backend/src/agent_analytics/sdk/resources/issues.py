"""
Issues resource for the AgentOps SDK

Provides methods for creating and querying issues.
"""

from typing import Any

from agent_analytics_common.interfaces.issues import IssueLevel

from agent_analytics.core.data_composite.issue import BaseIssue, IssueComposite
from agent_analytics.runtime.storage.logical_data_manager import AnalyticsDataManager
from agent_analytics.sdk.models import Issue
from agent_analytics.sdk.resources.base_relatable import RelatableElementsResource


class IssuesResource(RelatableElementsResource[IssueComposite, Issue]):
    """
    API for working with issues.

    This resource provides methods to create and query issues
    associated with traces, trace groups, or any other element.
    """

    def __init__(self, data_manager: AnalyticsDataManager):
        """
        Initialize the issues resource.

        Args:
            data_manager: The data manager instance
        """
        super().__init__(data_manager)

    def _get_composite_class(self) -> type[IssueComposite]:
        """Get the IssueComposite class"""
        return IssueComposite

    def _get_builder_class(self) -> type:
        """Get the BaseIssue class (used for bulk_store)"""
        return BaseIssue

    def _get_bulk_store_param_name(self) -> str:
        """Override to return correct parameter name for bulk_store"""
        return "base_issues"

    def _validate_create_params(self, **kwargs):
        """
        Validate issue creation parameters.

        Args:
            **kwargs: Parameters including name, description

        Raises:
            ValueError: If required parameters are missing
        """
        if not kwargs.get("name"):
            raise ValueError("Issue name is required")

        if not kwargs.get("description"):
            raise ValueError("Issue description is required")

    def _create_builder(self, **kwargs) -> BaseIssue:
        """
        Create an issue builder instance.

        Args:
            **kwargs: Parameters including name, description, level, etc.

        Returns:
            BaseIssue builder instance
        """
        return BaseIssue(
            name=kwargs["name"],
            description=kwargs["description"],
            level=kwargs.get("level", IssueLevel.WARNING),
            confidence=kwargs.get("confidence"),
            effect=kwargs.get("effect") or [],
            tags=kwargs.get("tags") or [],
            plugin_metadata_id=kwargs.get("plugin_metadata_id")
        )

    def _to_sdk_model(self, composite: IssueComposite, **kwargs) -> Issue:
        """
        Convert internal composite to SDK model.

        Args:
            composite: Internal issue composite object
            **kwargs: Additional parameters

        Returns:
            SDK Issue model
        """
        return Issue(_composite=composite)

    async def create(
        self,
        owner: Any,
        name: str,
        description: str,
        level: IssueLevel = IssueLevel.WARNING,
        confidence: float | None = None,
        effect: list[str] | None = None,
        related_to: list[Any] | tuple[list[str], list[str]] | None = None,
        tags: list[str] | None = None,
        plugin_id: str | None = None
    ) -> Issue:
        """
        Create a new issue associated with an owner element.

        Args:
            owner: Owner element this issue belongs to (Trace, TraceGroup, or any Element)
            name: Display name for the issue
            description: Description of the issue
            level: Severity level of the issue (INFO, WARNING, ERROR, CRITICAL)
            confidence: Confidence level (0.0 to 1.0)
            effect: List of effects this issue causes
            related_to: Optional elements to relate this issue to (e.g., Span, Task)
            tags: List of tags for categorization
            plugin_id: Optional identifier of the plugin that created this issue

        Returns:
            The created Issue object

        Example:
            # Create an issue for a trace
            issue = await client.issues.create(
                owner=trace,
                name="High Latency",
                description="Response time exceeded threshold",
                level=IssueLevel.WARNING,
                confidence=0.95,
                effect=["slow_response"],
                related_to=[span1, span2]
            )

            # Create an issue for a trace group
            issue = await client.issues.create(
                owner=trace_group,
                name="Consistent Failures",
                description="Multiple traces failing",
                level=IssueLevel.ERROR
            )

            # Create an issue related to a task
            issue = await client.issues.create(
                owner=trace,
                name="Task Timeout",
                description="Task exceeded time limit",
                related_to=[task]
            )
        """
        return await super().create(
            owner=owner,
            name=name,
            description=description,
            related_to=related_to,
            tags=tags,
            plugin_id=plugin_id,
            level=level,
            confidence=confidence,
            effect=effect
        )

    async def create_many(
        self,
        owner: Any,
        issues: list[dict[str, Any]]
    ) -> list[Issue]:
        """
        Create multiple issues at once for better performance.

        Args:
            owner: Owner element these issues belong to
            issues: List of issue definitions

        Returns:
            List of created Issue objects

        Example:
            issues = await client.issues.create_many(
                owner=trace,
                issues=[
                    {
                        "name": "High Latency",
                        "description": "Slow response",
                        "level": IssueLevel.WARNING
                    },
                    {
                        "name": "Error",
                        "description": "Operation failed",
                        "level": IssueLevel.ERROR
                    }
                ]
            )
        """
        return await super().create_many(owner=owner, elements=issues)
