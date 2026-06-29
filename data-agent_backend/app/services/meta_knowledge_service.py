import uuid
from typing import Optional

from langchain_huggingface import HuggingFaceEndpointEmbeddings
from sqlalchemy.ext.asyncio import AsyncSession

from app.conf.meta_config import MetaConfig, TableConfig, MetricConfig
from app.core.log import logger
from app.models.es.value_info_es import ValueInfoEs
from app.models.mysql.column_info_mysql import ColumnInfoMySQL
from app.models.mysql.column_metric_mysql import ColumnMetricMySQL
from app.models.mysql.metric_info_mysql import MetricInfoMySQL
from app.models.mysql.table_info_mysql import TableInfoMySQL
from app.models.qdrant.column_info_qdrant import ColumnInfoQdrant
from app.models.qdrant.metric_info_qdrant import MetricInfoQdrant
from app.repositories.es.value_es_repository import ValueESRepository
from app.repositories.mysql.dw_mysql_repository import DWMysqlRepository
from app.repositories.mysql.meta_mysql_repository import MetaMysqlRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository

class MetaKnowledgeService:
    """ 构建元数据知识库的业务类 """

    def __init__(self,
                 dw_mysql_repo: DWMysqlRepository,
                 meta_mysql_repo: MetaMysqlRepository,
                 column_qdrant_repo: ColumnQdrantRepository,
                 value_es_repo: ValueESRepository,
                 metric_qdrant_repo: MetricQdrantRepository,
                 embedding_client: HuggingFaceEndpointEmbeddings
                 ):
        self.dw_mysql_repo = dw_mysql_repo
        self.meta_mysql_repo = meta_mysql_repo
        self.column_qdrant_repo = column_qdrant_repo
        self.value_es_repo = value_es_repo
        self.metric_qdrant_repo = metric_qdrant_repo
        self.embedding_client = embedding_client

    async def build(self, config: MetaConfig):
        """ 构建元数据知识库的业务方法 """
        # 1 处理表相关信息数据
        if config.tables:
            # 1.1 保存表信息和字段信息到meta数据库(table_info和column_info)
            column_infos: list[ColumnInfoMySQL] = await self._save_table_infos_to_meta_db(config.tables)
            logger.info("保存表信息到meta数据库成功")

            # 1.2 为字段信息建立向量索引
            await self._save_column_infos_to_qdrant(column_infos)
            logger.info("为字段信息建立向量索引成功")

            # 1.3 为字段取值建立全文索引
            await self._save_value_infos_to_es(config.tables, column_infos)
            logger.info("为字段取值建立全文索引成功")

        # 2 处理指标信息数据
        if config.metrics:
            # 2.1 保存指标信息到meta数据库(metric_info和column_metric)
            metric_infos: list[MetricInfoMySQL] = await self._save_metric_infos_to_meta_db(config.metrics)
            logger.info("保存指标信息到meta数据库成功")

            # 2.2 为指标信息建立向量索引
            await self._save_metric_infos_to_qdrant(metric_infos)

    async def _save_table_infos_to_meta_db(self, tables: list[TableConfig]) ->list[ColumnInfoMySQL]:
        """ 存表信息和字段信息到meta数据库(table_info和column_info) """
        # 创建表信息封装列表
        table_infos: list[TableInfoMySQL] = []
        # 创建字段信息封装列表
        column_infos: list[ColumnInfoMySQL] = []
        # 遍历配置表信息，封装数据对象
        for table in tables:
            # 封装表信息结构对象
            table_info_mysql = TableInfoMySQL(
                id=table.name,
                name=table.name,
                role=table.role,
                description=table.description,
            )
            table_infos.append(table_info_mysql)
            # 查询表中所有字段的类型数据
            column_types: dict[str, str] = await self.dw_mysql_repo.get_column_types(table.name)
            # 遍历当前表中关联的字段列表
            for column in table.columns:
                # 根据表和字段查询字段取值
                column_values: list[str] = await self.dw_mysql_repo.get_column_values(table.name, column.name)
                # 封装字段对象信息
                column_info_mysql = ColumnInfoMySQL(
                    id=f"{table.name}.{column.name}",
                    name=column.name,
                    type=column_types[column.name],
                    role=column.role,
                    examples=column_values,
                    description=column.description,
                    alias=column.alias,
                    table_id=table.name
                )
                column_infos.append(column_info_mysql)
        # 保存表信息到数据库
        # 显式 .begin() 会接管控制权
        # async with .begin() 的模式是安全且推荐的——提交/回滚由上下文管理器自动处理，不会遗漏
        async with self.meta_mysql_repo.session.begin():
            await self.meta_mysql_repo.save_table_infos(table_infos)
            await self.meta_mysql_repo.save_column_infos(column_infos)

        return column_infos

    async def _save_column_infos_to_qdrant(self, column_infos: list[ColumnInfoMySQL]):
        """ 为字段信息建立向量索引 """
        # 确保存储字段的向量集合存在
        await self.column_qdrant_repo.ensure_collection()
        # 定义列表收集封装数据
        points: list[dict] = []
        # 遍历存储所有字段的列表
        for column_info in column_infos:
            # name
            points.append({
                "id": uuid.uuid4(),
                "embedding_text": column_info.name,
                "payload": MetaKnowledgeService._convert_column_info_from_mysql_to_qdrant(column_info)
            })
            # description
            points.append({
                "id": uuid.uuid4(),
                "embedding_text": column_info.description,
                "payload": MetaKnowledgeService._convert_column_info_from_mysql_to_qdrant(column_info)
            })
            # alias
            for alia in column_info.alias:
                points.append({
                    "id": uuid.uuid4(),
                    "embedding_text": alia,
                    "payload": MetaKnowledgeService._convert_column_info_from_mysql_to_qdrant(column_info)
                })
        # 获取所有向量文本
        embedding_texts = [point["embedding_text"] for point in points]
        # 定义批次
        batch_size = 20
        # 定义向量列表
        embeddings: list[list[float]] = []
        # 遍历所有文本呢
        for i in range(0, len(embedding_texts), batch_size):
            # 获取批次文本
            batch_embedding_texts = embedding_texts[i:i + batch_size]
            # 转换向量 list[list[float]]
            batch_embedding = await self.embedding_client.aembed_documents(batch_embedding_texts)
            # 加入向量列表
            embeddings.extend(batch_embedding)
        # 获取所有id
        ids = [point["id"] for point in points]
        # 获取所有的payload
        payloads = [point["payload"] for point in points]
        # 保存字段数据到向量数据库
        await self.column_qdrant_repo.upsert_column_embeddings(ids, embeddings, payloads)

    @staticmethod
    def _convert_column_info_from_mysql_to_qdrant(column_info: ColumnInfoMySQL) ->ColumnInfoQdrant:
        """ 根据字段信息对象生成字段信息的qdrant对象 """
        return ColumnInfoQdrant(
            id=column_info.id,
            name=column_info.name,
            type=column_info.type,
            role=column_info.role,
            examples=column_info.examples,
            alias=column_info.alias,
            table_id=column_info.table_id,
            description=column_info.description
        )

    async def _save_value_infos_to_es(self, tables: list[TableConfig], column_infos: list[ColumnInfoMySQL]):
        """ 为字段取值建立全文索引 """
        # 确保存储的索引存在
        await self.value_es_repo.ensure_index()
        # 定义字段接收数据
        column2sync: dict[str, bool] = {}
        # 获取所有字段的索引情况
        for table in tables:
            for column in table.columns:
                column2sync[f"{table.name}.{column.name}"] = column.sync
        # 定义列表收集所有值数据
        value_infos: list[ValueInfoEs] = []
        # 遍历所有字段列表
        for column_info in column_infos:
            # 根据字段id，获取索引结果
            sync = column2sync[column_info.id]
            # 判断当前字段是否需要建立索引
            if sync:
                # 根据字段查询字段所属取值
                value_list: list[str] = await self.dw_mysql_repo.get_column_values(column_info.table_id,
                                                                                         column_info.name, 10000)
                # 封装全文索引字段取值数据
                for value_info in value_list:
                    # 封装值对象
                    value_info_es = ValueInfoEs(
                        id=f"{column_info.id}.{value_info}",
                        value=value_info,
                        type=column_info.type,
                        column_id=column_info.id,
                        column_name=column_info.name,
                        table_id=column_info.table_id,
                        table_name=column_info.table_id
                    )
                    value_infos.append(value_info_es)
        # 保存取值数据到es
        await self.value_es_repo.upsert_values(value_infos)

    async def _save_metric_infos_to_meta_db(self, metrics: list[MetricConfig]) -> list[MetricInfoMySQL]:
        """ 保存指标信息到meta数据库 """
        # 定义列表接收指标数据
        metric_infos: list[MetricInfoMySQL] = []
        column_metric_infos: list[ColumnMetricMySQL] = []
        for metric in metrics:
            # 封装指标信息对象
            metric_info_mysql = MetricInfoMySQL(
                id=metric.name,
                name=metric.name,
                description=metric.description,
                relevant_columns=metric.relevant_columns,
                alias=metric.alias
            )
            # 添加到列表中
            metric_infos.append(metric_info_mysql)

            for relevant_column in metric.relevant_columns:
                # 封装column_metric信息
                column_metric_mysql = ColumnMetricMySQL(
                    column_id=relevant_column,
                    metric_id=metric.name

                )
                # 添加到列表中
                column_metric_infos.append(column_metric_mysql)
        # 保存到meta数据库
        async with self.meta_mysql_repo.session.begin():
            await self.meta_mysql_repo.save_metric_infos(metric_infos)
            await self.meta_mysql_repo.save_column_metric_infos(column_metric_infos)

        return metric_infos

    async def _save_metric_infos_to_qdrant(self, metric_infos:list[MetricInfoMySQL]):
        """ 为指标信息建立向量索引 """
        await self.metric_qdrant_repo.ensure_collection()
        points = []
        for metric_info in metric_infos:
            points.append({
                "id": uuid.uuid4(),
                "embedding_text": metric_info.name,
                "payload": self._convert_metric_info_from_mysql_to_qdrant(metric_info)
            })
            # description
            points.append({
                "id": uuid.uuid4(),
                "embedding_text": metric_info.description,
                "payload": self._convert_metric_info_from_mysql_to_qdrant(metric_info)
            })
            # alias
            for alia in metric_info.alias:
                points.append({
                    "id": uuid.uuid4(),
                    "embedding_text": alia,
                    "payload": self._convert_metric_info_from_mysql_to_qdrant(metric_info)
                })
        embedding_texts: list[str] = [point["embedding_text"] for point in points]
        # 定义批次
        batch_size = 20
        # 定义向量列表
        embeddings: list[list[float]] = []
        # 遍历所有文本呢
        for i in range(0, len(embedding_texts), batch_size):
            # 获取批次文本
            batch_embedding_texts = embedding_texts[i:i + batch_size]
            # 转换向量 list[list[float]]
            batch_embedding = await self.embedding_client.aembed_documents(batch_embedding_texts)
            # 加入向量列表
            embeddings.extend(batch_embedding)

        # 获取所有id
        ids = [point["id"] for point in points]
        # 获取所有的payload
        payloads = [point["payload"] for point in points]
        # 保存字段数据到向量数据库
        await self.metric_qdrant_repo.upsert_column_embeddings(ids, embeddings, payloads)

    def _convert_metric_info_from_mysql_to_qdrant(self, metric_info: MetricInfoMySQL) -> MetricInfoQdrant:
        """ 根据指标信息对象生成指标信息的qdrant对象 """
        return MetricInfoQdrant(
            id=metric_info.id,
            name=metric_info.name,
            description=metric_info.description,
            relevant_columns=metric_info.relevant_columns,
            alias=metric_info.alias
        )
