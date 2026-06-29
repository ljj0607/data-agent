from typing import TypedDict

from app.models.es.value_info_es import ValueInfoEs
from app.models.qdrant.column_info_qdrant import ColumnInfoQdrant
from app.models.qdrant.metric_info_qdrant import MetricInfoQdrant


# 列信息封装实体
class ColumnInfoState(TypedDict):
    name: str
    type: str
    role: str
    examples: list
    description: str
    alias: list[str]

# 表信息封装实体
class TableInfoState(TypedDict):
    name: str
    role: str
    description: str
    columns: list[ColumnInfoState]


# 指标信息封装实体
class MetricInfoState(TypedDict):
    name: str
    description: str
    relevant_columns: list[str]
    alias: list[str]

# 日期时间信息封装实体
class DateInfoState(TypedDict):
    date: str
    weekday: str
    quarter: str

# 数据库环境信息封装实体
class DBInfoState(TypedDict):
    version: str
    dialect: str

# Agent总结状态封装实体
class DataAgentState(TypedDict):
    query: str # 用户的查询
    keywords: list[str] # 提取关键字列表
    recall_columns: list[ColumnInfoQdrant] # 召回列信息列表
    recall_metric: list[MetricInfoQdrant] # 召回指标信息列表
    recall_values: list[ValueInfoEs] # 召回值信息列表
    table_infos: list[TableInfoState] # 表信息列表
    metric_infos: list[MetricInfoState] # 指标信息列表
    date_info: DateInfoState # 日期时间信息
    db_info: DBInfoState # 数据库环境信息
    sql: str # 生成的SQL
    error: str # 错误信息,根据state中是否存在错误信息，可以进行流程执行
