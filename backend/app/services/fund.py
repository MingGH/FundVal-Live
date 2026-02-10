from __future__ import annotations

import time
import json
import re
from typing import List, Dict, Any

import pandas as pd
import akshare as ak
import requests

from ..db import get_db_connection, release_db_connection, dict_cursor
from ..config import Config


def get_fund_type(code: str, name: str) -> str:
    conn = None
    try:
        conn = get_db_connection()
        cur = dict_cursor(conn)
        cur.execute("SELECT type FROM funds WHERE code = %s", (code,))
        row = cur.fetchone()
        if row and row["type"]:
            return row["type"]
    except Exception as e:
        print(f"DB query error for {code}: {e}")
    finally:
        if conn:
            release_db_connection(conn)

    if "债" in name or "纯债" in name or "固收" in name:
        return "债券"
    if "QDII" in name or "纳斯达克" in name or "标普" in name or "恒生" in name:
        return "QDII"
    if "货币" in name:
        return "货币"
    return "未知"


def get_eastmoney_valuation(code: str) -> Dict[str, Any]:
    url = f"http://fundgz.1234567.com.cn/js/{code}.js?rt={int(time.time()*1000)}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            match = re.search(r"jsonpgz\((.*)\)", response.text)
            if match and match.group(1):
                data = json.loads(match.group(1))
                return {
                    "name": data.get("name"),
                    "nav": float(data.get("dwjz", 0.0)),
                    "estimate": float(data.get("gsz", 0.0)),
                    "estRate": float(data.get("gszzl", 0.0)),
                    "time": data.get("gztime")
                }
    except Exception as e:
        print(f"Eastmoney API error for {code}: {e}")
    return {}


def get_sina_valuation(code: str) -> Dict[str, Any]:
    url = f"http://hq.sinajs.cn/list=fu_{code}"
    headers = {"Referer": "http://finance.sina.com.cn"}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        match = re.search(r'="(.*)"', response.text)
        if match and match.group(1):
            parts = match.group(1).split(',')
            if len(parts) >= 8:
                return {
                    "estimate": float(parts[2]),
                    "nav": float(parts[3]),
                    "estRate": float(parts[6]),
                    "time": f"{parts[7]} {parts[1]}"
                }
    except Exception as e:
        print(f"Sina Valuation API error for {code}: {e}")
    return {}


def get_combined_valuation(code: str) -> Dict[str, Any]:
    data = get_eastmoney_valuation(code)
    if not data or data.get("estimate") == 0.0:
        sina_data = get_sina_valuation(code)
        if sina_data:
            data.update(sina_data)
    return data


def search_funds(q: str) -> List[Dict[str, Any]]:
    if not q:
        return []
    q_clean = q.strip()
    pattern = f"%{q_clean}%"

    conn = get_db_connection()
    cur = dict_cursor(conn)
    try:
        cur.execute("""
            SELECT code, name, type FROM funds
            WHERE code LIKE %s OR name LIKE %s LIMIT 20
        """, (pattern, pattern))
        rows = cur.fetchall()
        return [{"id": str(r["code"]), "name": r["name"], "type": r["type"] or "未知"} for r in rows]
    finally:
        release_db_connection(conn)


def get_eastmoney_pingzhong_data(code: str) -> Dict[str, Any]:
    url = Config.EASTMONEY_DETAILED_API_URL.format(code=code)
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            text = response.text
            data = {}
            name_match = re.search(r'fS_name\s*=\s*"(.*?)";', text)
            if name_match: data["name"] = name_match.group(1)

            code_match = re.search(r'fS_code\s*=\s*"(.*?)";', text)
            if code_match: data["code"] = code_match.group(1)

            manager_match = re.search(r'Data_currentFundManager\s*=\s*(\[.+?\])\s*;\s*/\*', text)
            if manager_match:
                try:
                    managers = json.loads(manager_match.group(1))
                    if managers:
                        data["manager"] = ", ".join([m["name"] for m in managers])
                except: pass

            for key in ["syl_1n", "syl_6y", "syl_3y", "syl_1y"]:
                m = re.search(rf'{key}\s*=\s*"(.*?)";', text)
                if m: data[key] = m.group(1)

            perf_match = re.search(r'Data_performanceEvaluation\s*=\s*(\{.+?\})\s*;\s*/\*', text)
            if perf_match:
                try:
                    perf = json.loads(perf_match.group(1))
                    if perf and "data" in perf and "categories" in perf:
                        data["performance"] = dict(zip(perf["categories"], perf["data"]))
                except: pass

            history_match = re.search(r'Data_netWorthTrend\s*=\s*(\[.+?\])\s*;\s*/\*', text)
            if history_match:
                try:
                    raw_hist = json.loads(history_match.group(1))
                    data["history"] = [
                        {"date": time.strftime('%Y-%m-%d', time.localtime(item['x']/1000)), "nav": float(item['y'])}
                        for item in raw_hist
                    ]
                except: pass

            return data
    except Exception as e:
        print(f"PingZhong API error for {code}: {e}")
    return {}


