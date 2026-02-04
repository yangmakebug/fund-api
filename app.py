from flask import Flask, request, jsonify
import requests
import json
import time
import os
from flask_cors import CORS
from requests.exceptions import Timeout, ConnectionError, RequestException

app = Flask(__name__)
# 生产环境限定跨域源（测试阶段用*，上线后替换为你的前端域名）
CORS(app, resources={r"/api/*": {"origins": ["*"]}})

# 缓存基金数据（单Worker模式可用，多Worker需换Redis）
fund_cache = {}
cache_expire = 60  # 缓存60秒

def get_fund_data(fund_code):
    # 先检查缓存
    if fund_code in fund_cache and time.time() - fund_cache[fund_code]["timestamp"] < cache_expire:
        return fund_cache[fund_code]["data"]
    
    # 修正后的天天基金估值接口（域名从123456789改为1234567）
    url = f"https://fundgz.1234567.com.cn/js/{fund_code}.js?rt={int(time.time()*1000)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Referer": "https://fund.eastmoney.com/"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # 触发HTTP状态码错误（4xx/5xx）
        response.encoding = "utf-8"
        
        # 更鲁棒的截取JSON部分（兼容接口返回格式小变动）
        data_str = response.text.strip()
        start_idx = data_str.find("(") + 1
        end_idx = data_str.rfind(")")
        if start_idx <= 0 or end_idx <= start_idx:
            raise ValueError("接口返回格式异常")
        data_str = data_str[start_idx:end_idx]
        
        data = json.loads(data_str)
        
        # 整理返回数据格式
        result = {
            "code": fund_code,
            "name": data.get("name", "未知基金"),
            "estimate_net": data.get("gsz", "0.0000"),  # 估值净值
            "estimate_change": data.get("gszzl", "0.00"),  # 估值涨跌幅
            "fund_type": "混合",  # 可扩展接口获取真实基金类型
            "stock_ratio": "94%",
            "bond_ratio": "3%",
            "cash_ratio": "3%"
        }
        
        # 更新缓存（修复你代码里断行的问题）
        fund_cache[fund_code] = {"timestamp": time.time(), "data": result}
        return result
    
    # 细化异常处理，方便排查问题
    except Timeout:
        return {"code": fund_code, "name": "查询超时", "estimate_net": "0.0000", "estimate_change": "0.00"}
    except ConnectionError:
        return {"code": fund_code, "name": "网络连接失败", "estimate_net": "0.0000", "estimate_change": "0.00"}
    except json.JSONDecodeError:
        return {"code": fund_code, "name": "数据解析失败", "estimate_net": "0.0000", "estimate_change": "0.00"}
    except RequestException as e:
        return {"code": fund_code, "name": f"请求错误: {str(e)}", "estimate_net": "0.0000", "estimate_change": "0.00"}
    except Exception as e:
        return {"code": fund_code, "name": f"未知错误: {str(e)}", "estimate_net": "0.0000", "estimate_change": "0.00"}

@app.route("/api/fund", methods=["POST"])
def fund_api():
    # 严格校验请求格式
    if not request.is_json:
        return jsonify({"error": "请求体必须为JSON格式"}), 400
    
    req_data = request.get_json()
    codes = req_data.get("codes", [])
    
    # 校验codes是否为数组
    if not isinstance(codes, list):
        return jsonify({"error": "codes必须为数组格式"}), 400
    
    result = []
    for code in codes:
        # 精准校验基金代码（公募基金多为6位数字）
        if isinstance(code, str) and code.isdigit() and len(code) == 6:
            result.append(get_fund_data(code))
        else:
            result.append({"code": code, "name": "无效的基金代码（需6位数字）", "estimate_net": "0.0000", "estimate_change": "0.00"})
    
    return jsonify(result)

# 适配Render部署的启动逻辑（修复你代码里断行的问题）
if __name__ == "__main__":
    # 读取Render分配的PORT环境变量（必填，避免端口冲突）
    port = int(os.environ.get("PORT", 5000))
    # 本地调试可开启debug，生产环境自动关闭
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug_mode)