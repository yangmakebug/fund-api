from flask import Flask, request, jsonify
import requests
import json
import time
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # 解决跨域问题

# 缓存基金数据，避免频繁请求 → 已调整为60秒
fund_cache = {}
cache_expire = 60  # 缓存60秒

def get_fund_data(fund_code):
    # 先检查缓存
    if fund_code in fund_cache and time.time() - fund_cache[fund_code]["timestamp"] < cache_expire:
        return fund_cache[fund_code]["data"]
    
    # 天天基金估值接口
    url = f"https://fundgz.1234567.com.cn/js/{fund_code}.js?rt={int(time.time()*1000)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Referer": "https://fund.eastmoney.com/"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = "utf-8"
        # 处理返回的js格式数据
        data_str = response.text.strip().replace(f"jsonpgz(", "").rstrip(");")
        data = json.loads(data_str)
        
        # 整理数据格式
        result = {
            "code": fund_code,
            "name": data.get("name", "未知基金"),
            "estimate_net": data.get("gsz", "0.0000"),
            "estimate_change": data.get("gszzl", "0.00"),
            "fund_type": "混合",  # 简化处理，可扩展接口获取更详细类型
            "stock_ratio": "94%", # 简化处理
            "bond_ratio": "3%",
            "cash_ratio": "3%"
        }
        
        # 更新缓存
        fund_cache[fund_code] = {"timestamp": time.time(), "data": result}
        return result
    except Exception as e:
        return {"code": fund_code, "name": f"查询失败: {str(e)[:10]}", "estimate_net": "0.0000", "estimate_change": "0.00"}

@app.route("/api/fund", methods=["POST"])
def fund_api():
    codes = request.json.get("codes", [])
    result = []
    for code in codes:
        if code.isdigit() and (len(code) == 5 or len(code) == 6):
            result.append(get_fund_data(code))
    return jsonify(result)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)