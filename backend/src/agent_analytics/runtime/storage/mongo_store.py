from ast import alias
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Type
from motor.motor_asyncio import AsyncIOMotorCollection
from pydantic import BaseModel
from pymongo.errors import DuplicateKeyError, BulkWriteError
from contextlib import asynccontextmanager
from .store_interface import BaseStore, QueryFilter, QueryOperator, StoreFactory, M, SortOrder, DuplicateKeyException
from .store_config import StoreConfig

class MongoStoreConfig(StoreConfig):
    """MongoDB specific configuration"""
    collection_name: str
    indexes: Optional[list] = None
    tenant_id: str
    write_concern: Optional[Dict[str, Any]] = None
    read_preference: Optional[str] = None
   
    
class MongoStore(BaseStore[M]):
    def __init__(
        self,
        collection: AsyncIOMotorCollection,
        model_class: Type[M],
        tenant_id: str,
        soft_delete: bool = False,
        use_field_aliases: bool = False
    ):
        super().__init__(use_field_aliases=use_field_aliases)
        self.collection = collection
        self.model_class = model_class
        self.tenant_id = tenant_id
        self.soft_delete = soft_delete
       

    async def initialize(self, indexes: Optional[List[Any]] = None, **kwargs) -> None:
        """Initialize store with indexes"""
        if indexes:
            await self.collection.create_indexes(indexes)
    
    def _construct_model(self, data: Dict[str, Any], model_class: Type[M]) -> M:
        """Construct a model instance from dictionary data"""
        if 'type' in data:
            del data['type']
        if 'tenant_id' in data:
            del data['tenant_id']
        return model_class(**data)
    
    def _translate_query_filter(self, field: str,value: QueryFilter) -> Any:
        if value.operator == QueryOperator.EQUAL:
            return value.value
        elif value.operator == QueryOperator.GREATER_EQUAL:
            return {"$gte": value.value}
        elif value.operator == QueryOperator.LESS_EQUAL:
            return {"$lte": value.value}
        elif value.operator == QueryOperator.ARRAY_CONTAINS:
            # For MongoDB, to check if an array field contains a value
            return value.value 
        elif value.operator == QueryOperator.EQUALS_MANY:  
            return {"$in": value.value}
        raise ValueError(f"Unsupported operator: {value.operator}")

    async def store(self, data: M, type_info: Optional[Type[M]] = None) -> str:
        """Store a single document"""
        try:
            document = {                
                **data.model_dump(by_alias=self.use_field_aliases), #Check if to use pydantic aliases for field names or not. Right now Mongo doesn't because it cannot handle "." in field names
                'tenant_id': self.tenant_id,
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow(),
            }
            if type_info:
                document['type'] = type_info.__name__                        
        
            result = await self.collection.insert_one(document)
            return str(result.inserted_id)
        except DuplicateKeyError as e:
            raise DuplicateKeyException(f"Duplicate key error: {str(e)}")
   
    async def retrieve(
        self,
        id_field: str,
        id_value: Any,
        type_info: Optional[Type[M]] = None
    ) -> Optional[M]:
        """Retrieve a single document"""
        query = {
            id_field: id_value,
            'tenant_id': self.tenant_id  # ADD THIS LINE
        }
        if type_info:
            query['type'] = type_info.__name__
        if self.soft_delete:
            query['deleted_at'] = {'$exists': False}
        
        result = await self.collection.find_one(query)
        if result:
            return self._construct_model(result, type_info or self.model_class)
        return None


    async def search(
        self,
        query: Dict[str, QueryFilter],
        type_info: Optional[Type[M]] = None,
        sort_by: Optional[Dict[str, SortOrder]] = None,
        skip: int = 0,
        limit: Optional[int] = None,
    ) -> List[M]:
        """Search for documents"""
        if type_info is None:
            type_info = self.model_class

        search_query = {}
        for field, filter_value in query.items():
            translated_field = self._translate_field_name(field, type_info)
            translated_value = self._translate_query_filter(translated_field,filter_value)
            search_query[translated_field] = translated_value

        if type_info:
            search_query['type'] = type_info.__name__
        if self.soft_delete:
            search_query['deleted_at'] = {'$exists': False}
        search_query['tenant_id'] = self.tenant_id

        cursor = self.collection.find(search_query)
        if sort_by:
            sort_params = [(k, v.value) for k, v in sort_by.items()]
            cursor = cursor.sort(sort_params)

        cursor = cursor.skip(skip)
        if limit is not None:
            cursor = cursor.limit(limit)

        results = await cursor.to_list(None)
        return [self._construct_model(result, type_info or self.model_class) for result in results]  

    async def update(
        self,
        id_field: str,
        id_value: Any,
        data: Dict[str, Any],
        type_info: Optional[Type[M]] = None,
        upsert: bool = False
    ) -> bool:
        """Update a document"""
        query = {
            id_field: id_value,
            'tenant_id': self.tenant_id  
        }
        if type_info:
            query['type'] = type_info.__name__
        if self.soft_delete:
            query['deleted_at'] = {'$exists': False}

        update_data = {
            **data,
            'updated_at': datetime.utcnow()
        }

        # Ensure tenant_id doesn't get overwritten
        if 'tenant_id' in update_data:
            del update_data['tenant_id']

        try:
            result = await self.collection.update_one(
                query,
                {'$set': update_data},
                upsert=upsert
            )
            return result.modified_count > 0 or (upsert and result.upserted_id is not None)
        except DuplicateKeyError as e:
            raise DuplicateKeyException(f"Duplicate key error: {str(e)}")

    async def delete(
        self,
        id_field: str,
        id_value: Any,
        type_info: Optional[Type[M]] = None
    ) -> bool:
        """Delete a document"""
        query = {
            id_field: id_value,
            'tenant_id': self.tenant_id  
        }

        if type_info:
            query['type'] = type_info.__name__

        if self.soft_delete:
            result = await self.collection.update_one(
                {**query, 'deleted_at': {'$exists': False}},
                {'$set': {'deleted_at': datetime.utcnow()}}
            )
            return result.modified_count > 0
        else:
            result = await self.collection.delete_one(query)
            return result.deleted_count > 0

    async def bulk_store(
        self,
        items: Sequence[M],
        type_info: Optional[Type[M]] = None,
        ignore_duplicates: bool = False
    ) -> List[str]:
        """Store multiple documents"""
        documents = []
        for item in items:
            doc = {
                **item.model_dump(by_alias=self.use_field_aliases),
                'tenant_id': self.tenant_id, 
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow(),
            }
            if type_info:
                doc['type'] = type_info.__name__
            documents.append(doc)
            
        result = None
        duplicate_ids = None
        try:
            # Set ordered=False to continue insertion after encountering duplicates
            result = await self.collection.insert_many(documents, ordered=(not ignore_duplicates))
        except BulkWriteError as bwe:
            # Filter out duplicate key errors from the error details
            insert_errors = bwe.details['writeErrors']
            duplicate_ids = [e['keyValue']['element_id'] for e in insert_errors if e['code'] == 11000]
            other_errors = [e for e in insert_errors if e['code'] != 11000]
            
            print(f"Successfully inserted: {bwe.details.get('nInserted', 0)} documents")
            print(f"Duplicates skipped: {len(duplicate_ids)}")
            
            if other_errors:
                print(f"Other errors encountered: {len(other_errors)}")
                raise
        finally:
            return_val = []
            if result:
                return_val.extend([str(id_) for id_ in result.inserted_ids])
            if duplicate_ids:
                return_val.extend([str(id_) for id_ in duplicate_ids])
            return return_val


    async def bulk_update(
        self,
        updates: List[tuple[Dict[str, Any], Dict[str, Any]]],
        type_info: Optional[Type[M]] = None,
        ordered: bool = True
    ) -> int:
        """Update multiple documents"""
        operations = []
        for query, data in updates:
            if type_info:
                query['type'] = type_info.__name__
            if self.soft_delete:
                query['deleted_at'] = {'$exists': False}
            query['tenant_id'] = self.tenant_id

            update_data = {
                **data,
                'updated_at': datetime.utcnow()
            }
            
            operations.append({
                'update_one': {
                    'filter': query,
                    'update': {'$set': update_data}
                }
            })

        try:
            result = await self.collection.bulk_write(operations, ordered=ordered)
            return result.modified_count
        except DuplicateKeyError as e:
            raise DuplicateKeyException(f"Duplicate key error in bulk operation: {str(e)}")
        
class MongoStoreFactory(StoreFactory):
    def __init__(self, db):
        self.db = db

    async def create_store(
        self,
        model_class: Type[M],
        config: StoreConfig,
    ) -> MongoStore[M]:
        if not isinstance(config, MongoStoreConfig):
            raise ValueError("MongoDB store requires MongoStoreConfig")
            
        collection = self.db[config.collection_name]
        
        # Apply MongoDB specific configurations
        if config.write_concern:
            collection = collection.with_options(
                write_concern=config.write_concern
            )
        if config.read_preference:
            collection = collection.with_options(
                read_preference=config.read_preference
            )
            
        store = MongoStore(
            collection=collection,
            model_class=model_class,
            tenant_id=config.tenant_id,
            soft_delete=config.soft_delete,
            use_field_aliases=config.use_field_aliases            
        )
        
        if config.indexes:
            await store.initialize(indexes=config.indexes)
            
        return store
