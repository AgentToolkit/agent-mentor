from collections.abc import Sequence
from datetime import datetime
from typing import Any

from opensearchpy import AsyncOpenSearch, ConflictError, NotFoundError
from opensearchpy.helpers import async_bulk, async_streaming_bulk

from .store_config import StoreConfig
from .store_interface import (
    BaseStore,
    DuplicateKeyException,
    M,
    QueryFilter,
    QueryOperator,
    SortOrder,
    StoreFactory,
)


class OpenSearchStoreConfig(StoreConfig):
    """OpenSearch-specific configuration"""
    index_name: str
    id_field: str = "element_id"
    mappings: dict[str, Any] | None = None
    settings: dict[str, Any] | None = None
    tenant_id: str
    use_field_aliases: bool = True


class OpenSearchStore(BaseStore[M]):
    def __init__(
        self,
        os_client: AsyncOpenSearch,
        model_class: type[M],
        index_name: str,
        id_field: str,
        tenant_id: str,
        soft_delete: bool = False,
        use_field_aliases: bool = True
    ):
        super().__init__(use_field_aliases=use_field_aliases)
        self.os_client = os_client
        self.model_class = model_class
        self.index_name = index_name
        self.id_field = id_field
        self.tenant_id = tenant_id
        self.soft_delete = soft_delete

    async def initialize(self, mappings: dict[str, Any] | None = None, settings: dict[str, Any] | None = None) -> None:
        """
        Create the index in OpenSearch if it does not exist.
        Apply mappings/settings if provided.
        """
        exists = await self.os_client.indices.exists(index=self.index_name)
        if not exists:
            body = {}
            if settings:
                body["settings"] = settings
            if mappings:
                body["mappings"] = mappings

            # Create index
            await self.os_client.indices.create(index=self.index_name, body=body)

    def _construct_model(self, data: dict[str, Any], model_class: type[M]) -> M:
        """Construct a model instance from dictionary data"""
        if 'type' in data:
            del data['type']
        if 'tenant_id' in data:
            del data['tenant_id']
        return model_class(**data)

    def _translate_query_filter(self, field:str, filter: QueryFilter) -> Any:
        """Translates QueryFilter to OpenSearch query DSL"""
        if filter.operator == QueryOperator.EQUAL:
            return {"term": {f"{field}": filter.value}}
        elif filter.operator in (QueryOperator.GREATER_EQUAL, QueryOperator.LESS_EQUAL):
            # Format datetime to ISO format without timezone info
            value = filter.value
            if isinstance(value, datetime):
                value = value.isoformat()

            range_op = "gte" if filter.operator == QueryOperator.GREATER_EQUAL else "lte"
            return {"range": {field: {range_op: value}}}
        elif filter.operator == QueryOperator.ARRAY_CONTAINS:
            # For checking if an array field contains a specific value
            return {"match": {f"{field}": filter.value}}
        elif filter.operator == QueryOperator.EQUALS_MANY:
            # For checking if field contains a value from within an array
            return {"terms": {f"{field}": filter.value}}

        raise ValueError(f"Unsupported operator: {filter.operator}")

    @classmethod
    def clean_dict_keys(cls, obj):
        if isinstance(obj, dict):
            return {
                key.replace('..', '_').replace(' ', '_').strip(): cls.clean_dict_keys(value)
                for key, value in obj.items()
            }
        elif isinstance(obj, list):
            return [cls.clean_dict_keys(item) for item in obj]
        else:
            return obj

    async def store(self, data: M, type_info: type[M] | None = None) -> str:
        """Store a single document"""
        doc = OpenSearchStore.clean_dict_keys({
            **data.model_dump(by_alias=self.use_field_aliases),
            'tenant_id': self.tenant_id,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        })

        if type_info:
            doc['type'] = type_info.__name__

        unique_field = self.id_field
        unique_value = doc.get(unique_field)
        document_id = f"{self.tenant_id}_{unique_value}"


        try:
            # Store the document
            result = await self.os_client.create(
                index=self.index_name,
                id=document_id,
                body=doc,
                refresh="wait_for",
                timeout="30s",
                request_timeout=30
            )
            return result["_id"]
        except ConflictError:
            # OpenSearch raises ConflictError for 409
            raise DuplicateKeyException(
                f"Duplicate document detected for {unique_field}: {unique_value}"
            )
        except Exception:
            import traceback
            print(traceback.format_exc())
            raise

    async def retrieve(
        self,
        id_field: str,
        id_value: Any,
        type_info: type[M] | None = None
    ) -> M | None:
        """
        Retrieve a single document by searching on a specific field.
        """
        query = {
            "bool": {
                "must": [
                    {"term": {f"{id_field}": id_value}},
                    {"term": {"tenant_id": self.tenant_id}}
                ]
            }
        }

        if self.soft_delete:
            # Exclude docs where deleted_at exists
            query["bool"]["must_not"] = [{"exists": {"field": "deleted_at"}}]

        if type_info:
            query["bool"]["must"].append({"term": {"type": type_info.__name__}})

        search_result = await self.os_client.search(
            index=self.index_name,
            body={"query": query, "size": 1}
        )
        hits = search_result["hits"]["hits"]
        if not hits:
            return None

        source = hits[0]["_source"]
        return self._construct_model(source, type_info or self.model_class)

    async def search(
            self,
            query: dict[str, QueryFilter],
            type_info: type[M] | None = None,
            sort_by: dict[str, SortOrder] | None = None,
            skip: int = 0,
            limit: int | None = None,
        ) -> list[M]:
        """Search for documents"""
        if not isinstance(query, dict):
            raise ValueError("The `query` parameter must be a dictionary of key-value pairs.")

        if type_info is None:
            type_info = self.model_class

        # Build must clauses
        must_clauses = [
            {"term": {"tenant_id": self.tenant_id}}
        ]
        for field, filter_value in query.items():
            translated_field = self._translate_field_name(field, type_info)
            translated_value = self._translate_query_filter(translated_field, filter_value)
            must_clauses.append(translated_value)

        # Add type filtering if `type_info` is provided
        if type_info:
            must_clauses.append({"term": {"type": type_info.__name__}})

        # Construct the base query
        os_query = {"bool": {"must": must_clauses}}

        # Add soft-delete filtering if enabled
        if self.soft_delete:
            soft_delete_clause = {"exists": {"field": "deleted_at"}}
            os_query["bool"].setdefault("must_not", []).append(soft_delete_clause)

        # Construct request body
        body = {"query": os_query}

        # Handle pagination
        from_ = skip
        size_ = limit or 10_000  # Default max size

        search_result = await self.os_client.search(
            index=self.index_name,
            body={**body, "from": from_, "size": size_}
        )

        hits = search_result["hits"]["hits"]

        # Convert OpenSearch hits into model instances
        return [self._construct_model(hit["_source"], type_info or self.model_class) for hit in hits]

    async def update(
        self,
        id_field: str,
        id_value: Any,
        data: dict[str, Any],
        type_info: type[M] | None = None,
        upsert: bool = False
    ) -> bool:
        """Update a document"""
        # 1) Search for the doc
        doc = await self.retrieve(id_field, id_value, type_info=type_info)
        if not doc and not upsert:
            return False

        update_data = {
            **data,
            'updated_at': datetime.utcnow()
        }

        # Upsert simulation
        if doc is None and upsert:
            # Create a new model instance from the data
            new_model = self.model_class(**update_data)
            await self.store(new_model, type_info=type_info)
            return True

        # 2) If doc found, get its OpenSearch _id
        query = {
            "bool": {
                "must": [
                    {"term": {f"{id_field}": id_value}},
                    {"term": {"tenant_id": self.tenant_id}}  # ADD THIS LINE
                ]
            }
        }
        if type_info:
            query["bool"]["must"].append({"term": {"type": type_info.__name__}})
        if self.soft_delete:
            query["bool"]["must_not"] = [{"exists": {"field": "deleted_at"}}]

        search_result = await self.os_client.search(
            index=self.index_name,
            body={"query": query, "size": 1}
        )
        hits = search_result["hits"]["hits"]
        if not hits:
            return False

        os_id = hits[0]["_id"]

        # 3) Update the doc
        try:
            await self.os_client.update(
                index=self.index_name,
                id=os_id,
                body={"doc": update_data}
            )
            return True
        except NotFoundError:
            return False

    async def delete(
        self,
        id_field: str,
        id_value: Any,
        type_info: type[M] | None = None
    ) -> bool:
        """Delete a document"""
        # 1) Find the doc's OpenSearch _id
        doc = await self.retrieve(id_field, id_value, type_info=type_info)
        if not doc:
            return False

        # 2) If soft_delete, update the doc with deleted_at
        if self.soft_delete:
            update_data = {
                'deleted_at': datetime.utcnow()
            }
            return await self.update(id_field, id_value, update_data, type_info=type_info)
        else:
            # physically remove from OpenSearch
            query = {
                "bool": {
                    "must": [
                        {"term": {f"{id_field}": id_value}},
                        {"term": {"tenant_id": self.tenant_id}}
                    ]
                }
            }
            if type_info:
                query["bool"]["must"].append({"term": {"type": type_info.__name__}})

            search_result = await self.os_client.search(
                index=self.index_name,
                body={"query": query, "size": 1}
            )
            hits = search_result["hits"]["hits"]
            if not hits:
                return False

            os_id = hits[0]["_id"]
            await self.os_client.delete(index=self.index_name, id=os_id, refresh="wait_for")
            return True

    async def bulk_store(
        self,
        items: Sequence[M],
        type_info: type[M] | None = None,
        ignore_duplicates: bool = False
    ) -> list[str]:
        """
        Store multiple documents in OpenSearch and return their _ids.
        """
        actions = []
        for item in items:
            doc = OpenSearchStore.clean_dict_keys({
                **item.model_dump(by_alias=self.use_field_aliases),
                'tenant_id': self.tenant_id,
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow(),
            })

            if type_info:
                doc['type'] = type_info.__name__

            unique_value = doc.get(self.id_field)
            document_id = f"{self.tenant_id}_{unique_value}"

            action = {
                "_index": self.index_name,
                "_source": doc,
                "_id": document_id,        # Use id_field as _id
            }
            if not ignore_duplicates:
                action["_op_type"] = "create"
            else:
                action["_op_type"] = "index"

            actions.append(action)

        ids = []

        if ignore_duplicates:
            async for success, result in async_streaming_bulk(self.os_client, actions, refresh="wait_for", raise_on_error=False, ignore_status=[409], timeout="30s", request_timeout=30):
                if success:
                    ids.append(result["index"]["_id"])
                else:
                    print(f"Failed to store for INDEX: {self.index_name} ERROR:{result['index'].get('error', {}).get('reason', 'Unknown error')}")
        else:
            async for success, result in async_streaming_bulk(self.os_client, actions, refresh="wait_for", timeout="30s", request_timeout=30):
                if success:
                    ids.append(result["create"]["_id"])
                else:
                   print(f"Failed to store for INDEX: {self.index_name} ERROR:{result['create'].get('error', {}).get('reason', 'Unknown error')}")

        return ids

    async def bulk_update(
        self,
        updates: list[tuple[dict[str, Any], dict[str, Any]]],
        type_info: type[M] | None = None,
        ordered: bool = True
    ) -> int:
        """Update multiple documents"""
        actions = []

        for query_dict, data_dict in updates:
            # Build the filter query
            must_clauses = [
                {"term": {"tenant_id": self.tenant_id}}
            ]
            must_clauses = [{"term": {k: v}} for k, v in query_dict.items()]
            must_not_clauses = [{"exists": {"field": "deleted_at"}}] if self.soft_delete else []

            if type_info:
                must_clauses.append({"term": {"type": type_info.__name__}})

            filter_query = {"bool": {"must": must_clauses}}
            if must_not_clauses:
                filter_query["bool"]["must_not"] = must_not_clauses

            # Search for matching documents
            search_result = await self.os_client.search(
                index=self.index_name,
                body={"query": filter_query, "size": 10_000}
            )
            hits = search_result.get("hits", {}).get("hits", [])

            # Create update actions for matching documents
            for hit in hits:
                os_id = hit["_id"]
                actions.append({
                    "_op_type": "update",
                    "_index": self.index_name,
                    "_id": os_id,
                    "_source": {
                        "doc": {
                            **data_dict,
                            "updated_at": datetime.utcnow()
                        }
                    }
                })

        # Perform the bulk update
        if not actions:
            return 0

        try:
            success_count, errors = await async_bulk(
                self.os_client,
                actions,
                raise_on_error=ordered,
                stats_only=False,
                refresh="wait_for"
            )
            if errors:
                pass  # Handle errors as needed

            return success_count
        except Exception as e:
            raise RuntimeError(f"Bulk update failed: {str(e)}")


class OpenSearchStoreFactory(StoreFactory):
    def __init__(self, os_client: AsyncOpenSearch,initialize_index: bool | None = False):
        self.os_client = os_client
        self.initalize_index = initialize_index

    async def create_store(
        self,
        model_class: type[M],
        config: StoreConfig,
    ) -> BaseStore[M]:
        if not isinstance(config, OpenSearchStoreConfig):
            raise ValueError("OpenSearch store requires OpenSearchStoreConfig")

        store = OpenSearchStore(
            os_client=self.os_client,
            model_class=model_class,
            index_name=config.index_name,
            id_field=config.id_field,
            tenant_id=config.tenant_id,
            soft_delete=config.soft_delete,
            use_field_aliases=config.use_field_aliases
        )
        if self.initalize_index:
            await store.initialize(
                mappings=config.mappings,
                settings=config.settings
            )
        return store
