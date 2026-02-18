"""Database initialization script. Run: python scripts/init_db.py [--reset]"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.storage.sqlite_client import init_db, get_db, close_db


async def main():
    settings = get_settings()
    reset = "--reset" in sys.argv

    settings.resolved_data_dir.mkdir(parents=True, exist_ok=True)

    if reset and settings.db_path.exists():
        settings.db_path.unlink()
        print(f"已删除旧数据库: {settings.db_path}")

    await init_db()
    print(f"数据库初始化完成: {settings.db_path}")

    db = await get_db()
    cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = await cursor.fetchall()
    print(f"已创建 {len(tables)} 张表:")
    for t in tables:
        print(f"  - {t[0]}")

    await close_db()


if __name__ == "__main__":
    asyncio.run(main())
