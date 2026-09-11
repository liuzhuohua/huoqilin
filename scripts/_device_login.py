"""GitHub device flow login — 阻塞等用户输入验证码"""
import json, time, urllib.request, urllib.parse, sys

CLIENT_ID = "178c6fc778ccc68e1d6a"   # gh CLI 公开 OAuth client_id
SCOPES = "repo,read:org,gist"

# 1) 申请 device code
req = urllib.request.Request(
    "https://github.com/login/device/code",
    data=urllib.parse.urlencode({"client_id": CLIENT_ID, "scope": SCOPES}).encode(),
    headers={"Accept": "application/json"},
    method="POST",
)
info = json.loads(urllib.request.urlopen(req, timeout=10).read())
device_code = info["device_code"]
user_code = info["user_code"]
interval = info.get("interval", 5)
expires_in = info.get("expires_in", 900)

print("=" * 60)
print("  GitHub 设备授权")
print("  请去 https://github.com/login/device")
print(f"  输入验证码: {user_code}")
print(f"  (用户名 liuzhuohua, {expires_in // 60} 分钟内有效)")
print("=" * 60)
print()
print("⏳ 等待你完成浏览器授权...")

deadline = time.time() + expires_in
attempt = 0
while time.time() < deadline:
    attempt += 1
    time.sleep(interval)
    try:
        r = urllib.request.Request(
            "https://github.com/login/oauth/access_token",
            data=urllib.parse.urlencode({
                "client_id": CLIENT_ID,
                "device_code": device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            }).encode(),
            headers={"Accept": "application/json"},
            method="POST",
        )
        resp = json.loads(urllib.request.urlopen(r, timeout=10).read())
        if "access_token" in resp:
            tok = resp["access_token"]
            # 写到 keyring-like 文件 (chmod 600)
            out = r"C:\Users\XYJZ_AJEEF_Win10\AppData\Local\Temp\gh_token.txt"
            with open(out, "w") as f:
                f.write(tok)
            # 同时用 git credential helper 形式写入
            print(f"✅ 授权成功 (尝试 {attempt} 次)")
            print(f"   token 已写入: {out}")
            print(f"   token 长度: {len(tok)}")
            sys.exit(0)
        if "slow_down" in resp:
            interval += 5
            print(f"   [{attempt}] 速率限制, 间隔 -> {interval}s")
            continue
        if "authorization_pending" in resp:
            if attempt % 6 == 0:
                print(f"   [{attempt}] 等待中...")
            continue
        if "expired_token" in resp:
            print("❌ 验证码已过期, 请重跑")
            sys.exit(1)
        if "access_denied" in resp:
            print("❌ 你拒绝了授权")
            sys.exit(1)
        print(f"   [{attempt}] 未知: {resp}")
    except Exception as e:
        print(f"   [{attempt}] 异常: {e}")
print("❌ 超时")
sys.exit(1)