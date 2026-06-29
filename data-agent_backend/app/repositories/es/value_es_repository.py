from elasticsearch import AsyncElasticsearch
from app.models.es.value_info_es import ValueInfoEs

class ValueESRepository:
    """ es全文搜索操作的持久层类: 对字段取值进行保存和全文检索 """
    es_index_name = "data_agent_values2"

    es_index_mappings = {
        "dynamic": False,
        "properties": {
            "id": {"type": "keyword"},
            "value": {"type": "text", "analyzer": "standard", "search_analyzer": "standard"},
            "type": {"type": "keyword"},
            "column_id": {"type": "keyword"},
            "column_name": {"type": "keyword"},
            "table_id": {"type": "keyword"},
            "table_name": {"type": "keyword"},
        }
    }

    def __init__(self, client: AsyncElasticsearch):
        self.client = client

    async def ensure_index(self):
        """
        确保字段值存储集合存在（不存在则创建）
        """
        if not await self.client.indices.exists(index=self.es_index_name):
            await self.client.indices.create(
                index=self.es_index_name,
                mappings=self.es_index_mappings
            )

    async def upsert_values(self, value_infos: list[ValueInfoEs], batch_size: int = 20):
         """ 保存数据到ES """
         for i in range(0, len(value_infos), batch_size):
             batch_value_infos = value_infos[i:i + batch_size]
             operations = []
             for value_info in batch_value_infos:
                 operations.append({
                     "index": {
                         "_index": self.es_index_name
                     }
                 })
                 operations.append(value_info)
             # 保存批次数据
             await self.client.bulk(
                 operations=operations,
             )

    async def search(self, keyword: str):
        """ 根据关键字匹配字段取值（索引不存在时返回空列表） """
        try:
            resp = await self.client.search(
                index=self.es_index_name,
                query={
                    "match": {
                        "value": keyword
                    }
                },
            )
            return [re["_source"] for re in resp["hits"]["hits"]]
        except Exception as e:
            from elasticsearch import NotFoundError
            if isinstance(e, NotFoundError):
                return []
            raise