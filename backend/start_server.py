#!/usr/bin/env python3
"""
启动服务器脚本 - 解决时区问题
"""
import os
import sys
import multiprocessing

if __name__ == "__main__":
    # Windows multiprocessing 支持
    multiprocessing.freeze_support()
    
    # 设置时区环境变量
    os.environ['TZ'] = 'Asia/Shanghai'

    # 设置 PYTHONPATH
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, current_dir)

    try:
        # 尝试导入并启动应用
        import uvicorn
        
        print("🚀 启动南海舆情日报生成系统后端服务...")
        print("📍 服务地址: http://localhost:8001")
        print("📖 API文档: http://localhost:8001/docs")
        print("=" * 50)
        
        uvicorn.run(
            "main:app", 
            host="0.0.0.0", 
            port=8001, 
            reload=False,  # 在 Windows 上禁用 reload 避免 multiprocessing 问题
            log_level="info"
        )
        
    except ImportError as e:
        print(f"❌ 导入错误: {e}")
        print("请确保所有依赖都已正确安装")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)