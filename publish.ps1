# 청약콕 매일 갱신: 사이트 생성 후 gh-pages 브랜치로 올림 (선박 PC 작업 스케줄러에서 실행)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"
python build.py *> build.log
if ((Get-ChildItem site\apt).Count -lt 1) { throw "단지 페이지 0개 - 올리지 않음" }
Set-Content site\CNAME "cheongyakkok.com" -NoNewline -Encoding ASCII
$url = git remote get-url origin
Push-Location site
if (Test-Path .git) { Remove-Item .git -Recurse -Force }
git init -q -b gh-pages
git add -A
git -c user.name=pgodrl77 -c user.email=pgodrl77@users.noreply.github.com commit -q -m ("자동 갱신 " + (Get-Date -Format "yyyy-MM-dd HH:mm"))
git push -q -f $url gh-pages
Pop-Location
# IndexNow: GitHub Pages 배포가 끝난 뒤(키 파일이 열려야 함) 바뀐 페이지만 빙·네이버에 알림. 실패해도 갱신은 성공 처리
Start-Sleep 90
try { python indexnow.py *>> build.log } catch { "IndexNow 실패: $_" | Out-File -Append build.log }
"OK " + (Get-Date)
