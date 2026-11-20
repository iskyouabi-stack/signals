import ccxt, json, os, time
import pandas as pd

EX = ccxt.kucoin()  # Binance محجوب غالبًا على سيرفرات Colab
PAIRS = ["BTC/USDT","ETH/USDT","SOL/USDT","BNB/USDT",
         "XRP/USDT","LINK/USDT","ADA/USDT","AVAX/USDT"]
TF, FILE = "1h", "signals.json"

def get(pair, limit=200):
    o = EX.fetch_ohlcv(pair, TF, limit=limit)
    return pd.DataFrame(o, columns=["t","o","h","l","c","v"])

def ind(d):
    c = d.c
    d["e20"] = c.ewm(span=20).mean()
    d["e50"] = c.ewm(span=50).mean()
    ch = c.diff()
    up = ch.clip(lower=0).ewm(alpha=1/14).mean()
    dn = (-ch.clip(upper=0)).ewm(alpha=1/14).mean()
    d["rsi"] = 100 - 100/(1 + up/dn)
    m = c.ewm(span=12).mean() - c.ewm(span=26).mean()
    d["hist"] = m - m.ewm(span=9).mean()
    tr = pd.concat([d.h-d.l, (d.h-c.shift()).abs(),
                    (d.l-c.shift()).abs()], axis=1).max(axis=1)
    d["atr"] = tr.ewm(alpha=1/14).mean()
    d["vr"] = d.v / d.v.rolling(20).mean()
    return d

def score(d):
    x, y = d.iloc[-2], d.iloc[-3]  # آخر شمعة مغلقة
    if x.e20 <= x.e50:
        return 0, x
    s = 30
    s += 10 if x.c > x.e20 else 0
    s += 20 if 45 <= x.rsi <= 65 else 0
    s += 20 if x.hist > 0 and x.hist > y.hist else 0
    s += 10 if x.vr > 1.2 else 0
    return s, x

def r(v): return float(f"{v:.5g}")

def update(sigs):
    for g in sigs:
        if g["s"] not in ("open", "tp1"):
            continue
        d = get(g["pair"])
        for _, c in d[d.t > g["ts"]].iterrows():
            if g["s"] == "open":
                if c.l <= g["sl"]: g["s"] = "sl"; break
                if c.h >= g["t2"]: g["s"] = "tp2"; break
                if c.h >= g["t1"]: g["s"] = "tp1"
            elif c.h >= g["t2"]:
                g["s"] = "tp2"; break

sigs = json.load(open(FILE)) if os.path.exists(FILE) else []
update(sigs)
busy = {g["pair"] for g in sigs if g["s"] in ("open", "tp1")}

for p in PAIRS:
    if p in busy: continue
    d = ind(get(p))
    sc, x = score(d)
    if sc >= 60:
        e = d.iloc[-1].c
        a = x.atr
        sigs.append({"pair": p, "e": r(e), "sl": r(e-1.5*a),
                     "t1": r(e+1.5*a), "t2": r(e+3*a),
                     "c": sc, "s": "open", "ts": int(time.time()*1000)})
        print("إشارة جديدة:", p, "ثقة", sc)

json.dump(sigs, open(FILE, "w"), ensure_ascii=False, indent=1)
w = sum(g["s"] in ("tp1","tp2") for g in sigs)
l = sum(g["s"] == "sl" for g in sigs)
print(f"رابحة {w} | خاسرة {l} | مفتوحة {len(sigs)-w-l}")
