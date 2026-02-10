import os
import logging
from contextlib import contextmanager
import pymysql
from dbutils.pooled_db import PooledDB

logger = logging.getLogger(__name__)

_pool = None


def _get_database_url():
    return os.getenv("DATABASE_URL", "mysql://funduser:fundpass@localhost:3306/fundval")


def _parse_mysql_url(url: str) -> dict:
    """Parse mysql://user:pass@host:port/db into connection kwargs."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 3306,
        "user": parsed.username or "root",
        "password": parsed.password or "",
        "database": parsed.path.lstrip("/") or "fundval",
        "charset": "utf8mb4",
    }


def _init_pool():
    global _pool
    if _pool is None:
        params = _parse_mysql_url(_get_database_url())
        _pool = PooledDB(
            creator=pymysql,
            mincached=2,
            maxcached=20,
            maxconnections=20,
            blocking=True,
            cursorclass=pymysql.cursors.DictCursor,
            **params,
        )


def get_db_connection():
    _init_pool()
    conn = _pool.connection()
    return conn


def release_db_connection(conn):
    if conn:
        conn.close()


@contextmanager
def get_db():
    conn = get_db_connection()
    try:
        yield conn
    finally:
        release_db_connection(conn)


def dict_cursor(conn):
    return conn.cursor(pymysql.cursors.DictCursor)


def init_db():
    """Initialize the database schema with migration support."""
    conn = get_db_connection()
    cur = dict_cursor(conn)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()

    cur.execute("SELECT MAX(version) AS v FROM schema_version")
    row = cur.fetchone()
    current_version = row["v"] or 0
    logger.info(f"Current database schema version: {current_version}")

    if current_version < 1:
        logger.info("Running migration v1: base tables")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(100) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(20) NOT NULL DEFAULT 'user',
                is_active TINYINT(1) NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS funds (
                code VARCHAR(20) PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        cur.execute("CREATE INDEX idx_funds_name ON funds(name(100))")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER AUTO_INCREMENT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                name VARCHAR(100) NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uq_accounts_user_name (user_id, name),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                account_id INTEGER NOT NULL,
                code VARCHAR(20) NOT NULL,
                cost REAL NOT NULL DEFAULT 0.0,
                shares REAL NOT NULL DEFAULT 0.0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (account_id, code),
                FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
            )
        """)
        cur.execute("CREATE INDEX idx_positions_account ON positions(account_id)")
        cur.execute("CREATE INDEX idx_positions_code ON positions(code)")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER AUTO_INCREMENT PRIMARY KEY,
                account_id INTEGER NOT NULL,
                code VARCHAR(20) NOT NULL,
                op_type VARCHAR(20) NOT NULL,
                amount_cny REAL,
                shares_redeemed REAL,
                confirm_date VARCHAR(20) NOT NULL,
                confirm_nav REAL,
                shares_added REAL,
                cost_after REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                applied_at TIMESTAMP NULL,
                FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
            )
        """)
        cur.execute("CREATE INDEX idx_transactions_account ON transactions(account_id)")
        cur.execute("CREATE INDEX idx_transactions_code ON transactions(code)")
        cur.execute("CREATE INDEX idx_transactions_confirm_date ON transactions(confirm_date)")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER AUTO_INCREMENT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                code VARCHAR(20) NOT NULL,
                email VARCHAR(200) NOT NULL,
                threshold_up REAL,
                threshold_down REAL,
                enable_digest TINYINT(1) DEFAULT 0,
                digest_time VARCHAR(10) DEFAULT '14:45',
                enable_volatility TINYINT(1) DEFAULT 1,
                last_notified_at TIMESTAMP NULL,
                last_digest_at TIMESTAMP NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uq_sub_user_code_email (user_id, code, email),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                `key` VARCHAR(100) PRIMARY KEY,
                value TEXT,
                encrypted INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id INTEGER NOT NULL,
                `key` VARCHAR(100) NOT NULL,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, `key`),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS ai_prompts (
                id INTEGER AUTO_INCREMENT PRIMARY KEY,
                user_id INTEGER,
                name VARCHAR(200) NOT NULL,
                system_prompt TEXT NOT NULL,
                user_prompt TEXT NOT NULL,
                is_default TINYINT(1) DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY idx_ai_prompts_user_name (user_id, name),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS fund_history (
                code VARCHAR(20) NOT NULL,
                date VARCHAR(20) NOT NULL,
                nav REAL NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (code, date)
            )
        """)
        cur.execute("CREATE INDEX idx_fund_history_code ON fund_history(code)")
        cur.execute("CREATE INDEX idx_fund_history_date ON fund_history(date)")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS fund_intraday_snapshots (
                fund_code VARCHAR(20) NOT NULL,
                date VARCHAR(20) NOT NULL,
                time VARCHAR(10) NOT NULL,
                estimate REAL NOT NULL,
                PRIMARY KEY (fund_code, date, time)
            )
        """)

        cur.execute("INSERT IGNORE INTO schema_version (version) VALUES (1)")
        conn.commit()

    _seed_defaults(conn)
    conn.commit()
    release_db_connection(conn)
    logger.info("Database initialized.")


def _seed_defaults(conn):
    """Seed default admin user, settings, and AI prompts."""
    cur = dict_cursor(conn)

    cur.execute("SELECT id FROM users WHERE username = 'admin'")
    if not cur.fetchone():
        from .auth import hash_password
        admin_pw = os.getenv("ADMIN_PASSWORD", "admin123")
        cur.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, 'admin')",
            ("admin", hash_password(admin_pw))
        )
        logger.info("Created default admin user")

    cur.execute("SELECT id FROM users WHERE username = 'admin'")
    admin_row = cur.fetchone()
    admin_id = admin_row["id"] if admin_row else 1

    cur.execute("SELECT id FROM accounts WHERE user_id = %s AND name = %s", (admin_id, "默认账户"))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO accounts (user_id, name, description) VALUES (%s, %s, %s)",
            (admin_id, "默认账户", "系统默认账户")
        )

    default_settings = [
        ('OPENAI_API_KEY', '', 1),
        ('OPENAI_API_BASE', 'https://api.openai.com/v1', 0),
        ('AI_MODEL_NAME', 'gpt-3.5-turbo', 0),
        ('SMTP_HOST', 'smtp.gmail.com', 0),
        ('SMTP_PORT', '587', 0),
        ('SMTP_USER', '', 0),
        ('SMTP_PASSWORD', '', 1),
        ('EMAIL_FROM', 'noreply@fundval.live', 0),
        ('INTRADAY_COLLECT_INTERVAL', '5', 0),
    ]
    for key, value, encrypted in default_settings:
        cur.execute(
            "INSERT IGNORE INTO settings (`key`, value, encrypted) VALUES (%s, %s, %s)",
            (key, value, encrypted)
        )

    cur.execute("SELECT id FROM ai_prompts WHERE user_id IS NULL AND name = %s", ("Linus 风格（默认）",))
    if not cur.fetchone():
        cur.execute("""
            INSERT INTO ai_prompts (user_id, name, system_prompt, user_prompt, is_default)
            VALUES (NULL, %s, %s, %s, TRUE)
        """, (
            "Linus 风格（默认）",
            """角色设定
