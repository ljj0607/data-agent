# Data Agent Backend

基于 LangGraph 的 Text-to-SQL 智能数据查询服务。用户输入自然语言问题，系统通过多路召回（字段、指标、字段取值）+ LLM 推理自动生成并执行 SQL，返回查询结果。

## 技术栈

| 类别 | 技术 | 说明 |
|------|------|------|
| Web 框架 | FastAPI + Uvicorn | 异步 API 服务，SSE 流式返回 |
| Agent 编排 | LangGraph | 多节点有向图，支持条件分支与并行召回 |
| LLM | DeepSeek V4 Pro（SiliconFlow） | SQL 生成、指标/表过滤、关键字扩展 |
| Embedding | BAAI/bge-large-zh-v1.5 | 1024 维中文向量模型，通过 HuggingFace TEI 部署 |
| 向量数据库 | Qdrant | 字段向量、指标向量存储与召回 |
| 全文搜索 | Elasticsearch | 字段取值全文检索 |
| 关系型数据库 | MySQL 8.0 | meta 库（元数据）+ dw 库（数据仓库） |
| ORM | SQLAlchemy 2.0 (async) | 异步数据库操作 |
| 中文分词 | jieba | 关键字提取 |
| 配置管理 | OmegaConf + YAML | 统一配置加载 |
| 日志 | Loguru | 结构化日志 |
| Python | >= 3.14 | 依赖管理使用 uv |

## 项目结构

```
data-agent_backend/
├── main.py                      # FastAPI 入口，启动 API 服务
├── pyproject.toml               # 项目依赖配置
├── uv.lock                      # 依赖锁定文件
│
├── conf/
│   └── app_config.yaml          # 全局配置（数据库、Qdrant、ES、LLM 等）
│
├── docker/
│   ├── docker-compose.yaml      # 一键启动 MySQL/Qdrant/ES/Kibana/Embedding
│   └── mysql/                   # 数据库初始化 SQL
│       ├── meta.sql             # meta 库建表语句
│       └── dw.sql               # dw 库建表语句
│
├── prompts/                     # LLM Prompt 模板
│   ├── extend_keywords_for_column_recall.prompt
│   ├── extend_keywords_for_metric_recall.prompt
│   ├── extend_keywords_for_value_recall.prompt
│   ├── filter_metric_info.prompt
│   ├── filter_table_info.prompt
│   ├── generate_sql.prompt
│   └── correct_sql.prompt
│
└── app/
    ├── api/                     # API 层
    │   ├── routers/
    │   │   └── query_router.py  # POST /api/query 接口
    │   ├── schemas/
    │   │   └── query_schema.py  # 请求体定义
    │   └── dependencies.py      # FastAPI 依赖注入
    │
    ├── services/                # 业务服务层
    │   ├── query_service.py     # 查询服务（调用 Agent 图）
    │   └── meta_knowledge_service.py  # 元数据知识库构建服务
    │
    ├── agent/                   # LangGraph Agent
    │   ├── graph.py             # 图定义（节点 + 边 + 条件分支）
    │   ├── state.py             # 全局状态 DataAgentState
    │   ├── context.py           # 运行时上下文 DataAgentContext
    │   ├── llm.py               # LLM 实例
    │   └── node/                # 图节点
    │       ├── extract_keywords.py   # 1. jieba 提取关键字
    │       ├── recall_column.py      # 2. 向量召回字段信息
    │       ├── recall_metric.py      # 2. 向量召回指标信息
    │       ├── recall_value.py       # 2. ES 全文检索字段取值
    │       ├── merge_retrieved_info.py  # 3. 合并多路召回结果
    │       ├── filter_metric.py      # 4. LLM 过滤无关指标
    │       ├── filter_table.py       # 4. LLM 过滤无关表
    │       ├── add_extra_context.py  # 5. 补充日期/数据库环境等上下文
    │       ├── generate_sql.py       # 6. LLM 生成 SQL
    │       ├── validata_sql.py       # 7. SQL 语法校验
    │       ├── correct_sql.py        # 7. SQL 修正（校验失败时）
    │       └── execute_sql.py        # 8. 执行 SQL 并返回结果
    │
    ├── repositories/            # 持久层
    │   ├── qdrant/
    │   │   ├── column_qdrant_repository.py  # 字段向量 CRUD
    │   │   └── metric_qdrant_repository.py  # 指标向量 CRUD
    │   ├── es/
    │   │   └── value_es_repository.py       # 字段取值全文检索
    │   └── mysql/
    │       ├── meta_mysql_repository.py     # meta 库元数据操作
    │       └── dw_mysql_repository.py       # dw 库数据查询
    │
    ├── models/                  # 数据模型
    │   ├── qdrant/              # Qdrant payload 结构
    │   ├── es/                  # ES 文档结构
    │   └── mysql/               # MySQL ORM 模型
    │
    ├── clients/                 # 客户端管理器（连接池生命周期）
    │   ├── embedding_client_manager.py
    │   ├── qdrant_client_manager.py
    │   ├── es_client_manager.py
    │   └── mysql_client_manager.py
    │
    ├── conf/
    │   ├── app_config.py        # 配置读取入口
    │   └── meta_config.py       # 元数据构建配置
    │
    ├── core/
    │   ├── lifespan.py          # FastAPI 生命周期管理
    │   ├── context.py           # 请求上下文（request_id）
    │   └── log.py               # 日志配置
    │
    ├── prompt/
    │   └── prompt_loader.py     # Prompt 模板加载器
    │
    └── scripts/
        └── build_meta_knowledge.py  # 构建元数据知识库脚本
```

