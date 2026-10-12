@echo off
rem cheongyakkok -> Naver blog category post. Task CheongyakkokNaverPost: Sun/Wed 19:20 local = Mon/Thu morning KST.
rem Mon: weekly schedule roundup / Thu: next week's 3 big complexes. Data: data\blogdata.json from daily 15:40 site build.
cd /d C:\Users\Master\Documents\cheongyakradar
set PYTHONIOENCODING=utf-8
C:\Users\Master\AppData\Local\Programs\Python\Python312\python.exe blogpost.py auto >> blogpost_log.txt 2>&1
cd /d C:\Users\Master\Documents\pgodrl77\naver-blog
C:\Users\Master\AppData\Local\Programs\Python\Python312\python.exe daily.py --queue queue_cy >> daily_run.txt 2>&1
