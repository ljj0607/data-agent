from app.clients.embedding_client_manager import embedding_client_manager
from app.clients.es_client_manager import es_client_manager
from app.clients.mysql_client_manager import meta_mysql_client_manager, dw_mysql_client_manager
from app.clients.qdrant_client_manager import qdrant_client_manager
from app.conf.meta_config import meta_config
from app.repositories.es.value_es_repository import ValueESRepository
from app.repositories.mysql.dw_mysql_repository import DWMysqlRepository
from app.repositories.mysql.meta_mysql_repository import MetaMysqlRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository
from app.core.log import logger
from app.services.meta_knowledge_service import MetaKnowledgeService


async def build():
    """ 初始化各个客户端管理器 """
    meta_mysql_client_manager.init()
    dw_mysql_client_manager.init()
    qdrant_client_manager.init()
    embedding_client_manager.init()
    es_client_manager.init()

    try:
        # 创建session对象
        async with (
            meta_mysql_client_manager.session_factory() as meta_session,
            dw_mysql_client_manager.session_factory() as dw_session
        ):
            # 创建持久层对象
            meta_mysql_repository = MetaMysqlRepository(meta_session) # meta
            dw_mysql_repository = DWMysqlRepository(dw_session) # dw
            column_qdrant_repository = ColumnQdrantRepository(qdrant_client_manager.client)
            value_es_repository = ValueESRepository(es_client_manager.client) # 字段取值
            metric_qdrant_repository = MetricQdrantRepository(qdrant_client_manager.client)

            # 创建业务层对象
            meta_knowledge_service = MetaKnowledgeService(
                dw_mysql_repo=dw_mysql_repository,  # dw数据库
                meta_mysql_repo=meta_mysql_repository, # meta数据库
                column_qdrant_repo=column_qdrant_repository, # 存储字段向量的集合
                value_es_repo=value_es_repository, # 字段值存储集合
                metric_qdrant_repo=metric_qdrant_repository, # 指标信息向量化
                embedding_client=embedding_client_manager.client,  # 文本向量化
            )

            # 启动构建元数据知识库的业务流程
            await meta_knowledge_service.build(meta_config)
    except Exception as e:
        logger.error(f"构建元数据知识库出错: {str(e)}")
        raise e
    finally:
        # 关闭客户端管理器
        await meta_mysql_client_manager.close()
        await dw_mysql_client_manager.close()
        await qdrant_client_manager.close()
        await es_client_manager.close()

if __name__ =="__main__":
    import asyncio
    asyncio.run(build())