"""
Recommendations resource for the AgentOps SDK

Provides methods for creating and querying recommendations.
"""

from typing import Any

from agent_analytics_common.interfaces.recommendations import RecommendationLevel

from agent_analytics.core.data_composite.recommendation import (
    BaseRecommendation,
    RecommendationComposite,
)
from agent_analytics.runtime.storage.logical_data_manager import AnalyticsDataManager
from agent_analytics.sdk.models import Recommendation
from agent_analytics.sdk.resources.base_relatable import RelatableElementsResource


class RecommendationsResource(RelatableElementsResource[RecommendationComposite, Recommendation]):
    """
    API for working with recommendations.

    This resource provides methods to create and query recommendations
    associated with traces, trace groups, or any other element.
    """

    def __init__(self, data_manager: AnalyticsDataManager):
        """
        Initialize the recommendations resource.

        Args:
            data_manager: The data manager instance
        """
        super().__init__(data_manager)

    def _get_composite_class(self) -> type[RecommendationComposite]:
        """Get the RecommendationComposite class"""
        return RecommendationComposite

    def _get_builder_class(self) -> type:
        """Get the BaseRecommendation class (used for bulk_store)"""
        return BaseRecommendation

    def _get_bulk_store_param_name(self) -> str:
        """Override to return correct parameter name for bulk_store"""
        return "base_recommendations"

    def _validate_create_params(self, **kwargs):
        """
        Validate recommendation creation parameters.

        Args:
            **kwargs: Parameters including name, description

        Raises:
            ValueError: If required parameters are missing
        """
        if not kwargs.get("name"):
            raise ValueError("Recommendation name is required")

        if not kwargs.get("description"):
            raise ValueError("Recommendation description is required")

    def _create_builder(self, **kwargs) -> BaseRecommendation:
        """
        Create a recommendation builder instance.

        Args:
            **kwargs: Parameters including name, description, level, etc.

        Returns:
            BaseRecommendation builder instance
        """
        return BaseRecommendation(
            name=kwargs["name"],
            description=kwargs["description"],
            level=kwargs.get("level", RecommendationLevel.MODERATE),
            effect=kwargs.get("effect", []),
            tags=kwargs.get("tags", []),
            plugin_metadata_id=kwargs.get("plugin_metadata_id")
        )

    def _to_sdk_model(self, composite: RecommendationComposite, **kwargs) -> Recommendation:
        """
        Convert internal composite to SDK model.

        Args:
            composite: Internal recommendation composite object
            **kwargs: Additional parameters

        Returns:
            SDK Recommendation model
        """
        return Recommendation(_composite=composite)

    async def create(
        self,
        owner: Any,
        name: str,
        description: str,
        level: RecommendationLevel = RecommendationLevel.MODERATE,
        effect: list[str] | None = None,
        related_to: list[Any] | tuple[list[str], list[str]] | None = None,
        tags: list[str] | None = None,
        plugin_id: str | None = None
    ) -> Recommendation:
        """
        Create a new recommendation associated with an owner element.

        Args:
            owner: Owner element this recommendation belongs to
            name: Display name for the recommendation
            description: Description of the recommendation
            level: Impact level (MINOR, MODERATE, MAJOR, CRITICAL)
            effect: List of effects this recommendation provides
            related_to: Optional elements to relate this recommendation to
            tags: List of tags for categorization
            plugin_id: Optional identifier of the plugin that created this recommendation

        Returns:
            The created Recommendation object

        Example:
            recommendation = await client.recommendations.create(
                owner=trace,
                name="Optimize Query",
                description="Consider adding an index",
                level=RecommendationLevel.MAJOR,
                effect=["performance_improvement"],
                related_to=[span]
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
            effect=effect
        )

    async def create_many(
        self,
        owner: Any,
        recommendations: list[dict[str, Any]]
    ) -> list[Recommendation]:
        """
        Create multiple recommendations at once for better performance.

        Args:
            owner: Owner element these recommendations belong to
            recommendations: List of recommendation definitions

        Returns:
            List of created Recommendation objects
        """
        return await super().create_many(owner=owner, elements=recommendations)
