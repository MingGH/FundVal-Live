import os
import re
import datetime
import numpy as np
import pandas as pd
from typing import Optional, Dict, Any, List
from duckduckgo_search import DDGS
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser

from ..config import Config
from .prompts import LINUS_FINANCIAL_ANALYSIS_PROMPT
from .fund import get_fund_history, _calculate_technical_indicators
from ..db import get_db_connection, release_db_connection, dict_cursor


class AIService:
    def __init__(self):
        pass

    def _get_prompt_template(self, prompt_id: Optional[int] = None, user_id: Optional[int] = None):
        conn = get_db_connection()
        cur = dict_cursor(conn)

        if prompt_id:
            cur.execute("SELECT system_prompt, user_prompt FROM ai_prompts WHERE id = %s", (prompt_id,))
        else:
            # Try user default first, then system default
            if user_id:
                cur.execute("SELECT system_prompt, user_prompt FROM ai_prompts WHERE user_id = %s AND is_default = TRUE LIMIT 1", (user_id,))
                row = cur.fetchone()
                if row:
                    release_db_connection(conn)
                    from langchain_core.prompts import ChatPromptTemplate
                    return ChatPromptTemplate.from_messages([("system", row["system_prompt"]), ("user", row["user_prompt"])])
            cur.execute("SELECT system_prompt, user_prompt FROM ai_prompts WHERE user_id IS NULL AND is_default = TRUE LIMIT 1")

        row = cur.fetchone()
        release_db_connection(conn)

        if not row:
            return LINUS_FINANCIAL_ANALYSIS_PROMPT

        from langchain_core.prompts import ChatPromptTemplate
        return ChatPromptTemplate.from_messages([("system", row["system_prompt"]), ("user", row["user_prompt"])])

    def _init_llm(self, fast_mode=True):
        api_base = Config.OPENAI_API_BASE
        api_key = Config.OPENAI_API_KEY
        model = Config.AI_MODEL_NAME

        if not api_key:
            return None

        return ChatOpenAI(
            model=model, openai_api_key=api_key, openai_api_base=api_base,
            temperature=0.3, request_timeout=60 if fast_mode else 120
        )

    def search_news(self, query: str) -> str:
        try:
            ddgs = DDGS(verify=False)
            results = ddgs.text(keywords=query, region="cn-zh", safesearch="off", timelimit="w", max_results=5)
            if not results:
                return "暂无相关近期新闻。"
            output = ""
            for i, res in enumerate(results, 1):
                output += f"{i}. {res.get('title')} - {res.get('body')}\n"
            return output
        except Exception as e:
            print(f"Search error: {e}")
            return "新闻搜索服务暂时不可用。"

    def _calculate_indicators(self, history: List[Dict[str, Any]]) -> Dict[str, str]:
        if not history or len(history) < 5:
            return {"status": "数据不足", "desc": "新基金或数据缺失"}

        navs = [item['nav'] for item in history]
        current_nav = navs[-1]
        max_nav = max(navs)
        min_nav = min(navs)
        avg_nav = sum(navs) / len(navs)
        position = (current_nav - min_nav) / (max_nav - min_nav) if max_nav > min_nav else 0.5

        status = "正常"
        if position > 0.9: status = "高位"
        elif position < 0.1: status = "低位"
        elif current_nav > avg_nav * 1.05: status = "偏高"
        elif current_nav < avg_nav * 0.95: status = "偏低"

        return {
            "status": status,
            "desc": f"近30日最高{max_nav:.4f}, 最低{min_nav:.4f}, 现价处于{'高位' if position>0.8 else '低位' if position<0.2 else '中位'}区间 ({int(position*100)}%)"
        }

    async def analyze_fund(self, fund_info: Dict[str, Any], prompt_id: Optional[int] = None, user_id: Optional[int] = None) -> Dict[str, Any]:
        llm = self._init_llm()

        if not llm:
            return {
                "summary": "未配置 LLM API Key，无法进行分析。",
                "risk_level": "未知",
                "analysis_report": "请在设置页面配置 OpenAI API Key 以启用 AI 分析功能。",
                "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
            }

        fund_id = fund_info.get("id")
        fund_name = fund_info.get("name", "未知基金")

        history = get_fund_history(fund_id, limit=250)
        indicators = self._calculate_indicators(history[:30] if len(history) >= 30 else history)
        technical_indicators = _calculate_technical_indicators(history)

        consistency_note = ""
        try:
            sharpe = technical_indicators.get("sharpe")
            annual_return_str = technical_indicators.get("annual_return", "")
            volatility_str = technical_indicators.get("volatility", "")
            if sharpe != "--" and annual_return_str != "--" and volatility_str != "--":
                annual_return = float(annual_return_str.rstrip('%')) / 100.0
                volatility = float(volatility_str.rstrip('%')) / 100.0
                sharpe_val = float(sharpe)
                rf = 0.02
                expected_sharpe = (annual_return - rf) / volatility if volatility > 0 else 0
                sharpe_diff = abs(expected_sharpe - sharpe_val)
                if sharpe_diff > 0.3:
                    consistency_note = f"\n⚠️ 数据一致性警告：夏普比率 {sharpe_val} 与计算值 {expected_sharpe:.2f} 偏差 {sharpe_diff:.2f}"
                else:
                    consistency_note = f"\n✓ 数据自洽性验证通过（偏差 {sharpe_diff:.2f}）"
        except: pass

        history_summary = "暂无历史数据"
        if history:
            recent_history = history[:30]
            history_summary = f"近30日走势: 起始{recent_history[0]['nav']} -> 结束{recent_history[-1]['nav']}. {indicators['desc']}"

        holdings_str = ""
        if fund_info.get("holdings"):
            holdings_str = "\n".join([
                f"- {h['name']}: {h['percent']}% (涨跌: {h['change']:+.2f}%)"
                for h in fund_info["holdings"][:10]
            ])

        variables = {
            "fund_code": fund_id, "fund_name": fund_name,
            "fund_type": fund_info.get("type", "未知"),
            "manager": fund_info.get("manager", "未知"),
            "nav": fund_info.get("nav", "--"),
            "estimate": fund_info.get("estimate", "--"),
            "est_rate": fund_info.get("estRate", 0),
            "sharpe": technical_indicators.get("sharpe", "--"),
            "volatility": technical_indicators.get("volatility", "--"),
            "max_drawdown": technical_indicators.get("max_drawdown", "--"),
            "annual_return": technical_indicators.get("annual_return", "--"),
            "concentration": fund_info.get("indicators", {}).get("concentration", "--"),
            "holdings": holdings_str or "暂无持仓数据",
            "history_summary": history_summary
        }

        prompt_template = self._get_prompt_template(prompt_id, user_id=user_id)
        chain = prompt_template | llm | StrOutputParser()

        try:
            raw_result = await chain.ainvoke(variables)
            clean_json = raw_result.strip()
            if "```json" in clean_json:
                clean_json = clean_json.split("```json")[1].split("```")[0]
            elif "```" in clean_json:
                clean_json = clean_json.split("```")[1].split("```")[0]

            import json
            result = json.loads(clean_json)
            result["indicators"] = indicators
            result["timestamp"] = datetime.datetime.now().strftime("%H:%M:%S")
            return result
        except Exception as e:
            print(f"AI Analysis Error: {e}")
            return {
                "summary": "分析生成失败", "risk_level": "未知",
                "analysis_report": f"LLM 调用或解析失败: {str(e)}",
                "indicators": indicators,
                "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
            }

ai_service = AIService()
