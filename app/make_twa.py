"""청약콕 안드로이드 앱(TWA) 패키지 요청 — PWABuilder 클라우드 빌더에서 서명 없이(signingMode none) 받고,
업로드 키(PC .secrets 에만 보관)로 따로 서명한다. 버전 올릴 때 VERSION/CODE 만 바꿔 다시 실행."""
import json, pathlib, urllib.request

HERE = pathlib.Path(__file__).resolve().parent
VERSION, CODE = "1.0.0", 1
SITE = "https://cheongyakkok.com"
opts = {
    "appVersion": VERSION, "appVersionCode": CODE,
    "backgroundColor": "#FFFFFF", "themeColor": "#1B64DA", "themeColorDark": "#1B64DA",
    "navigationColor": "#FFFFFF", "navigationColorDark": "#000000",
    "navigationDividerColor": "#FFFFFF", "navigationDividerColorDark": "#000000",
    "display": "standalone", "orientation": "portrait",
    "enableNotifications": True, "enableSiteSettingsShortcut": True,
    "fallbackType": "customtabs",
    "features": {"locationDelegation": {"enabled": False}, "playBilling": {"enabled": False}},
    "host": "cheongyakkok.com", "startUrl": "/?source=twa",
    "iconUrl": f"{SITE}/icon-512.png", "maskableIconUrl": f"{SITE}/icon-mask-512.png", "monochromeIconUrl": None,
    "includeSourceCode": False, "isChromeOSOnly": False, "isMetaQuest": False,
    "launcherName": "청약콕", "name": "청약콕 - 아파트 청약 일정",
    "packageId": "com.cheongyakkok.app",
    "shortcuts": [{"name": "청약 달력", "shortName": "청약 달력", "url": f"{SITE}/calendar.html", "icons": [{"src": f"{SITE}/icon-192.png", "sizes": "192x192"}]},
                  {"name": "가점 계산기", "shortName": "가점 계산기", "url": f"{SITE}/calc.html", "icons": [{"src": f"{SITE}/icon-192.png", "sizes": "192x192"}]}],
    "signing": None, "signingMode": "none",
    "splashScreenFadeOutDuration": 300, "minSdkVersion": 21,
    "webManifestUrl": f"{SITE}/manifest.webmanifest", "pwaUrl": SITE, "fullScopeUrl": SITE + "/",
    "additionalTrustedOrigins": [], "generatorApp": "PWABuilder",
}
req = urllib.request.Request("https://pwabuilder-cloudapk.azurewebsites.net/generateAppPackage",
                             data=json.dumps(opts).encode("utf-8"), headers={"Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=600) as r:
        data = r.read()
    out = HERE / f"cheongyakkok-{VERSION}-unsigned.zip"
    out.write_bytes(data)
    print("ok", out, len(data))
except urllib.error.HTTPError as e:
    print("HTTP", e.code, e.read().decode("utf-8", "ignore")[:1500])