def _get_fund_info_from_db(code: str) -> Dict[str, Any]:
    try:
        conn = get_db_connection()
        cur = dict_cursor(conn)
        cur.execute("SELECT name, type FROM funds WHERE code = %s", (code,))
        row = cur.fetchone()
        release_db_connection(conn)
        if row:
            return {"name": row["name"], "type": row["type"]}
    except Exception as e:
        print(f"DB fetch error for {code}: {e}")
    return {}


def _fetch_stock_spots_sina(codes: List[str]) -> Dict[str, float]:
    if not codes:
        return {}

    formatted = []
    code_map = {}

    for c in codes:
        if not c: continue
        c_str = str(c).strip()
        prefix = ""
        clean_c = c_str

        if c_str.isdigit():
            if len(c_str) == 6:
                prefix = "sh" if c_str.startswith(('60', '68', '90', '11')) else "sz"
            elif len(c_str) == 5:
                prefix = "hk"
        elif c_str.isalpha():
            prefix = "gb_"
            clean_c = c_str.lower()

        if prefix:
            sina_code = f"{prefix}{clean_c}"
            formatted.append(sina_code)
            code_map[sina_code] = c_str

    if not formatted:
        return {}

    url = f"http://hq.sinajs.cn/list={','.join(formatted)}"
    headers = {"Referer": "http://finance.sina.com.cn"}

    try:
        response = requests.get(url, headers=headers, timeout=5)
        results = {}
        for line in response.text.strip().split('\n'):
            if not line or '=' not in line or '"' not in line: continue
            line_key = line.split('=')[0].split('_str_')[-1]
            original_code = code_map.get(line_key)
            if not original_code: continue

            data_part = line.split('"')[1]
            if not data_part: continue
            parts = data_part.split(',')

            change = 0.0
            try:
                if line_key.startswith("gb_"):
                    if len(parts) > 2:
                        change = float(parts[2])
                elif line_key.startswith("hk"):
                    if len(parts) > 6:
                        prev_close = float(parts[3])
                        last = float(parts[6])
                        if prev_close > 0:
                            change = round((last - prev_close) / prev_close * 100, 2)
                else:
                    if len(parts) > 3:
                        prev_close = float(parts[2])
                        last = float(parts[3])
                        if prev_close > 0:
                            change = round((last - prev_close) / prev_close * 100, 2)
                results[original_code] = change
            except: continue
        return results
    except Exception as e:
        print(f"Sina fetch failed: {e}")
        return {}


def get_fund_history(code: str, limit: int = 30) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cur = dict_cursor(conn)

    if limit >= 9999:
        cur.execute("SELECT date, nav, updated_at FROM fund_history WHERE code = %s ORDER BY date DESC", (code,))
    else:
        cur.execute("SELECT date, nav, updated_at FROM fund_history WHERE code = %s ORDER BY date DESC LIMIT %s", (code, limit))

    rows = cur.fetchall()

    cache_valid = False
    if rows:
        latest_update = rows[0]["updated_at"]
        latest_nav_date = rows[0]["date"]
        try:
            from datetime import datetime
            update_time = latest_update if isinstance(latest_update, datetime) else datetime.fromisoformat(str(latest_update))
            age_hours = (datetime.now() - update_time.replace(tzinfo=None)).total_seconds() / 3600
            today_str = datetime.now().strftime("%Y-%m-%d")
            current_hour = datetime.now().hour
            min_rows = 10 if limit < 9999 else 100

            if current_hour >= 16 and latest_nav_date < today_str:
                cache_valid = False
            else:
                cache_valid = age_hours < 24 and len(rows) >= min(limit, min_rows)
        except: pass

    if cache_valid:
        release_db_connection(conn)
        return [{"date": row["date"], "nav": float(row["nav"])} for row in reversed(rows)]

    try:
        df = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
        if df is None or df.empty:
            release_db_connection(conn)
            return []

        if limit < 9999:
            df = df.sort_values(by="净值日期", ascending=False).head(limit)
        df = df.sort_values(by="净值日期", ascending=True)

        results = []
        for _, row in df.iterrows():
            d = row["净值日期"]
            date_str = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10]
            nav_value = float(row["单位净值"])
            results.append({"date": date_str, "nav": nav_value})

            cur.execute("""
                INSERT INTO fund_history (code, date, nav, updated_at)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                ON DUPLICATE KEY UPDATE nav = VALUES(nav), updated_at = CURRENT_TIMESTAMP
            """, (code, date_str, nav_value))

        conn.commit()
        release_db_connection(conn)
        return results
    except Exception as e:
        print(f"History fetch error for {code}: {e}")
        release_db_connection(conn)
        return []


def get_nav_on_date(code: str, date_str: str) -> float | None:
    history = get_fund_history(code, limit=90)
    for item in history:
        if item["date"][:10] == date_str[:10]:
            return item["nav"]
    return None


