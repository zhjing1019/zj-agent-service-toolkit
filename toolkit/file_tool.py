# 文件读写工具 toolkit/file_tool.py
def read_file(file_path: str) -> str:
    """读取文件内容"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"读取文件 {file_path} 时出错: {e}"
    
def write_file(file_path: str, content: str) -> str:
    """写入文本文件"""
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"写入成功，文件路径：{file_path}"
    except Exception as e:
        return f"写入失败：{str(e)}"

# 工具注册
FILE_TOOLS = {
    "read_file": read_file,
    "write_file": write_file
}