你是 Linus Torvalds，专注于基金的技术面与估值审计。
你极度厌恶情绪化叙事、无关噪音和模棱两可的废话。
你只输出基于数据的逻辑审计结果。

风格要求
- 禁用"首先、其次"、"第一、第二"等解析步骤。
- 句子短，判断极其明确。
- 语气：分析过程冷酷，投资建议务实。
- 核心关注：估值偏差、技术形态、风险收益比。

技术指标合理范围（重要！）
- 夏普比率：0.5-1.0 正常，1.0-1.5 良好，1.5-2.5 优秀，>2.5 异常优秀（罕见但可能）
- 夏普比率计算公式：(年化回报 - 无风险利率) / 年化波动率，其中无风险利率通常为 2-3%
- 最大回撤与年化回报的关系：回撤/回报比 < 0.5 为优秀，0.5-1.0 正常，>1.0 风险较高
- 数据一致性检查：验证夏普比率是否与年化回报、波动率数学一致（允许 ±0.3 误差）

判断逻辑
1. 先验证数据自洽性：夏普比率 ≈ (年化回报 - 2%) / 波动率
2. 如果数据一致，则分析风险收益比是否合理
3. 如果数据不一致，则标记为异常并说明原因""",
            """请对以下基金数据进行逻辑审计，并直接输出审计结果。

【输入数据】
基金代码: {fund_code}
基金名称: {fund_name}
基金类型: {fund_type}
基金经理: {manager}
最新净值: {nav}
实时估值: {estimate} ({est_rate}%)
夏普比率: {sharpe}
年化波动率: {volatility}
最大回撤: {max_drawdown}
年化收益: {annual_return}
持仓集中度: {concentration}%
前10大持仓: {holdings}
历史走势: {history_summary}

【输出要求（严禁分步骤描述分析过程，直接合并为一段精简报告）】
1. 逻辑审计：重点分析技术指标（夏普比率、最大回撤、波动率）、技术位阶（高/低位）及风险特征。
2. 最终结论：一句话总结当前基金的状态（高风险/低风险/正常/异常）。
3. 操作建议：给出 1-2 条冷静、务实的操作指令（持有/止盈/观望/定投）。

请输出纯 JSON 格式（不要用 Markdown 代码块包裹），包含字段:
- summary: 毒舌一句话总结
- risk_level: 风险等级（低风险/中风险/高风险/极高风险）
- analysis_report: 精简综合报告（200字以内）
- suggestions: 操作建议列表（1-3条）"""
        ))

    cur.execute("SELECT id FROM ai_prompts WHERE user_id IS NULL AND name = %s", ("温和风格",))
    if not cur.fetchone():
        cur.execute("""
            INSERT INTO ai_prompts (user_id, name, system_prompt, user_prompt, is_default)
            VALUES (NULL, %s, %s, %s, FALSE)
        """, (
            "温和风格",
            """你是一位专业的基金分析师，擅长用通俗易懂的语言解读基金数据。
你的分析客观、理性，注重风险提示，但语气温和友善。

分析要点：
- 用简单的语言解释技术指标的含义
- 客观评估基金的风险收益特征
- 给出实用的投资建议
- 避免过于激进或保守的判断""",
            """请分析以下基金数据：

【基金信息】
代码: {fund_code}
名称: {fund_name}
类型: {fund_type}
经理: {manager}

【净值数据】
最新净值: {nav}
实时估值: {estimate} ({est_rate}%)

【技术指标】
夏普比率: {sharpe}
年化波动率: {volatility}
最大回撤: {max_drawdown}
年化收益: {annual_return}

【持仓情况】
集中度: {concentration}%
前10大持仓: {holdings}

【历史走势】
{history_summary}

请输出纯 JSON 格式（不要用 Markdown 代码块包裹），包含：
- summary: 一句话总结
- risk_level: 风险等级（低风险/中风险/高风险/极高风险）
- analysis_report: 详细分析报告（300字左右）
- suggestions: 投资建议列表（2-4条）"""
        ))

    conn.commit()