def _calculate_technical_indicators(history: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not history or len(history) < 10:
        return {"sharpe": "--", "volatility": "--", "max_drawdown": "--", "annual_return": "--"}

    try:
        import numpy as np
        navs = np.array([item['nav'] for item in history])
        daily_returns = np.diff(navs) / navs[:-1]
        total_return = (navs[-1] - navs[0]) / navs[0]
        years = len(history) / 250.0
        annual_return = (1 + total_return)**(1/years) - 1 if years > 0 else 0
        volatility = np.std(daily_returns) * np.sqrt(250)
        rf = 0.02
        sharpe = (annual_return - rf) / volatility if volatility > 0 else 0
        rolling_max = np.maximum.accumulate(navs)
        drawdowns = (navs - rolling_max) / rolling_max
        max_drawdown = np.min(drawdowns)

        return {
            "sharpe": round(float(sharpe), 2),
            "volatility": f"{round(float(volatility) * 100, 2)}%",
            "max_drawdown": f"{round(float(max_drawdown) * 100, 2)}%",
            "annual_return": f"{round(float(annual_return) * 100, 2)}%"
        }
    except Exception as e:
        print(f"Indicator calculation error: {e}")
        return {"sharpe": "--", "volatility": "--", "max_drawdown": "--", "annual_return": "--"}


def get_fund_intraday(code: str) -> Dict[str, Any]:
    em_data = get_combined_valuation(code)

    name = em_data.get("name")
    nav = float(em_data.get("nav", 0.0))
    estimate = float(em_data.get("estimate", 0.0))
    est_rate = float(em_data.get("estRate", 0.0))
    update_time = em_data.get("time", time.strftime("%H:%M:%S"))

    pz_data = get_eastmoney_pingzhong_data(code)
    extra_info = {}
    if pz_data.get("name"): extra_info["full_name"] = pz_data["name"]
    if pz_data.get("manager"): extra_info["manager"] = pz_data["manager"]
    for k in ["syl_1n", "syl_6y", "syl_3y", "syl_1y"]:
        if pz_data.get(k): extra_info[k] = pz_data[k]

    db_info = _get_fund_info_from_db(code)
    if db_info:
        if not extra_info.get("full_name"): extra_info["full_name"] = db_info["name"]
        extra_info["official_type"] = db_info["type"]

    if not name:
        name = extra_info.get("full_name", f"基金 {code}")
    manager = extra_info.get("manager", "--")

    history_data = pz_data.get("history", [])
    if history_data:
        tech_indicators = _calculate_technical_indicators(history_data[-250:])
    else:
        history_data = get_fund_history(code, limit=250)
        tech_indicators = _calculate_technical_indicators(history_data)

    holdings = []
    concentration_rate = 0.0
    try:
        current_year = str(time.localtime().tm_year)
        holdings_df = ak.fund_portfolio_hold_em(symbol=code, date=current_year)
        if holdings_df is None or holdings_df.empty:
            prev_year = str(time.localtime().tm_year - 1)
            holdings_df = ak.fund_portfolio_hold_em(symbol=code, date=prev_year)

        if not holdings_df.empty:
            holdings_df = holdings_df.copy()
            if "占净值比例" in holdings_df.columns:
                holdings_df["占净值比例"] = (
                    holdings_df["占净值比例"].astype(str).str.replace("%", "", regex=False)
                )
                holdings_df["占净值比例"] = pd.to_numeric(holdings_df["占净值比例"], errors="coerce").fillna(0.0)

            sorted_holdings = holdings_df.sort_values(by="占净值比例", ascending=False)
            top10 = sorted_holdings.head(10)
            concentration_rate = top10["占净值比例"].sum()

            stock_codes = [str(c) for c in holdings_df["股票代码"].tolist() if c]
            spot_map = _fetch_stock_spots_sina(stock_codes)

            seen_codes = set()
            for _, row in sorted_holdings.iterrows():
                stock_code = str(row.get("股票代码"))
                percent = float(row.get("占净值比例", 0.0))
                if stock_code in seen_codes or percent < 0.01: continue
                seen_codes.add(stock_code)
                holdings.append({
                    "name": row.get("股票名称"),
                    "percent": percent,
                    "change": spot_map.get(stock_code, 0.0),
                })
            holdings = holdings[:20]
    except: pass

    sector = get_fund_type(code, name)

    return {
        "id": str(code), "name": name, "type": sector, "manager": manager,
        "nav": nav, "estimate": estimate, "estRate": est_rate, "time": update_time,
        "holdings": holdings,
        "indicators": {
            "returns": {
                "1M": extra_info.get("syl_1y", "--"),
                "3M": extra_info.get("syl_3y", "--"),
                "6M": extra_info.get("syl_6y", "--"),
                "1Y": extra_info.get("syl_1n", "--")
            },
            "concentration": round(concentration_rate, 2),
            "technical": tech_indicators
        }
    }
