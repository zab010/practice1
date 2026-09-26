"""최근 로또 6/45 당첨 결과를 가져와 페이지 안의 결과 데이터를 갱신합니다.

- index.html: 최근 3회 (RESULTS)
- stats.html: 최근 100회 (DRAWS)

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
# (파일, 변수 이름, 회차 수)
TARGETS = [
    (ROOT / "index.html", "RESULTS", 3),
    (ROOT / "stats.html", "DRAWS", 100),
]
MAX_PAGES = 10

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


def fetch_draws(count):
    """결과 페이지를 넘겨 가며 최근 count회를 모읍니다."""
    seen = {}
    for pnum in range(1, MAX_PAGES + 1):
        for d in parse(fetch(f"{SOURCE_URL}?pnum={pnum}")):
            seen[d["round"]] = d
        if len(seen) >= count:
            break
    draws = sorted(seen.values(), key=lambda d: d["round"], reverse=True)[:count]
    if len(draws) < count:
        sys.exit(f"결과를 {count}회분 찾지 못했습니다. 원본 페이지 구조가 바뀌었는지 확인하세요.")
    rounds = [d["round"] for d in draws]
    if rounds != list(range(rounds[0], rounds[0] - count, -1)):
        sys.exit("빠진 회차가 있습니다. 원본 페이지를 확인하세요.")
    return draws


def update_page(path, name, draws):
    marker = re.compile(rf"(/\* {name}:START \*/\n).*?(\n\s*/\* {name}:END \*/)", re.S)
    page = path.read_text(encoding="utf-8")
    current = marker.search(page)
    if not current:
        sys.exit(f"{path.name}에서 {name}:START/END 표시를 찾지 못했습니다.")
    old = re.search(rf"const {name} = (.*);", current[0])
    if old and json.loads(old[1]).get("draws") == draws:
        print(f"{path.name}: 새 회차 없음")
        return
    data = {
        "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": SOURCE_URL,
        "draws": draws,
    }
    embed = f"  const {name} = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";"
    path.write_text(marker.sub(lambda m: m[1] + embed + m[2], page, count=1), encoding="utf-8")
    print(f"{path.name}: {draws[-1]['round']}~{draws[0]['round']}회")


def main():
    draws = fetch_draws(max(n for _, _, n in TARGETS))
    for path, name, count in TARGETS:
        update_page(path, name, draws[:count])


if __name__ == "__main__":
    main()
