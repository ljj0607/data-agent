import json
from langgraph.runtime import Runtime
from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState, TableInfoState, ColumnInfoState, MetricInfoState
from app.core.log import logger
from app.models.es.value_info_es import ValueInfoEs
from app.models.mysql.column_info_mysql import ColumnInfoMySQL
from app.models.mysql.table_info_mysql import TableInfoMySQL
from app.models.qdrant.column_info_qdrant import ColumnInfoQdrant
from app.models.qdrant.metric_info_qdrant import MetricInfoQdrant

async def merge_retrieved_info(state:DataAgentState,runtime:Runtime[DataAgentContext]):
    """
        合并多路召回的节点
        步骤：
        1、从 state 获取召回字段、指标、取值信息
        2、根据指标关联字段，补充缺失的字段信息（从 mysql 查）
        3、根据取值关联字段，补充缺失的字段信息并添加示例值
        4、按表 ID 分组字段
        5、遍历每张表，补充表中缺失的字段（主外键等）
        6、装换字段、指标信息为 state 结构并返回
    """
    writer = runtime.stream_writer
    writer({"stage": "合并召回信息"})

    try:
        recall_columns: list[ColumnInfoQdrant] = state["recall_columns"] # 召回的字段信息
        recall_metrics: list[MetricInfoQdrant] = state["recall_metric"] # 召回的指标信息
        recall_values: list[ValueInfoEs] = state["recall_values"] # 召回的取值信息
        table_infos: list[TableInfoState] = [] # 创建表信息列表封装数据
        meta_mysql_repository = runtime.context["meta_mysql_repository"]
        retrieved_column_maps:dict[str,ColumnInfoQdrant]={recall_column["id"]: recall_column for recall_column in recall_columns}  # 条件召回字段结构

        # 1、根据召回指标对应字段，补充设计的字段信息
        for recall_metric in recall_metrics:
            for relevant_column in recall_metric["relevant_columns"]:
                if relevant_column not in retrieved_column_maps:
                    column_info_mysql: ColumnInfoMySQL = await meta_mysql_repository.get_column_info_by_id(
                        relevant_column)
                    retrieved_column_maps[relevant_column] = _convert_column_info_from_mysql_to_qdrant(column_info_mysql)


        # 2.根据召回字段取值，补充涉及到的字段取值对应的字段信息
        for recall_value in recall_values:
            column_id = recall_value["column_id"]
            column_value = recall_value["value"]

            if column_id not in retrieved_column_maps:
                column_info_mysql: ColumnInfoMySQL = await meta_mysql_repository.get_column_info_by_id(column_id)
                retrieved_column_maps[column_id] = _convert_column_info_from_mysql_to_qdrant(column_info_mysql)

            if column_value not in retrieved_column_maps[column_id]["examples"]:
                retrieved_column_maps[column_id]["examples"].append(column_value)

        # 3、划分字段以表为单位的结构
        retrieved_table_maps: dict[str, list[ColumnInfoQdrant]] = {}
        for column_info in retrieved_column_maps.values():
            table_id = column_info["table_id"]
            if table_id not in retrieved_table_maps:
                retrieved_table_maps[table_id]=[]
            retrieved_table_maps[table_id].append(column_info)

        # 4、遍历表字段结构数据，添加主外键数据
        for table_id, columns_list in retrieved_table_maps.items():
            column_infos: list[ColumnInfoMySQL] = await meta_mysql_repository.get_column_infos_by_table_id(table_id)
            column_ids: list[str] = [columns["id"] for columns in columns_list]

            for column_info in column_infos:
                column_id = column_info.id
                if column_id not in column_ids:
                    columns_list.append(_convert_column_info_from_mysql_to_qdrant(column_info))

            table_info_mysql:TableInfoMySQL = await meta_mysql_repository.get_table_info_by_id(table_id)
            columns = [_convert_column_info_from_qdrant_to_state(column) for column in columns_list]
            table_info = TableInfoState(
                name=table_info_mysql.name,
                role=table_info_mysql.role,
                description=table_info_mysql.description,
                columns=columns
            )
            table_infos.append(table_info)

        logger.info(f"合并召回表信息成功：{table_infos}")
        # 5.转换指标信息
        metric_infos: list[MetricInfoState] = [_convert_metric_info_form_qdrant_to_state(recall_metric) for
                                               recall_metric in recall_metrics]
        logger.info(f"合并召回指标信息成功:{metric_infos}")

        return {"table_infos":table_infos,"metric_infos":metric_infos}
    except Exception as e:
        logger.error(f"合并召回信息异常:{str(e)}")
        raise

def _convert_column_info_from_mysql_to_qdrant(column_info_mysql):
    return ColumnInfoQdrant(
        id=column_info_mysql.id,
        name=column_info_mysql.name,
        description=column_info_mysql.description,
        role=column_info_mysql.role,
        type=column_info_mysql.type,
        examples=column_info_mysql.examples,
        table_id=column_info_mysql.table_id,
        alias=column_info_mysql.alias
    )

def _convert_column_info_from_qdrant_to_state(column:ColumnInfoQdrant)->ColumnInfoState:
    return ColumnInfoState(
        name=column['name'],
        type=column['type'],
        role=column["role"],
        examples=column["examples"],
        description=column["description"],
        alias=column["alias"]
    )

def _convert_metric_info_form_qdrant_to_state(recall_metric:MetricInfoQdrant):
    return MetricInfoState(
        name=recall_metric['name'],
        description=recall_metric["description"],
        relevant_columns=recall_metric["relevant_columns"],
        alias=recall_metric["alias"]
    )