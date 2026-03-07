import ezkl
import asyncio
import urllib.request
import sys

srs_path = "ezkl_kzg.srs"
LOGROWS = 16  # 与 run_ezkl.py 一致（PLA 无 lookup 轻量化后）

# ezkl 官方 SRS 地址（国内可能超时，需代理或手动下载）
EZKL_SRS_URL = f"https://kzg.ezkl.xyz/kzg{LOGROWS}.srs"


def download_srs_fallback(url: str, path: str, timeout: int = 120) -> bool:
    """网络不通时可用：用 Python 拉取 SRS（或你在能访问的机器上下载后拷到 path）"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ezkl-srs-download"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            with open(path, "wb") as f:
                f.write(r.read())
        return True
    except Exception as e:
        print(f"备用下载失败: {e}", file=sys.stderr)
        return False


async def main():
    try:
        await ezkl.get_srs(logrows=LOGROWS, srs_path=srs_path)
        print("SRS 生成完成:", srs_path)
        return
    except RuntimeError as e:
        err = str(e).lower()
        if "get srs" in err or "reqwest" in err or "url" in err:
            print("ezkl 官方下载失败（多为网络/墙），尝试备用下载...", file=sys.stderr)
            if download_srs_fallback(EZKL_SRS_URL, srs_path):
                print("SRS 备用下载完成:", srs_path)
                return
            print(
                "\n若仍失败，请：\n"
                "  1) 使用代理/VPN 后重新运行: python 3.py\n"
                f"  2) 或在可访问外网的机器上用浏览器/curl 下载 {EZKL_SRS_URL}\n"
                f"     保存为当前目录下的 {srs_path}",
                file=sys.stderr,
            )
            sys.exit(1)
        raise


if __name__ == "__main__":
    asyncio.run(main())