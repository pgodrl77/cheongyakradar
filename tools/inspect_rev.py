import io, re, pathlib
R = pathlib.Path(__file__).resolve().parent.parent
s = io.open(R / "build.py", encoding="utf-8").read()
for k in ["ADSENSE_CLIENT =", "CPA = ", "CPA_LINKS", "def cpa_html", "def ad_slot"]:
    i = s.find(k)
    print("==", k, s[i:i + 900] if i >= 0 else "NONE")
print("coupang links:", len(re.findall(r"link\.coupang\.com", s)))
m = io.open(R / "moveday.py", encoding="utf-8").read()
print("moveday coupang:", len(re.findall(r"coupang", m)), "cpa refs:", len(re.findall(r"cpa", m)))
print("apt pages:", len(list((R / "site" / "apt").glob("*.html"))))