## Agent 工作流

```
                          ┌─────────────────┐
                          │ extract_keywords │  jieba 分词提取关键字
                          └───────┬─────────┘
                     ┌────────────┼────────────┐
                     ▼            ▼            ▼
              ┌──────────┐ ┌──────────┐ ┌──────────┐
              │recall_   │ │recall_   │ │recall_   │  三路并行召回
              │column    │ │metric    │ │value     │
              └─────┬────┘ └─────┬────┘ └─────┬────┘
                    └────────────┼────────────┘
                                 ▼
                    ┌──────────────────────┐
                    │merge_retrieved_info  │  合并去重
                    └──────────┬───────────┘
                     ┌─────────┴─────────┐
                     ▼                   ▼
              ┌────────────┐      ┌────────────┐
              │filter_     │      │filter_     │  LLM 过滤
              │metric      │      │table       │
              └──────┬─────┘      └──────┬─────┘
                     └────────┬──────────┘
                              ▼
                   ┌────────────────────┐
                   │add_extra_context   │  补充日期/DB 信息
                   └─────────┬──────────┘
                             ▼
                      ┌────────────┐
                      │generate_sql│  LLM 生成 SQL
                      └──────┬─────┘
                             ▼
                      ┌──────────────┐
                      │validata_sql  │  语法校验
                      └──────┬───────┘
                         ┌───┴───┐
                    通过  │       │ 失败
                         ▼       ▼
              ┌────────────┐ ┌────────────┐
              │execute_sql │ │correct_sql │→ execute_sql
              └─────┬──────┘ └────────────┘
                    ▼
                   END
```

```bash
# 导入 meta 库
mysql -h 127.0.0.1 -P 13800 -u root -p < docker/mysql/meta.sql

# 导入 dw 库
mysql -h 127.0.0.1 -P 13800 -u root -p < docker/mysql/dw.sql
```

请求体：

```json
{
  "query": "统计华北地区去年销售总额"
}
```


## 下载后端项目所有依赖

- 进入后端项目目录date-agent-backend下，运行命令：uv sync

## 通过docker安装相关中断件并启动服务
- 启动window版本docker（docker desktop）
- 进入docker_windows目录下执行：docker compose up -d

## 构建知识库

- 运行构建脚本：app/scripts/build_meta_knowledge.py

## 运行后端项目

- 运行启动脚本： main.py
[dw.sql](../../MyFile/%E6%8E%8C%E6%9F%9C%E9%97%AE%E6%95%B0/%E8%B5%84%E6%96%99/docker/docker_linux/mysql/dw.sql)
## 运行前端项目

- 进入前端项目目录date-agent-frontend下，运行：

## 访问测试

- 浏览器上访问： http://127.0.0.1:5173/
- 搜索：相关问题[dw.sql](../../MyFile/%E6%8E%8C%E6%9F%9C%E9%97%AE%E6%95%B0/%E8%B5%84%E6%96%99/docker/docker_linux/mysql/dw.sql)
  - 统计华北地区销售总额
  - 统计2025年各地区销售总[dw.sql](../../MyFile/%E6%8E%8C%E6%9F%9C%E9%97%AE%E6%95%B0/%E8%B5%84%E6%96%99/docker/docker_linux/mysql/dw.sql)额
  - 统计2025年各个商品的销量
  - 统计各地区销量排名前三的商品
