"""用 RDAP 批量查询域名是否已被注册。404 = 注册局无记录（大概率可注册）。"""
import json
import sys
import time
import urllib.error
import urllib.request

UA = {"User-Agent": "domain-check/1.0", "Accept": "application/rdap+json"}


def get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
                return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return 404, None
            if e.code in (429, 500, 502, 503) and i < tries - 1:
                time.sleep(2 ** (i + 1))
                continue
            return e.code, None
        except Exception:
            if i < tries - 1:
                time.sleep(2 ** (i + 1))
                continue
            return None, None


def load(path):
    out = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        base, _, tlds = line.partition(":")
        for tld in (tlds or "com").split(","):
            out.append(f"{base.strip()}.{tld.strip()}")
    return out


def main(src, dst):
    _, boot = get("https://data.iana.org/rdap/dns.json")
    servers = {t: urls[0] for tlds, urls in boot["services"] for t in tlds}
    rows = []
    for d in load(src):
        tld = d.rsplit(".", 1)[1]
        base = servers.get(tld)
        if not base:
            rows.append((d, "无 RDAP", "", ""))
            continue
        code, data = get(base.rstrip("/") + "/domain/" + d)
        if code == 404:
            rows.append((d, "可注册", "", ""))
        elif code == 200:
            ev = {e.get("eventAction"): e.get("eventDate", "")[:10] for e in data.get("events", [])}
            rows.append((d, "已注册", ev.get("registration", ""), ev.get("expiration", "")))
        else:
            rows.append((d, f"未知({code})", "", ""))
        print(*rows[-1], sep="\t", flush=True)
        time.sleep(0.4)

    free = [r for r in rows if r[1] == "可注册"]
    with open(dst, "w", encoding="utf-8") as f:
        f.write(f"# 域名查询结果\n\n查询时间（UTC）：{time.strftime('%Y-%m-%d %H:%M')}，共 {len(rows)} 个，可注册 {len(free)} 个。\n\n")
        f.write("> 「可注册」= RDAP 注册局无记录。部分（尤其 .ai）可能是保留或溢价域名，以注册商显示的价格为准。\n\n")
        f.write("## 可注册\n\n")
        f.write("".join(f"- {r[0]}\n" for r in free) or "（无）\n")
        f.write("\n## 全部\n\n| 域名 | 状态 | 注册日期 | 到期日期 |\n|---|---|---|---|\n")
        f.write("".join(f"| {' | '.join(r)} |\n" for r in rows))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
