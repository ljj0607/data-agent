from qdrant_client import AsyncQdrantClient, models
from app.conf.app_config import app_config
from app.models.qdrant.metric_info_qdrant import MetricInfoQdrant


class MetricQdrantRepository:
    """  对指标信息进行qdrant向量化操作的持久层类 """
    collection_name: str = "data_agent_metric2"

    def __init__(self, client: AsyncQdrantClient):
        self.client = client


    async def ensure_collection(self):
        """ 确保存储指标向量的集合存在 """

        if not await self.client.collection_exists(self.collection_name):
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(size=app_config.qdrant.embedding_size,distance=models.Distance.COSINE),
            )

    async def upsert_column_embeddings(self, ids:list[str], embeddings:list[list[float]], payloads:list[MetricInfoQdrant],batch_size:int=10):
        """ 保存指标信息到向量数据库 """
        zipped = list(zip(ids, embeddings, payloads))
        for i in range(0, len(zipped), batch_size):
            batch_zipped = zipped[i:i + batch_size]
            # 转换结构为[PointStruct,PointStruct,PointStruct]
            points = [models.PointStruct(
                id=id,
                payload=payload,
                vector=embedding,
            )
                for id, embedding, payload in batch_zipped]
            # 保存向量到qdrant
            await self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )

    async  def search(self, embedding: list[float], limit: int = 10):
        """ 根据指标召回指标向量（集合不存在时返回空列表） """
        try:
            points = await self.client.query_points(
                collection_name=self.collection_name,
                query=embedding,
                score_threshold=0.6,
                limit=limit,
            )
            return [point.payload for point in points.points]
        except Exception:
            return []




