"""
主控制脚本 - 简化版
"""
import sys
import argparse
import subprocess
from pathlib import Path

def run_script(script_name: str, args: list = None):
    """运行指定脚本"""
    script_path = Path(__file__).parent / f"{script_name}.py"
    
    if not script_path.exists():
        print(f"✗ 脚本不存在: {script_name}.py")
        return False
    
    cmd = ["python", str(script_path)]
    if args:
        cmd.extend(args)
    
    try:
        result = subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ 脚本执行失败: {script_name}, 退出码: {e.returncode}")
        return False
    except FileNotFoundError:
        print(f"✗ 未找到Python解释器")
        return False

def show_workflow():
    """显示工作流程"""
    print("\n" + "="*60)
    print("医疗知识图谱系统 - 执行流程")
    print("="*60)
    print()
    print("📋 完整流程:")
    print("  1. 数据库初始化     → python scripts/manage.py setup-db")
    print("  2. 构建公有层图谱    → python scripts/manage.py build-umls")
    print("  3. 构建私有层图谱    → python scripts/manage.py build-private --pdf-dir /path/to/pdfs")
    print("  4. 连接图谱层       → python scripts/manage.py connect")
    print("  5. 开始检索         → python scripts/manage.py query --interactive")
    print()
    print("🚀 快速开始（如果系统已就绪）:")
    print("  python scripts/manage.py query --interactive")
    print("  python scripts/manage.py start-api")
    print()
    print("📊 添加新数据:")
    print("  python scripts/manage.py add-data --notepad '患者信息...'")
    print("="*60)

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="医疗知识图谱系统管理")
    parser.add_argument("command", nargs="?", choices=[
        "setup-db", "build-umls", "build-private", "connect", "build-all",
        "add-data", "query", "start-api", "workflow"
    ], help="要执行的命令")
    parser.add_argument("args", nargs="*", help="传递给命令的参数")
    
    args = parser.parse_args()
    
    # 显示工作流程
    if not args.command or args.command == "workflow":
        show_workflow()
        return True
    
    # 命令映射
    command_map = {
        "setup-db": "setup_database",
        "build-umls": "build_kg",
        "build-private": "build_kg", 
        "connect": "build_kg",
        "build-all": "build_kg",
        "add-data": "add_data",
        "query": "run_retrieval",
        "start-api": "start_api"
    }
    
    script_name = command_map[args.command]
    
    # 为特定命令添加默认参数
    if args.command == "build-umls":
        script_args = ["--umls-only"] + args.args
    elif args.command == "build-private":
        script_args = ["--private-only"] + args.args
    elif args.command == "connect":
        script_args = ["--connect-only"] + args.args
    elif args.command == "build-all":
        script_args = args.args
    else:
        script_args = args.args
    
    print(f"执行命令: {args.command}")
    print(f"脚本: {script_name}.py")
    print(f"参数: {' '.join(script_args) if script_args else '无'}")
    print("-" * 50)
    
    success = run_script(script_name, script_args)
    
    if success:
        print("✓ 命令执行成功")
        return True
    else:
        print("✗ 命令执行失败")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)