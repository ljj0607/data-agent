import asyncio
import sys
import uuid
from pathlib import Path
from loguru import logger
from app.conf.app_config import app_config
from app.core.context import get_request_id, set_request_id

# 配置日志格式
log_format = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<magenta>request_id - {extra[request_id]}</magenta> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)


def inject_request_id(record):
    """
    Loguru 日志补丁函数：为日志记录对象注入 request_id
    """
    try:
        # 尝试从上下文变量中获取 request_id
        request_id = get_request_id()
    except Exception as e:
        # 如果获取失败，生成 UUID4 作为兜底
        request_id = str(uuid.uuid4())
    record["extra"]["request_id"] = request_id


def setup_logger():
    """
    配置并返回带 request_id 补丁的 logger
    """
    # 移除默认的控制台输出
    logger.remove()

    # 配置控制台输出
    if app_config.logging.console.enable:
        logger.add(
            sink=sys.stdout,
            level=app_config.logging.console.level,
            format=log_format
        )

    # 配置文件输出
    if app_config.logging.file.enable:
        path = Path(app_config.logging.file.path)
        path.mkdir(parents=True, exist_ok=True)
        logger.add(
            sink=path / "app.log",
            level=app_config.logging.file.level,
            format=log_format,
            rotation=app_config.logging.file.rotation,
            retention=app_config.logging.file.retention,
            encoding="utf-8"
        )

    # 在配置完成后应用 patch
    return logger.patch(inject_request_id)


# 创建最终的 logger 实例
logger = setup_logger()

if __name__ == '__main__':
    async def graph(request: str):
        """
        模拟图处理函数
        """
        # 因为 get_request_id 需要传入 request_id 参数，我们直接使用 request
        request_id = get_request_id(request)  # 传入 request 作为参数
        logger.info(f"Processing graph for: {request}")
        logger.info(f"Current request_id: {request_id}")


    async def req1():
        """
        模拟请求1
        """
        set_request_id("111111111")
        await asyncio.sleep(1)
        await graph("request-1")


    async def req2():
        """
        模拟请求2
        """
        set_request_id("2222222222")
        await asyncio.sleep(1)
        await graph("request-2")


    async def main():
        """
        主函数：并发执行两个请求
        """
        await asyncio.gather(req1(), req2())


    # 运行主函数
    asyncio.run(main())