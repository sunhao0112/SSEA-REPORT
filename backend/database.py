from supabase import create_client, Client
from dotenv import load_dotenv
import os
from typing import Optional

load_dotenv()

# Supabase配置
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("请设置SUPABASE_URL和SUPABASE_ANON_KEY环境变量")

# 创建Supabase客户端
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_supabase() -> Client:
    """获取Supabase客户端实例"""
    return supabase

class SupabaseService:
    """Supabase数据库服务类"""

    def __init__(self):
        self.client = supabase

    async def execute_query(self, table: str, query_builder):
        """执行查询"""
        try:
            response = query_builder.execute()
            return response.data
        except Exception as e:
            print(f"查询执行失败: {str(e)}")
            raise e

    async def insert_data(self, table: str, data: dict):
        """插入数据"""
        try:
            response = self.client.table(table).insert(data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"数据插入失败: {str(e)}")
            raise e

    async def bulk_insert_data(self, table: str, data_list: list):
        """批量插入数据 - 真正的批量操作"""
        try:
            if not data_list:
                return []

            # Supabase支持批量插入，一次性插入所有数据
            response = self.client.table(table).insert(data_list).execute()
            return response.data if response.data else []
        except Exception as e:
            print(f"批量数据插入失败: {str(e)}")
            raise e

    async def update_data(self, table: str, data: dict, filters: dict):
        """更新数据"""
        try:
            query = self.client.table(table).update(data)
            for key, value in filters.items():
                query = query.eq(key, value)
            response = query.execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"数据更新失败: {str(e)}")
            raise e

    async def delete_data(self, table: str, filters: dict):
        """删除数据"""
        try:
            query = self.client.table(table).delete()
            for key, value in filters.items():
                query = query.eq(key, value)
            response = query.execute()
            return response.data
        except Exception as e:
            print(f"数据删除失败: {str(e)}")
            raise e

    async def get_data(self, table: str, filters: Optional[dict] = None, select: str = "*"):
        """查询数据"""
        try:
            query = self.client.table(table).select(select)
            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)
            response = query.execute()
            return response.data
        except Exception as e:
            print(f"数据查询失败: {str(e)}")
            raise e

# 创建全局服务实例
db_service = SupabaseService()