import asyncio
from random import random
from typing import Optional

from app.conf.app_config import app_config, QdrantConfig
from qdrant_client import AsyncQdrantClient, models


class OdrantClientManager:
    """ 向量数据库 """

    def __init__(self, config: QdrantConfig):
        self.config = config
        self.client: Optional[AsyncQdrantClient] = None


    def _get_url(self):
        return f"http://{self.config.host}:{self.config.port}"

    def init(self):
        self.client = AsyncQdrantClient(self._get_url())

    async def close(self):
        await self.client.close()

# 创建向量数据库客户端管理器
qdrant_client_manager = OdrantClientManager(app_config.qdrant)


if __name__ == '__main__':
    import asyncio
    async  def test():
        qdrant_client_manager.init()

        client = qdrant_client_manager.client
        collection_name = "my_collection"

        if await client.collection_exists(collection_name):
            await client.delete_collection(collection_name)

        await client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(size=10, distance=models.Distance.COSINE)
        )

        # 插入数据
        await client.upsert(
            collection_name=collection_name,
            points=[
                models.PointStruct(
                    id=i,
                    payload={
                        "color": "red" if i%2 == 0 else "blue",
                    },
                    # 生成10维随机向量
                    vector=[random() for _ in range(10)],
                )
                for i in range(100)
            ]
        )

        # 搜索向量：查找最相似的 10个向量
        result = await  client.query_points(
            collection_name=collection_name,
            query=[random() for _ in range(10)],  # 生成一个10维随机向量 用于查询
            limit=9,  # 返回的最相似的9个向量
            score_threshold=0.9 # 向量相似度阈值，低于该阈值的向量将被忽略
        )

        print(result.points)
        print(len(result.points))

        await qdrant_client_manager.close()


    asyncio.run(test())

