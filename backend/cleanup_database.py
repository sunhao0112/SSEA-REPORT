#!/usr/bin/env python3
"""
数据库清理脚本 - 清理不一致的处理状态记录
"""

import asyncio
import logging
from services.database_service import DatabaseService

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def cleanup_database():
    """清理数据库中的不一致记录"""
    db_service = DatabaseService()

    try:
        # 1. 查找所有处理状态记录
        all_processing = await db_service.supabase.table("processing_status").select("*").execute()
        logger.info(f"发现 {len(all_processing.data)} 条处理状态记录")

        # 2. 查找所有上传记录
        all_uploads = await db_service.supabase.table("upload_records").select("*").execute()
        upload_ids = {record['id'] for record in all_uploads.data}
        logger.info(f"发现 {len(upload_ids)} 条上传记录")

        # 3. 找到孤立的处理状态记录（没有对应的上传记录）
        orphaned_processing = []
        for processing in all_processing.data:
            if processing['upload_id'] not in upload_ids:
                orphaned_processing.append(processing)

        logger.info(f"发现 {len(orphaned_processing)} 条孤立的处理状态记录")

        # 4. 清理孤立记录
        if orphaned_processing:
            for record in orphaned_processing:
                logger.info(f"删除孤立记录: processing_id={record['id']}, upload_id={record['upload_id']}")
                await db_service.supabase.table("processing_status").delete().eq("id", record['id']).execute()

        # 5. 显示当前状态
        remaining = await db_service.supabase.table("processing_status").select("*").execute()
        logger.info(f"清理后剩余 {len(remaining.data)} 条处理状态记录")

        # 6. 显示最近5条记录的映射关系
        if remaining.data:
            recent_records = sorted(remaining.data, key=lambda x: x['id'], reverse=True)[:5]
            logger.info("最近的处理状态记录:")
            for record in recent_records:
                logger.info(f"  processing_id={record['id']} -> upload_id={record['upload_id']}")

        return True

    except Exception as e:
        logger.error(f"清理失败: {str(e)}")
        return False

async def main():
    """主函数"""
    logger.info("开始数据库清理...")

    success = await cleanup_database()

    if success:
        logger.info("✅ 数据库清理完成")
    else:
        logger.error("❌ 数据库清理失败")

if __name__ == "__main__":
    asyncio.run(main())