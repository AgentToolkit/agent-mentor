import os
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from elasticsearch import ApiError, AsyncElasticsearch, NotFoundError
from elasticsearch.helpers import async_bulk, async_streaming_bulk

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

force_single_tenant = os.environ.get('FORCE_SINGLE_TENANT', "false").lower() == "true"

class ElasticSearchStoreConfig(StoreConfig):
    """Elasticsearch-specific configuration"""
    index_name: str
    id_field: str = "element_id"
    mappings: dict[str, Any] | None = None
    settings: dict[str, Any] | None = None
    tenant_id: str
    use_field_aliases: bool = True




class ElasticSearchStore(BaseStore[M]):
    def __init__(
        self,
        es_client: AsyncElasticsearch,
        model_class: type[M],
        index_name: str,
        id_field: str,
        tenant_id: str,
        soft_delete: bool = False,
        use_field_aliases: bool = True,

    ):
        super().__init__(use_field_aliases=use_field_aliases)
        self.es_client = es_client
        self.model_class = model_class
        self.index_name = index_name
        self.id_field = id_field
        self.soft_delete = soft_delete
        self.tenant_id = tenant_id

    async def initialize(self, mappings: dict[str, Any] | None = None, settings: dict[str, Any] | None = None) -> None:
        """
        Create the index in Elasticsearch if it does not exist.
        Apply mappings/settings if provided.
        """
        exists = await self.es_client.indices.exists(index=self.index_name)
        if not exists:
            body = {}
            if settings:
                body["settings"] = settings
            if mappings:
                body["mappings"] = mappings

            # Create index
            await self.es_client.indices.create(index=self.index_name, body=body)


    def _construct_model(self, data: dict[str, Any], model_class: type[M]) -> M:
        """Construct a model instance from dictionary data"""
        if 'type' in data:
            del data['type']
        if 'tenant_id' in data:
            del data['tenant_id']
        return model_class(**data)


    def _translate_query_filter(self, field:str, filter: QueryFilter) -> Any:

        """Translates QueryFilter to Elasticsearch query DSL"""
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
            return {"terms": {f"{field}": filter.value}} # Note the 's' in terms!

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
        doc = ElasticSearchStore.clean_dict_keys({
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
            result = await self.es_client.index(
                index=self.index_name,
                id=document_id,        # Use id_field as _id
                op_type='create',      # Fail atomically on duplicate
                document=doc,
                refresh="wait_for",
                timeout="30s"
            )
            return result["_id"]
        except ApiError as e:
            if e.status_code == 409:  # Conflict = duplicate
                raise DuplicateKeyException(f"Duplicate document detected for {unique_field}: {doc[unique_field]}")
            raise
        except Exception:
            #mappings = await self.es_client.indices.get_mapping(index=self.index_name)
            # print(">>>Current mappings:", mappings)
            # print(">>>Inserted Document:", doc)
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
                ]
            }
        }

        if not force_single_tenant:
            query["bool"]["must"].append({"term": {"tenant_id": self.tenant_id}})

        if self.soft_delete:
            # Exclude docs where deleted_at exists
            query["bool"]["must_not"] = [{"exists": {"field": "deleted_at"}}]

        if type_info:
            query["bool"]["must"].append({"term": {"type": type_info.__name__}})

        search_result = await self.es_client.search(
            index=self.index_name,
            query=query,
            size=1  # Only need one result
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
        must_clauses = []

        if not force_single_tenant:
            must_clauses.append({"term": {"tenant_id": self.tenant_id}})

        for field, filter_value in query.items():
            translated_field = self._translate_field_name(field, type_info)
            translated_value = self._translate_query_filter(translated_field,filter_value)
            must_clauses.append(translated_value)


        # Build the Elasticsearch bool query with must clauses for key-value pairs
        #TODO: check
        # must_clauses = []
        # for key, value in query.items():
        #     #TODO: Add logic to decide when to use keyword
        #     must_clauses.append({"term": {key: str(value)}})


        # Add type filtering if `type_info` is provided
        if type_info:
            must_clauses.append({"term": {"type": type_info.__name__}})

        # Construct the base query
        es_query = {"bool": {"must": must_clauses}}

        # Add type filtering if `type_info` is provided
        # if type_info:
        #     type_clause = {"term": {"type": type_info.__name__}}
        #     es_query["bool"].setdefault("should", []).append(type_clause)

        # Add soft-delete filtering if enabled
        if self.soft_delete:
            soft_delete_clause = {"exists": {"field": "deleted_at"}}
            es_query["bool"].setdefault("must_not", []).append(soft_delete_clause)

        # Construct request body
        body = {"query": es_query}

        # Handle sorting
        # if sort_by:
        #     if not isinstance(sort_by, dict):
        #         raise ValueError("The `sort_by` parameter must be a dictionary of field names and sort orders.")

        #     sort_clauses = []
        #     for field, order in sort_by.items():
        #         if order not in [SortOrder.ASCENDING, SortOrder.DESCENDING]:
        #             raise ValueError(f"Invalid sort order for field '{field}'. Use 'asc' or 'desc'.")

        #         sort_clauses.append({field: {"order": order}})

        #     body["sort"] = sort_clauses


        # TODO: Handle pagination

        from_ = skip
        size_ = limit or 10_000  # Default max size

        search_result = await self.es_client.search(
            index=self.index_name,
            from_=from_,
            size=size_,
            body=body
        )

        hits = search_result["hits"]["hits"]

        # Convert Elasticsearch hits into model instances
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
            # We'll forcibly store it.
            new_model = self.model_class(**update_data)
            await self.store(new_model, type_info=type_info)
            return True

        # 2) If doc found, get its ES _id (not to be confused with doc’s own id_field)
        # We can re-search with a size=1, then extract the _id
        query = {
            "bool": {
                "must": [
                    {"term": {f"{id_field}": id_value}},
                ]
            }
        }
        if not force_single_tenant:
            query["bool"]["must"].append({"term": {"tenant_id": self.tenant_id}})
        if type_info:
            query["bool"]["must"].append({"term": {"type": type_info.__name__}})
        if self.soft_delete:
            query["bool"]["must_not"] = [{"exists": {"field": "deleted_at"}}]

        search_result = await self.es_client.search(
            index=self.index_name,
            query=query,
            size=1
        )
        hits = search_result["hits"]["hits"]
        if not hits:
            return False

        es_id = hits[0]["_id"]

        # 3) Update the doc
        try:
            await self.es_client.update(
                index=self.index_name,
                id=es_id,
                doc={"doc": update_data}
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
        # 1) Find the doc’s ES _id
        doc = await self.retrieve(id_field, id_value, type_info=type_info)
        if not doc:
            return False

        # 2) If soft_delete, update the doc with deleted_at
        if self.soft_delete:
            update_data = {
                'deleted_at': datetime.utcnow()
            }
            # same approach as update

            return await self.update(id_field, id_value, update_data, type_info=type_info, refresh="wait_for")

        else:
            # physically remove from ES
            # We do a similar search to get the ES _id
            query = {
                "bool": {
                    "must": [
                        {"term": {f"{id_field}": id_value}},
                    ]
                }
            }
            if not force_single_tenant:
                query["bool"]["must"].append({"term": {"tenant_id": self.tenant_id}})
            if type_info:
                query["bool"]["must"].append({"term": {"type": type_info.__name__}})

            search_result = await self.es_client.search(
                index=self.index_name,
                query=query,
                size=1
            )
            hits = search_result["hits"]["hits"]
            if not hits:
                return False

            es_id = hits[0]["_id"]

            await self.es_client.delete(index=self.index_name, id=es_id, refresh="wait_for")

            return True

    async def bulk_store(
        self,
        items: Sequence[M],

        type_info: type[M] | None = None,
        ignore_duplicates: bool = False

    ) -> list[str]:
        """
        Store multiple documents in Elasticsearch and return their _ids.
        """
        actions = []
        for item in items:

            doc = ElasticSearchStore.clean_dict_keys({
                **item.model_dump(by_alias=self.use_field_aliases),
                'tenant_id': self.tenant_id,  # ADD THIS LINE
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow(),
            })

            if type_info:
                doc['type'] = type_info.__name__

            unique_value = doc.get(self.id_field)
            document_id = f"{self.tenant_id}_{unique_value}"

            action = {
                "_index": self.index_name,
                "_id": document_id,        # Use id_field as _id
                "_source": doc,
            }

            if not ignore_duplicates:
                action["_op_type"] = "create"  #Fail on duplicate

            actions.append(action)


        ids = []

        if ignore_duplicates:
            async for success, result in async_streaming_bulk(self.es_client, actions, refresh="wait_for", raise_on_error=False, ignore_status=[409], timeout="30s", request_timeout=30):
                if success:
                    ids.append(result["index"]["_id"])  # Retrieve _id from Elasticsearch response
                else:
                    print(f"Failed to store for INDEX: {self.index_name} ERROR:{result['index'].get('error', {}).get('reason', 'Unknown error')}")
        else:
            async for success, result in async_streaming_bulk(self.es_client, actions, refresh="wait_for", timeout="30s", request_timeout=30):
                if success:
                    ids.append(result["create"]["_id"])  # Retrieve _id from Elasticsearch response
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

        # A naive approach is to individually search for each item,
        # then create the update action if found. This can be expensive
        # because each item requires a search. Real usage might rely on
        # known doc IDs or a different approach.

        actions = []

        for query_dict, data_dict in updates:
            # Build the filter query
            must_clauses = [
                {"term": {"tenant_id": self.tenant_id}}  # ADD THIS LINE
            ]
            must_clauses.extend([{"term": {k: v}} for k, v in query_dict.items()])
            must_not_clauses = [{"exists": {"field": "deleted_at"}}] if self.soft_delete else []

            if type_info:
                must_clauses.append({"term": {"type": type_info.__name__}})

            filter_query = {"bool": {"must": must_clauses}}
            if must_not_clauses:
                filter_query["bool"]["must_not"] = must_not_clauses

            # Search for matching documents
            search_result = await self.es_client.search(
                index=self.index_name,
                query=filter_query,
                size=10_000 # TODO
            )
            hits = search_result.get("hits", {}).get("hits", [])

            # Create update actions for matching documents
            for hit in hits:
                es_id = hit["_id"]
                actions.append({
                    "_op_type": "update",
                    "_index": self.index_name,
                    "_id": es_id,
                    "doc": {
                        **data_dict,
                        "updated_at": datetime.utcnow()
                    }
                })

        # Perform the bulk update
        if not actions:
            return 0

        try:
            success_count, errors = await async_bulk(
                self.es_client,
                actions,
                raise_on_error=ordered,
                stats_only=False,
                refresh="wait_for"
            )
            if errors:

                pass

            return success_count
        except Exception as e:
            # Handle unexpected exceptions
            raise RuntimeError(f"Bulk update failed: {str(e)}")

class ElasticSearchStoreFactory(StoreFactory):
    def __init__(self, es_client: AsyncElasticsearch, initialize_index: bool | None = False):
        self.es_client = es_client
        self.initalize_index = initialize_index

    async def create_store(
        self,
        model_class: type[M],
        config: StoreConfig,
    ) -> BaseStore[M]:
        if not isinstance(config, ElasticSearchStoreConfig):
            raise ValueError("Elasticsearch store requires ElasticSearchStoreConfig")

        store = ElasticSearchStore(
            es_client=self.es_client,
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


