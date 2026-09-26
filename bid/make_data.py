"""사정률 분석기용 가상 전자입찰 데이터 20건을 만들어 index.html에 넣습니다.

모든 공고, 발주기관, 업체(아미이앤씨 포함)는 임의로 만든 것입니다.
나라장터 복수예비가격 방식을 단순화해 따릅니다.
- 기초금액의 ±3% 범위에서 복수예비가격 15개를 만든다.
- 참가 업체 5곳이 각각 2개씩 고르고, 많이 뽑힌 4개의 평균이 예정가격이다.
- 사정률 = 예정가격 / 기초금액 × 100 (97~103% 사이)
- 낙찰하한가 = 예정가격 × 낙찰하한율, 하한가 이상 최저 투찰자가 낙찰된다.
"""
import json
import random
import re
from datetime import date, timedelta
from pathlib import Path

SEED = 20260926
PAGE = Path(__file__).resolve().parent / "index.html"
ME = "아미이앤씨"
RIVALS = ["한결건설", "누리토건", "청솔이엔지", "바름종합건설", "소담개발", "다온건설", "푸른산업개발"]

AGENCIES = ["한빛시", "새솔군", "가람시", "누리군", "해밀시", "도담시 교육지원청", "라온도 건설본부", "여울시 상수도사업소"]
WORKS = [
    "도로 포장 보수공사", "배수로 정비공사", "초등학교 외벽 방수공사", "하천 호안 정비공사",
    "공원 산책로 조성공사", "마을회관 증축공사", "상수도 관로 교체공사", "체육관 지붕 개량공사",
    "보도 정비공사", "주차장 확장공사", "노후 옹벽 보강공사", "농로 포장공사",
]


def lower_rate(base):
    """적격심사 낙찰하한율(공사, 예시값). 실제 적용 비율은 공고문에서 확인해야 한다."""
    if base < 1_000_000_000:
        return 89.745
    if base < 5_000_000_000:
        return 88.745
    return 87.495


def make_bid(rng, no, day, rivals):
    base = rng.randrange(150, 3200) * 1_000_000 + rng.randrange(0, 1000) * 1000
    rate = lower_rate(base)
    prelim = sorted(round(base * (1 + rng.uniform(-0.03, 0.03)), -1) for _ in range(15))
    # 복수예비가격은 추첨 번호 순서로 섞어 둔다
    order = list(range(15))
    rng.shuffle(order)
    prelim = [prelim[i] for i in order]

    companies = [ME] + rivals
    picks = {c: sorted(rng.sample(range(15), 2)) for c in companies}
    count = [0] * 15
    for p in picks.values():
        for i in p:
            count[i] += 1
    ranked = sorted(range(15), key=lambda i: (-count[i], rng.random()))
    chosen = sorted(ranked[:4])
    planned = round(sum(prelim[i] for i in chosen) / 4)
    assess = planned / base * 100
    floor = -(-planned * rate // 100)  # 원 단위 올림

    bids = []
    for c in companies:
        # 업체마다 예상 사정률을 정하고 하한율을 곱해 투찰한다
        center = 100.4 if c != ME else 100.3
        guess = min(102.8, max(97.2, rng.gauss(center, 1.0)))
        amount = int(base * guess / 100 * rate / 100) + rng.randrange(0, 20) * 1000
        amount = amount // 1000 * 1000 + rng.randrange(0, 1000)
        bids.append({"company": c, "amount": amount, "pick": picks[c]})
    valid = sorted((b for b in bids if b["amount"] >= floor), key=lambda b: b["amount"])
    winner = valid[0]["company"] if valid else None
    for b in bids:
        b["bidRate"] = round(b["amount"] / base * 100, 4)  # 투찰률(기초금액 대비)
        b["impliedAssess"] = round(b["amount"] / base * 100 / rate * 100, 4)  # 투찰이 가정한 사정률
        b["result"] = "낙찰" if b["company"] == winner else ("하한 미달" if b["amount"] < floor else "탈락")
    return {
        "no": f"R26BK{no:08d}",
        "title": f"{rng.choice(AGENCIES)} {rng.choice(WORKS)}",
        "date": day.isoformat(),
        "base": base,
        "lowerRate": rate,
        "prelim": prelim,
        "chosen": chosen,
        "planned": planned,
        "assess": round(assess, 4),
        "floor": floor,
        "bids": bids,
    }


def main():
    rng = random.Random(SEED)
    day = date(2026, 3, 9)
    no = 10247311
    bids = []
    for _ in range(20):
        day += timedelta(days=rng.randrange(4, 12))
        no += rng.randrange(800, 9000)
        bids.append(make_bid(rng, no, day, rng.sample(RIVALS, 4)))
    data = {"me": ME, "bids": bids}

    page = PAGE.read_text(encoding="utf-8")
    marker = re.compile(r"(/\* BIDS:START \*/\n).*?(\n\s*/\* BIDS:END \*/)", re.S)
    embed = "  const DATA = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";"
    page, n = marker.subn(lambda m: m[1] + embed + m[2], page)
    if n != 1:
        raise SystemExit("index.html에서 BIDS:START/END 표시를 찾지 못했습니다.")
    PAGE.write_text(page, encoding="utf-8")

    rates = [b["assess"] for b in bids]
    wins = sum(1 for b in bids for x in b["bids"] if x["company"] == ME and x["result"] == "낙찰")
    print(f"사정률 {min(rates):.3f}~{max(rates):.3f}%, 평균 {sum(rates)/len(rates):.3f}%, {ME} 낙찰 {wins}건")


if __name__ == "__main__":
    main()
