from langchain.chat_models import init_chat_model
from app.conf.app_config import app_config

llm = init_chat_model(
    model=app_config.llm.model_name,
    api_key= app_config.llm.api_key,
    temperature=0, # 温度参数
    base_url=app_config.llm.base_url,
    model_provider=app_config.llm.model_provider,
)