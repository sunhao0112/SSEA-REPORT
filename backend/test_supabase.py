#!/usr/bin/env python3
"""
Supabase连接测试脚本
测试数据库连接和基本操作
"""

import asyncio
import sys
import os
from datetime import datetime

# 添加backend目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__)))

from database import get_supabase, db_service

async def test_connection():
    """测试Supabase连接"""
    print("正在测试Supabase连接...")

    try:
        # 获取客户端
        client = get_supabase()
        print("Supabase客户端创建成功")

        # 测试简单查询
        response = client.table("upload_records").select("*").limit(1).execute()
        print("数据库连接测试成功")
        print(f"upload_records表查询结果: {len(response.data)} 条记录")

        return True

    except Exception as e:
        print(f"连接测试失败: {str(e)}")
        return False

async def test_crud_operations():
    """测试基本CRUD操作"""
    print("\n正在测试CRUD操作...")

    try:
        # 测试插入
        test_data = {
            "filename": "test.csv",
            "file_path": "/test/test.csv",
            "file_size": 1024,
            "upload_time": datetime.now().isoformat(),
            "status": "uploaded"
        }

        result = await db_service.insert_data("upload_records", test_data)
        print(f"插入测试成功: {result}")

        # 获取插入的记录ID
        record_id = result.get('id')

        # 测试查询
        records = await db_service.get_data("upload_records", {"id": record_id})
        print(f"查询测试成功: 找到 {len(records)} 条记录")

        # 测试更新
        update_data = {"status": "processing"}
        updated = await db_service.update_data("upload_records", update_data, {"id": record_id})
        print(f"更新测试成功: {updated}")

        # 测试删除
        deleted = await db_service.delete_data("upload_records", {"id": record_id})
        print(f"删除测试成功: 删除了 {len(deleted)} 条记录")

        return True

    except Exception as e:
        print(f"CRUD操作测试失败: {str(e)}")
        return False

async def test_models():
    """测试数据模型"""
    print("\n正在测试数据模型...")

    try:
        from models import UploadRecord, ProcessingStatus

        # 测试UploadRecord模型
        upload_data = {
            "filename": "model_test.csv",
            "file_path": "/test/model_test.csv",
            "file_size": 2048,
            "status": "uploaded"
        }

        # 创建记录
        upload_record = await UploadRecord.create(upload_data)
        print(f"UploadRecord创建成功: ID {upload_record.id}")

        # 测试ProcessingStatus模型
        status_data = {
            "upload_id": upload_record.id,
            "current_step": "upload",
            "status": "processing",
            "progress": 0.0,
            "message": "开始处理"
        }

        processing_status = await ProcessingStatus.create(status_data)
        print(f"ProcessingStatus创建成功: ID {processing_status.id}")

        # 查询测试
        found_record = await UploadRecord.get_by_id(upload_record.id)
        print(f"模型查询测试成功: {found_record.filename}")

        # 清理测试数据
        await db_service.delete_data("processing_status", {"id": processing_status.id})
        await db_service.delete_data("upload_records", {"id": upload_record.id})
        print("测试数据清理完成")

        return True

    except Exception as e:
        print(f"数据模型测试失败: {str(e)}")
        return False

async def main():
    """主测试函数"""
    print("开始Supabase数据库测试")
    print("=" * 50)

    # 测试连接
    if not await test_connection():
        print("\n连接测试失败，请检查Supabase配置")
        return False

    # 测试CRUD操作
    if not await test_crud_operations():
        print("\nCRUD操作测试失败")
        return False

    # 测试数据模型
    if not await test_models():
        print("\n数据模型测试失败")
        return False

    print("\n所有测试通过！Supabase配置正确")
    print("=" * 50)
    return True

if __name__ == "__main__":
    # 运行测试
    success = asyncio.run(main())
    sys.exit(0 if success else 1)