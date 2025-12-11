"""
Annotations resource for the AgentOps SDK

Provides methods for creating and querying annotations.
"""

from typing import Any

from ibm_agent_analytics_common.interfaces.annotations import DataAnnotation

from agent_analytics.core.data_composite.annotation import AnnotationComposite, BaseAnnotation
from agent_analytics.runtime.storage.logical_data_manager import AnalyticsDataManager
from agent_analytics.sdk.models import Annotation
from agent_analytics.sdk.resources.base_relatable import RelatableElementsResource


class AnnotationsResource(RelatableElementsResource[AnnotationComposite, Annotation]):
    """
    API for working with annotations.

    This resource provides methods to create and query annotations
    associated with traces, trace groups, or any other element.
    """

    def __init__(self, data_manager: AnalyticsDataManager):
        """
        Initialize the annotations resource.

        Args:
            data_manager: The data manager instance
        """
        super().__init__(data_manager)

    def _get_composite_class(self) -> type[AnnotationComposite]:
        """Get the AnnotationComposite class"""
        return AnnotationComposite

    def _get_builder_class(self) -> type:
        """Get the BaseAnnotation class (used for bulk_store)"""
        return BaseAnnotation

    def _get_bulk_store_param_name(self) -> str:
        """Override to return correct parameter name for bulk_store"""
        return "base_annotations"

    def _validate_create_params(self, **kwargs):
        """
        Validate annotation creation parameters.

        Args:
            **kwargs: Parameters including name, description, segment_start

        Raises:
            ValueError: If required parameters are missing
        """
        if not kwargs.get("name"):
            raise ValueError("Annotation name is required")

        if not kwargs.get("description"):
            raise ValueError("Annotation description is required")

        if "segment_start" not in kwargs:
            raise ValueError("Annotation segment_start is required")

    def _create_builder(self, **kwargs) -> BaseAnnotation:
        """
        Create an annotation builder instance.

        Args:
            **kwargs: Parameters including name, description, segment_start, etc.

        Returns:
            BaseAnnotation builder instance
        """
        return BaseAnnotation(
            name=kwargs["name"],
            description=kwargs["description"],
            annotation_type=kwargs.get("annotation_type", DataAnnotation.Type.RAW_TEXT),
            path_to_string=kwargs.get("path_to_string"),
            segment_start=kwargs["segment_start"],
            segment_end=kwargs.get("segment_end"),
            annotation_title=kwargs.get("annotation_title"),
            annotation_content=kwargs.get("annotation_content"),
            tags=kwargs.get("tags", []),
            plugin_metadata_id=kwargs.get("plugin_metadata_id")
        )

    def _to_sdk_model(self, composite: AnnotationComposite, **kwargs) -> Annotation:
        """
        Convert internal composite to SDK model.

        Args:
            composite: Internal annotation composite object
            **kwargs: Additional parameters

        Returns:
            SDK Annotation model
        """
        return Annotation(_composite=composite)

    async def create(
        self,
        owner: Any,
        name: str,
        description: str,
        segment_start: int,
        annotation_type: DataAnnotation.Type = DataAnnotation.Type.RAW_TEXT,
        path_to_string: str | None = None,
        segment_end: int | None = None,
        annotation_title: str | None = None,
        annotation_content: str | None = None,
        related_to: list[Any] | tuple[list[str], list[str]] | None = None,
        tags: list[str] | None = None,
        plugin_id: str | None = None
    ) -> Annotation:
        """
        Create a new annotation associated with an owner element.

        Args:
            owner: Owner element this annotation belongs to
            name: Display name for the annotation
            description: Description of the annotation
            segment_start: Start position of the annotated segment
            annotation_type: Type of annotation (RAW_TEXT, MARKDOWN, etc.)
            path_to_string: Path to the annotated string
            segment_end: End position of the annotated segment
            annotation_title: Title of the annotation
            annotation_content: Content of the annotation
            related_to: Optional elements to relate this annotation to
            tags: List of tags for categorization
            plugin_id: Optional identifier of the plugin that created this annotation

        Returns:
            The created Annotation object

        Example:
            annotation = await client.annotations.create(
                owner=trace,
                name="Critical Section",
                description="Performance bottleneck",
                segment_start=100,
                segment_end=200,
                annotation_type=DataAnnotation.Type.RAW_TEXT,
                annotation_title="Bottleneck",
                annotation_content="This section is slow",
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
            segment_start=segment_start,
            annotation_type=annotation_type,
            path_to_string=path_to_string,
            segment_end=segment_end,
            annotation_title=annotation_title,
            annotation_content=annotation_content
        )

    async def create_many(
        self,
        owner: Any,
        annotations: list[dict[str, Any]]
    ) -> list[Annotation]:
        """
        Create multiple annotations at once for better performance.

        Args:
            owner: Owner element these annotations belong to
            annotations: List of annotation definitions

        Returns:
            List of created Annotation objects
        """
        return await super().create_many(owner=owner, elements=annotations)
