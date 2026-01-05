"""
文件处理工具模块
"""
import os
import logging
from pathlib import Path
from typing import List, Dict, Optional, Union
import mimetypes

logger = logging.getLogger(__name__)

class FileProcessor:
    """文件处理器"""
    
    def __init__(self):
        self.supported_extensions = {
            '.pdf': 'application/pdf',
            '.txt': 'text/plain',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.rtf': 'application/rtf',
            '.md': 'text/markdown'
        }
    
    def get_file_type(self, file_path: Union[str, Path]) -> str:
        """获取文件类型"""
        file_path = Path(file_path)
        extension = file_path.suffix.lower()
        
        if extension in self.supported_extensions:
            return self.supported_extensions[extension]
        
        # 使用mimetypes模块检测
        mime_type, _ = mimetypes.guess_type(str(file_path))
        return mime_type or 'application/octet-stream'
    
    def is_supported_file(self, file_path: Union[str, Path]) -> bool:
        """检查文件是否支持"""
        file_path = Path(file_path)
        extension = file_path.suffix.lower()
        return extension in self.supported_extensions
    
    def get_file_size(self, file_path: Union[str, Path]) -> int:
        """获取文件大小（字节）"""
        try:
            return Path(file_path).stat().st_size
        except OSError:
            return 0
    
    def get_file_info(self, file_path: Union[str, Path]) -> Dict[str, Union[str, int, bool]]:
        """获取文件信息"""
        file_path = Path(file_path)
        
        return {
            'name': file_path.name,
            'path': str(file_path),
            'size': self.get_file_size(file_path),
            'extension': file_path.suffix.lower(),
            'mime_type': self.get_file_type(file_path),
            'is_supported': self.is_supported_file(file_path),
            'exists': file_path.exists()
        }
    
    def list_files(self, directory: Union[str, Path], 
                   recursive: bool = False,
                   extensions: Optional[List[str]] = None) -> List[Path]:
        """列出目录中的文件"""
        directory = Path(directory)
        
        if not directory.exists() or not directory.is_dir():
            logger.warning(f"目录不存在或不是目录: {directory}")
            return []
        
        files = []
        
        if recursive:
            pattern = "**/*"
        else:
            pattern = "*"
        
        for file_path in directory.glob(pattern):
            if file_path.is_file():
                if extensions is None or file_path.suffix.lower() in extensions:
                    files.append(file_path)
        
        return sorted(files)
    
    def find_files_by_pattern(self, directory: Union[str, Path], 
                             pattern: str,
                             recursive: bool = True) -> List[Path]:
        """根据模式查找文件"""
        directory = Path(directory)
        
        if not directory.exists():
            return []
        
        if recursive:
            return list(directory.rglob(pattern))
        else:
            return list(directory.glob(pattern))
    
    def create_directory(self, directory: Union[str, Path]) -> bool:
        """创建目录"""
        try:
            Path(directory).mkdir(parents=True, exist_ok=True)
            logger.info(f"创建目录: {directory}")
            return True
        except OSError as e:
            logger.error(f"创建目录失败: {e}")
            return False
    
    def safe_filename(self, filename: str) -> str:
        """生成安全的文件名"""
        # 移除或替换不安全的字符
        unsafe_chars = '<>:"/\\|?*'
        for char in unsafe_chars:
            filename = filename.replace(char, '_')
        
        # 限制长度
        if len(filename) > 200:
            name, ext = os.path.splitext(filename)
            filename = name[:200-len(ext)] + ext
        
        return filename
    
    def get_relative_path(self, file_path: Union[str, Path], 
                         base_path: Union[str, Path]) -> str:
        """获取相对路径"""
        try:
            file_path = Path(file_path)
            base_path = Path(base_path)
            return str(file_path.relative_to(base_path))
        except ValueError:
            return str(file_path)
    
    def validate_file_path(self, file_path: Union[str, Path]) -> Dict[str, Union[bool, str]]:
        """验证文件路径"""
        file_path = Path(file_path)
        
        result = {
            'valid': True,
            'exists': file_path.exists(),
            'is_file': file_path.is_file(),
            'is_directory': file_path.is_dir(),
            'readable': False,
            'writable': False,
            'error': None
        }
        
        if file_path.exists():
            try:
                # 检查读权限
                result['readable'] = os.access(file_path, os.R_OK)
            except OSError as e:
                result['error'] = f"检查读权限失败: {e}"
                result['valid'] = False
            
            try:
                # 检查写权限
                result['writable'] = os.access(file_path, os.W_OK)
            except OSError as e:
                if not result['error']:
                    result['error'] = f"检查写权限失败: {e}"
                    result['valid'] = False
        
        return result

# 全局文件处理器实例
file_processor = FileProcessor()
