from pathlib import Path

def load_prompt(name: str):
    """ 读取 prompt """
    prmpt_file =Path(__file__).parents[2]/"prompts"/f"{name}.prompt"
    return prmpt_file.read_text(encoding="utf-8")