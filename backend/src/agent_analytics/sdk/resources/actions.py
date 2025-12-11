"""
Actions resource for the AgentOps SDK

Provides methods for querying and creating actions (Actions).
"""

from typing import Any

from agent_analytics.core.data.action_data import ActionData
from agent_analytics.core.data_composite.action import BaseAction, ActionComposite
from agent_analytics.runtime.storage.logical_data_manager import AnalyticsDataManager
from agent_analytics.runtime.storage.store_interface import QueryFilter, QueryOperator
from agent_analytics.sdk.models import Action


class ActionsResource:
    """
    API for working with actions.

    This resource provides methods to query, create, and retrieve action data
    from the analytics platform. Actions represent executable units of work
    within workflows.
    """

    def __init__(self, data_manager: AnalyticsDataManager):
        """
        Initialize the trace groups resource.

        Args:
            data_manager: The data manager instance
        """
        self._data_manager = data_manager



    async def fetch_by_owner(
        self,
        owner: Any,
        names: list[str] | None = None,
        code_ids: list[str] | None = None
    ) -> list[Action]:
        """
        Get all actions owned by a specific element.

        Args:
            owner: The owner element (wrapper, composite, or ID string)
            names: Optional list of names to filter by
            code_ids: Optional list of code IDs to filter by

        Returns:
            List of Action objects

        Example:
            # Get all actions owned by an element
            actions = await client.actions.fetch_by_owner(trace)

            # Filter by names
            actions = await client.actions.fetch_by_owner(
                owner=trace,
                names=["action-a", "action-b"]
            )

            # Filter by code IDs
            actions = await client.actions.fetch_by_owner(
                owner=trace,
                code_ids=["code-123"]
            )
        """
        # Extract ID from owner
        if hasattr(owner, "id"):
            root_id = owner.id
        elif hasattr(owner, "element_id"):
            root_id = owner.element_id
        elif isinstance(owner, str):
            root_id = owner
        else:
            raise TypeError("owner must be an Element object or string ID")

        # Build query
        query = {
            "root_id": QueryFilter(operator=QueryOperator.EQUAL, value=root_id)
        }

        if names:
            query["name"] = QueryFilter(operator=QueryOperator.EQUALS_MANY, value=names)

        if code_ids:
            query["code_id"] = QueryFilter(operator=QueryOperator.EQUALS_MANY, value=code_ids)

        composites = await self._data_manager.search(
            element_type=ActionComposite,
            query=query
        )

        return [self._to_sdk_model(comp) for comp in composites]

    async def fetch_by_code_id(
        self,
        code_id: str
    ) -> list[Action]:
        """
        Get actions by code ID.

        Args:
            code_id: The code ID to search for

        Returns:
            List of Action objects with the specified code ID

        Example:
            actions = await client.actions.fetch_by_code_id("code-123")
        """
        query = {
            "code_id": QueryFilter(operator=QueryOperator.EQUAL, value=code_id)
        }

        composites = await self._data_manager.search(
            element_type=ActionComposite,
            query=query
        )

        return [self._to_sdk_model(comp) for comp in composites]

    async def get(self, action_id: str) -> Action | None:
        """
        Get a specific action by ID.

        Args:
            action_id: The unique identifier of the action

        Returns:
            Action object if found, None otherwise

        Example:
            action = await client.actions.get("action-123")
        """
        # Get action using the internal API
        action_composite = await ActionComposite.get_by_id(
            data_manager=self._data_manager,
            id=action_id
        )

        if action_composite is None:
            return None

        return self._to_sdk_model(action_composite)

    async def create(
        self,
        root: Any,
        name: str,
        description: str,
        element_id: str | None = None,
        input_schema: str | None = None,
        output_schema: str | None = None,
        code_id: str | None = None,
        is_generated: bool = False,
        consumed_resources: list[str] | None = None
    ) -> Action:
        """
        Create a new action.

        Args:
            root: Root element this action belongs to
            name: Display name for the action
            description: Description of the action
            element_id: Optional custom element ID (auto-generated if not provided)
            input_schema: Optional input schema definition
            output_schema: Optional output schema definition
            code_id: Optional code implementation identifier
            is_generated: Whether this action was automatically generated
            consumed_resources: Optional list of consumed resources
           

        Returns:
            Created Action object

        Example:
            action = await client.actions.create(
                root=trace,
                name="Process Data",
                description="Processes incoming data",
                input_schema='{"type": "object", "properties": {"data": {"type": "string"}}}',
                output_schema='{"type": "object", "properties": {"result": {"type": "string"}}}',
                code_id="process_data_v1",
                is_generated=False,
                consumed_resources=["database", "cache"],
               
            )
        """
        # Use ActionComposite.create() following the same pattern as other resources
        action_composite = await ActionComposite.create(
            data_manager=self._data_manager,
            element_id=element_id or f"Action:{name}",
            root=root,
            name=name,
            description=description,
            input_schema=input_schema,
            output_schema=output_schema,
            code_id=code_id,
            is_generated=is_generated,
            consumed_resources=consumed_resources
        )

        return self._to_sdk_model(action_composite)

    async def create_many(
        self,
        root: Any,
        actions: list[dict[str, Any]]
    ) -> list[Action]:
        """
        Create multiple actions at once for better performance.

        Args:
            root: Root element these actions belong to
            actions: List of action definitions, each containing:
                - name (str): Display name
                - description (str): Description
                - element_id (str, optional): Custom element ID
                - input_schema (str, optional): Input schema
                - output_schema (str, optional): Output schema
                - code_id (str, optional): Code ID
                - is_generated (bool, optional): Whether generated
                - consumed_resources (list[str], optional): Consumed resources
                
        Returns:
            List of created Action objects

        Example:
            actions = await client.actions.create_many(
                root=trace,
                actions=[
                    {
                        "name": "Process Input",
                        "description": "Processes input data",
                        "code_id": "process_input_v1",
                        
                    },
                    {
                        "name": "Generate Output",
                        "description": "Generates output data",
                        "code_id": "generate_output_v1"
                        
                    }
                ]
            )
        """
        # Build list of BaseAction objects
        builders = []
        for action_dict in actions:
            if "name" not in action_dict:
                raise ValueError("Each action must have a 'name' field")
            if "description" not in action_dict:
                raise ValueError("Each action must have a 'description' field")

            builder = BaseAction(
                element_id=action_dict.get("element_id") or f"Action:{action_dict['name']}",
                root=root,
                name=action_dict["name"],
                description=action_dict["description"],
                input_schema=action_dict.get("input_schema"),
                output_schema=action_dict.get("output_schema"),
                code_id=action_dict.get("code_id"),
                is_generated=action_dict.get("is_generated", False),
                consumed_resources=action_dict.get("consumed_resources", [])

            )

            # Handle additional attributes
            for key, value in action_dict.items():
                if key not in ["name", "description", "element_id", "input_schema",
                              "output_schema", "code_id", "is_generated",
                              "consumed_resources"]:
                    builder.attributes[key] = value

            builders.append(builder)

        # Use bulk_store for efficiency
        composites = await BaseAction.bulk_store(self._data_manager, builders)

        return [self._to_sdk_model(c) for c in composites]

    def _to_sdk_model(self, composite: ActionComposite) -> Action:
        """
        Convert internal composite to SDK model.

        Args:
            composite: Internal Action composite object

        Returns:
            SDK Action model
        """
        return Action(_composite=composite)

    async def delete(self, action_id: str) -> bool:
        """
        Delete an action by its ID.
        Args:
            action_id: The unique identifier of the action to delete
        Returns:
            True if deleted successfully, False if action not found
        Example:
            success = await client.actions.delete("action-123")
        """
        return await self._data_manager._persistent_manager.delete(
            element_id=action_id,
            artifact_type=ActionData
        )

    async def delete_by_root_id(self, root_id: str) -> int:
        """
        Delete all actions with the given root_id.
        Args:
            root_id: The root_id (trace_id) to delete actions for
        Returns:
            Number of actions deleted
        Example:
            count = await client.actions.delete_by_root_id("trace-123")
        """
        # Get all actions with this root_id
        query = {
            "root_id": QueryFilter(operator=QueryOperator.EQUAL, value=root_id)
        }

        action_composites = await self._data_manager.search(
            element_type=ActionComposite,
            query=query
        )

        # Delete each action
        deleted_count = 0
        for action in action_composites:
            try:
                await self._data_manager._persistent_manager.delete(
                    element_id=action.element_id,
                    artifact_type=ActionData
                )
                deleted_count += 1
            except Exception:
                # Log but continue deleting other actions
                pass

        return deleted_count