from datetime import datetime

from pydantic import BaseModel

from agent_analytics.runtime.registry.analytics_metadata import AnalyticsMetadata
from agent_analytics.runtime.registry.registry_data_manager import RegistryDataManager
from agent_analytics.runtime.registry.validators.dependency_validator import DependencyValidator
from agent_analytics.runtime.registry.validators.field_type_validator import FieldTypeValidator
from agent_analytics.runtime.registry.validators.field_validator import FieldValidator
from agent_analytics.runtime.registry.validators.plugin_validator import PluginValidator


class AnalyticsRegistry:
    def __init__(self, store: RegistryDataManager):
        self.store = store

    async def register_analytics(self, metadata: AnalyticsMetadata) -> str:
        existing = await self.store.find_analytic(metadata.id)
        if existing:
            raise ValueError(f"Analytics with ID {metadata.id} already exists")

        try:
            module_path = metadata.template.runtime.config.get("module_path")
            if not module_path:
                raise ValueError("Runtime configuration is missing 'module_path'")

            # Get both module and specs
            module, specs = PluginValidator.validate_module_import(module_path)

            # Update metadata with inferred specs if available
            if specs:
                input_spec, output_spec = specs
                metadata.template.input_spec = input_spec
                metadata.template.output_spec = output_spec

            # Validate field specifications structure
            FieldValidator.validate_field_specs(metadata)

            # Validate template config
            if metadata.template.config:
                for field_name, value in metadata.template.config.items():
                    field_spec = next(
                        (f for f in metadata.template.input_spec.fields if f.name == field_name),
                        None
                    )
                    if field_spec:
                        error = FieldTypeValidator.validate_field_value(value, field_spec)
                        if error:
                            raise ValueError(f"Invalid template config: {error}")

            # Validate dependencies (both backward and forward)
            await self._validate_dependencies(metadata)

            return await self.store.register_analytic(metadata)

        except Exception as e:
            raise ValueError(f"Analytics validation failed: {str(e)}")

    async def _validate_dependencies(self, metadata: AnalyticsMetadata) -> None:
        """Validates all dependencies (both backward dependsOn and forward triggers) of an analytics"""

        # 1. First, collect ALL available fields from ALL dependencies
        pipeline_inputs = set()
        all_dependencies_metadata = {}

        for dep_id in metadata.template.controller.dependsOn:
            dep_metadata = await self.store.find_analytic(dep_id)
            if not dep_metadata:
                raise ValueError(f"Dependent analytics {dep_id} not found")

            all_dependencies_metadata[dep_id] = dep_metadata

            # Accumulate all available fields from this dependency
            pipeline_inputs.update(
                field.name for field in dep_metadata.template.input_spec.fields
            )
            pipeline_inputs.update(
                field.name for field in dep_metadata.template.output_spec.fields
            )

        # 2. Now validate that ALL required inputs are satisfied
        # Check each dependency for type compatibility with our required inputs
        for dep_id, dep_metadata in all_dependencies_metadata.items():
            DependencyValidator.validate_dependency_fields(
                metadata,
                dep_metadata,
                pipeline_inputs
            )

        # 3. Validate forward dependencies (triggers)
        # Note: For triggers, we use lighter validation because the triggered analytics
        # may have its own dependency chain that will be included in the execution graph.
        # We just need to ensure the triggered analytics exists and is properly registered.
        for trigger_id in metadata.template.controller.triggers:
            trigger_metadata = await self.store.find_analytic(trigger_id)
            if not trigger_metadata:
                raise ValueError(f"Triggered analytics {trigger_id} not found")

            # Optional: Check for obvious field mismatches only when the triggered analytics
            # has NO dependencies (meaning it relies solely on the triggering analytics)
            if not trigger_metadata.template.controller.dependsOn:
                # Build available inputs for triggered analytics
                triggered_pipeline_inputs = pipeline_inputs.copy()

                # Add our input fields (passed through)
                triggered_pipeline_inputs.update(
                    field.name for field in metadata.template.input_spec.fields
                )

                # Add our output fields
                triggered_pipeline_inputs.update(
                    field.name for field in metadata.template.output_spec.fields
                )

                # Only validate if triggered analytics has no other dependencies
                try:
                    DependencyValidator.validate_dependency_fields(
                        trigger_metadata,
                        metadata,
                        triggered_pipeline_inputs
                    )
                except ValueError as e:
                    raise ValueError(
                        f"Analytics '{metadata.id}' triggers '{trigger_id}' which has no dependencies, "
                        f"but cannot satisfy its requirements: {str(e)}"
                    )

    async def get_analytics(self, analytics_id: str) -> AnalyticsMetadata | None:
        return await self.store.find_analytic(analytics_id)

    async def list_analytics(self, filter_params: dict | None = None) -> list[AnalyticsMetadata]:
        return await self.store.list_analytics(filter_params)

    async def update_analytics(self, analytics_id: str, metadata: AnalyticsMetadata) -> bool:
        """
        Update analytics with full validation, ensuring changes don't break dependencies
        and field requirements are met through the pipeline
        """
        existing = await self.store.find_analytic(analytics_id)
        if not existing:
            raise ValueError(f"Analytics with ID {analytics_id} not found")

        try:
            # 1. Get module and infer specs
            module_path = metadata.template.runtime.config.get("module_path")
            if not module_path:
                raise ValueError("Runtime configuration is missing 'module_path'")

            module, specs = PluginValidator.validate_module_import(module_path)
            if specs:
                input_spec, output_spec = specs
                # Update metadata with inferred specs
                metadata.template.input_spec = input_spec
                metadata.template.output_spec = output_spec

            # 2. Basic validation
            FieldValidator.validate_field_specs(metadata)

            # Validate template config
            if metadata.template.config:
                for field_name, value in metadata.template.config.items():
                    field_spec = next(
                        (f for f in metadata.template.input_spec.fields if f.name == field_name),
                        None
                    )
                    if field_spec:
                        error = FieldTypeValidator.validate_field_value(value, field_spec)
                        if error:
                            raise ValueError(f"Invalid template config: {error}")

            # 3. Validate this analytics' dependencies and available fields
            pipeline_inputs = set()
            all_dependencies_metadata = {}

            # Collect ALL available fields from ALL dependencies first
            for dep_id in metadata.template.controller.dependsOn:
                dep_metadata = await self.store.find_analytic(dep_id)
                if not dep_metadata:
                    raise ValueError(f"Dependent analytics {dep_id} not found")

                all_dependencies_metadata[dep_id] = dep_metadata

                # Accumulate all available fields
                pipeline_inputs.update(
                    field.name for field in dep_metadata.template.input_spec.fields
                )
                pipeline_inputs.update(
                    field.name for field in dep_metadata.template.output_spec.fields
                )

            # Now validate with the complete set of available fields
            for dep_id, dep_metadata in all_dependencies_metadata.items():
                DependencyValidator.validate_dependency_fields(
                    metadata,
                    dep_metadata,
                    pipeline_inputs
                )

            # 4. Validate forward triggers
            for trigger_id in metadata.template.controller.triggers:
                trigger_metadata = await self.store.find_analytic(trigger_id)
                if not trigger_metadata:
                    raise ValueError(f"Triggered analytics {trigger_id} not found")

                # Build available inputs for triggered analytics
                triggered_pipeline_inputs = pipeline_inputs.copy()
                triggered_pipeline_inputs.update(
                    field.name for field in metadata.template.input_spec.fields
                )
                triggered_pipeline_inputs.update(
                    field.name for field in metadata.template.output_spec.fields
                )

                # Use the same validation method for consistency
                try:
                    DependencyValidator.validate_dependency_fields(
                        trigger_metadata,
                        metadata,
                        triggered_pipeline_inputs
                    )
                except ValueError as e:
                    raise ValueError(
                        f"Update would cause analytics '{metadata.id}' to trigger '{trigger_id}' "
                        f"with incompatible fields: {str(e)}"
                    )

            # 5. Validate impact on analytics that depend on this one
            all_analytics = await self.store.list_analytics()
            dependent_analytics = [
                a for a in all_analytics
                if analytics_id in a.template.controller.dependsOn
            ]

            # For each dependent, validate that our output changes won't break them
            for dependent in dependent_analytics:
                # Get the accumulated pipeline inputs up to the dependent
                dependent_pipeline_inputs = set(pipeline_inputs)

                # Add our new outputs
                dependent_pipeline_inputs.update(
                    field.name for field in metadata.template.output_spec.fields
                )

                try:
                    DependencyValidator.validate_dependency_fields(
                        dependent,
                        metadata,
                        dependent_pipeline_inputs
                    )
                except ValueError as e:
                    raise ValueError(
                        f"Update would break dependent analytics {dependent.id}: {str(e)}"
                    )

            # 6. Validate impact on analytics that are triggered by this one
            # Check if any analytics that we used to trigger are now orphaned
            if existing.template.controller.triggers:
                removed_triggers = set(existing.template.controller.triggers) - set(metadata.template.controller.triggers)
                if removed_triggers:
                    # Just a warning - removing triggers doesn't break anything
                    print(f"Warning: Removed triggers: {', '.join(removed_triggers)}")

            # 7. If everything passes, update the analytics
            metadata.updated_at = datetime.utcnow()
            return await self.store.update_analytic(analytics_id, metadata)

        except (ImportError, ValueError) as e:
            raise ValueError(f"Analytics update validation failed: {str(e)}")

    async def delete_analytics(self, analytics_id: str) -> bool:
        analytics = await self.store.find_analytic(analytics_id)
        if not analytics:
            raise ValueError(f"Analytics with ID {analytics_id} not found")

        # Find all analytics that depend on OR are triggered by this one
        all_analytics = await self.store.list_analytics()
        dependent_analytics = [
            analytic for analytic in all_analytics
            if analytics_id in analytic.template.controller.dependsOn or
               analytics_id in analytic.template.controller.triggers
        ]

        if dependent_analytics:
            # Create detailed error message listing all dependents
            backward_deps = [a for a in dependent_analytics if analytics_id in a.template.controller.dependsOn]
            forward_deps = [a for a in dependent_analytics if analytics_id in a.template.controller.triggers]

            error_parts = [f"Cannot delete analytics {analytics_id}:"]

            if backward_deps:
                error_parts.append("\nDepends on this analytics:")
                error_parts.extend([f"- {a.id} ({a.name})" for a in backward_deps])

            if forward_deps:
                error_parts.append("\nTriggered by this analytics:")
                error_parts.extend([f"- {a.id} ({a.name})" for a in forward_deps])

            error_parts.append("\nPlease update or delete the dependent analytics first.")

            raise ValueError("\n".join(error_parts))

        # Check if this analytics has any dependencies or triggers itself
        if analytics.template.controller.dependsOn or analytics.template.controller.triggers:
            deps_str = ', '.join(analytics.template.controller.dependsOn) if analytics.template.controller.dependsOn else "none"
            triggers_str = ', '.join(analytics.template.controller.triggers) if analytics.template.controller.triggers else "none"
            print(f"Warning: Deleting analytics {analytics_id} which depends on: {deps_str} and triggers: {triggers_str}")

        # Proceed with deletion
        return await self.store.delete_analytic(analytics_id)

    async def get_pipeline_input_model(self, analytics_id: str) -> type[BaseModel]:
        """Get the input model for the first analytics in the pipeline"""

        # Build dependency chain (similar to what we do in create_execution_graph)
        visited = set()
        analytics_order = []

        async def traverse_dependencies(current_id: str):
            current_metadata = await self.get_analytics(current_id)
            if not current_metadata:
                raise ValueError(f"Analytics {current_id} not found")

            if current_id in visited:
                return

            visited.add(current_id)

            for dep_id in current_metadata.template.controller.dependsOn:
                await traverse_dependencies(dep_id)

            analytics_order.append(current_id)

        # Build the order of execution
        await traverse_dependencies(analytics_id)

        if len(analytics_order) < 1:
            raise ValueError("Could not determine analytics execution order")

        # Get the first analytics in the chain
        first_analytics_id = analytics_order[0]
        first_analytics = await self.get_analytics(first_analytics_id)
        if (first_analytics is None):
            raise ValueError("Could not determine analytics execution order")
        # Get its input model
        plugin_class, specs = PluginValidator.validate_module_import(
            first_analytics.template.runtime.config["module_path"]
        )

        return plugin_class.get_input_model()
