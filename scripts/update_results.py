"""최근 로또 6/45 당첨 결과를 가져와 results.json과 lotto.html의 내장 데이터를 갱신합니다.

동행복권 공식 사이트는 해외 IP(GitHub Actions, Codespaces)에서 접속이 막혀 있어
공개 결과 페이지(redinfo.co.kr)의 회차 카드를 읽어 옵니다.
"""
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SOURCE_URL = "https://www.redinfo.co.kr/lotto/s/result"
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results.json"
PAGE = ROOT / "lotto.html"
EMBED_RE = re.compile(r"(/\* RESULTS:START \*/\n).*?(\n\s*/\* RESULTS:END \*/)", re.S)
COUNT = 3

CARD_RE = re.compile(
    r"<strong>(?P<round>\d+)</strong>회</a>.*?"
    r'class="s2-date">.*?(?P<date>\d{4}\.\d{2}\.\d{2})</span>.*?'
    r'<div class="s2-balls">(?P<balls>.*?)</div>.*?'
    r'<p class="s2-summary">(?P<summary>.*?)</p>',
    re.S,
)
NUM_RE = re.compile(r'<span class="ball[^"]*">(\d+)</span>')
SUMMARY_RE = re.compile(r"1등\s*([\d,]+)\s*·\s*([\d,]+)명")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as res:
        return res.read().decode("utf-8")


def parse(html):
    draws = []
    for m in CARD_RE.finditer(html):
        before, _, after = m["balls"].partition('class="plus"')
        numbers = [int(n) for n in NUM_RE.findall(before)]
        bonus = [int(n) for n in NUM_RE.findall(after)]
        if len(numbers) != 6 or len(bonus) != 1:
            continue
        draw = {
            "round": int(m["round"]),
            "date": m["date"].replace(".", "-"),
            "numbers": sorted(numbers),
            "bonus": bonus[0],
        }
        s = SUMMARY_RE.search(m["summary"])
        if s:
            draw["firstPrize"] = int(s[1].replace(",", ""))
            draw["firstWinners"] = int(s[2].replace(",", ""))
        draws.append(draw)
    draws.sort(key=lambda d: d["round"], reverse=True)
    return draws


def main():
    draws = parse(fetch(SOURCE_URL))[:COUNT]
    if len(draws) < COUNT:
        sys.exit(f"결과를 {COUNT}회분 찾지 못했습니다. 원본 페이지 구조가 바뀌었는지 확인하세요.")
    if OUT.exists() and json.loads(OUT.read_text(encoding="utf-8")).get("draws") == draws:
        print("새 회차 없음")
        return
    data = {
        "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": SOURCE_URL,
        "draws": draws,
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    page = PAGE.read_text(encoding="utf-8")
    embed = "  const FALLBACK_RESULTS = " + json.dumps(data, ensure_ascii=False) + ";"
    page, n = EMBED_RE.subn(lambda m: m[1] + embed + m[2], page)
    if n != 1:
        sys.exit("lotto.html에서 RESULTS:START/END 표시를 찾지 못했습니다.")
    PAGE.write_text(page, encoding="utf-8")
    print(f"{OUT.name}: " + ", ".join(f"{d['round']}회" for d in draws))


if __name__ == "__main__":
    main()
