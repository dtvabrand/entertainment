import os,re,io,sys,zipfile,gzip,requests
from urllib.parse import quote,unquote
from datetime import datetime
from zoneinfo import ZoneInfo

RD=os.getenv("README_PATH","README.md"); DBG=os.getenv("DEBUG_DASH","0").strip() not in ("","0","false","False","no","No")
COL={"ok":"2ecc71","warn":"f39c12","token":"3498db","date":"95a5a6","run":"f1c40f","err":"e74c3c","a":"27ae60"}
SERV=("Trakt","Live TV")

def _dbg(*a):
    if DBG:
        try: print("[dash]",*a,flush=True)
        except: pass

def read(p,d=""):
    try:
        with io.open(p,"r",encoding="utf-8",errors="replace") as f: return f.read()
    except: return d

def write(p,t):
    with io.open(p,"w",encoding="utf-8") as f: f.write(t)

def repl_block(md,tag,body):
    a=f"<!-- {tag} -->"; b=f"<!-- /{tag} -->"; block=f"{a}\n{body}\n{b}"
    pat=re.compile(re.escape(a)+r".*?"+re.escape(b),re.S)
    return pat.sub(block,md) if pat.search(md) else (md+("\n" if not md.endswith("\n") else "")+block+"\n")

def read_block(md,tag):
    a,f=f"<!-- {tag} -->",f"<!-- /{tag} -->"; s,e=md.find(a),md.find(f)
    return "" if (s==-1 or e==-1 or e<s) else md[s+len(a):e].strip()

ANSI=re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x1b]*\x1b\\|\x1b\][^\x07]*\x07")
def clean_lines(t): return ANSI.sub("",(t or "").replace("\r","")).splitlines() if isinstance(t,str) else []

IT_MONTH=["gen","feb","mar","apr","mag","giu","lug","ago","set","ott","nov","dic"]
def ts_now_it():
    z=datetime.now(ZoneInfo("Europe/Rome")); d=f"{z.day:02d} {IT_MONTH[z.month-1]} {z.year}"; h=z.hour%12 or 12; m=f"{z.minute:02d}"; ap="am" if z.hour<12 else "pm"; return f"{d} {h}:{m} {ap}"

def shield(label,val,color): return f"https://img.shields.io/badge/{quote(label,safe='')}-{quote(str(val),safe='')}-{quote(color,safe='')}?cacheSeconds=300"
def badgen_run(ts,color): return f"https://badgen.net/badge/Run/{quote(ts,safe='')}/{quote(color,safe='')}"
def enc_badge(u,href): return f"[![X]({u})]({href})" if href else f"![X]({u})"

def gh_headers(extra=None):
    h={"User-Agent":"dash-updater"}; t=os.getenv("GITHUB_TOKEN","").strip()
    if t: h["Authorization"]=f"Bearer {t}"
    if extra: h.update(extra)
    return h

def http_get(url,h):
    try: return requests.get(url,headers=h,timeout=60,allow_redirects=True)
    except Exception as e: _dbg("http",e); return None

def list_jobs(owner,repo,run_id):
    r=http_get(f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}/jobs?per_page=100",gh_headers({"Accept":"application/vnd.github+json"}))
    if not r or r.status_code!=200: return []
    return r.json().get("jobs") or []

def find_job_and_step(owner,repo,run_id,prefer=("trakt","trakt lists","trakt_lists"),step_exact=("Run trakt","Run script"),step_prefix=("Run ",)):
    jobs=list_jobs(owner,repo,run_id); job=None
    for p in prefer:
        job=next((j for j in jobs if p.lower() in (j.get("name") or "").lower()),None)
        if job: break
    if not job: job=jobs[0] if jobs else None
    if not job: return None,None,None
    steps=job.get("steps") or []; idx=None
    for i,s in enumerate(steps,1):
        nm=(s.get("name") or "").strip()
        if nm in step_exact: idx=i; break
    if not idx:
        for i,s in enumerate(steps,1):
            nm=(s.get("name") or "").strip()
            if any(nm.startswith(p) for p in step_prefix): idx=i; break
    if not idx: idx=1
    return job.get("id"),idx,job

def fetch_job_log(owner,repo,job_id):
    r=http_get(f"https://api.github.com/repos/{owner}/{repo}/actions/jobs/{job_id}/logs",gh_headers({"Accept":"*/*"}))
    if not r or not getattr(r,"content",None): return ""
    b=r.content
    try:
        z=zipfile.ZipFile(io.BytesIO(b)); txt=[]
        for n in sorted(z.namelist()):
            with z.open(n) as f: txt.append(f.read().decode("utf-8","replace"))
        return "\n".join(txt)
    except Exception:
        try: return b.decode("utf-8","replace")
        except Exception:
            try: return gzip.decompress(b).decode("utf-8","replace")
            except Exception: return b.decode("latin-1","replace")

def group_starts(raw): return [i for i,l in enumerate(clean_lines(raw),1) if "##[group]Run " in l]
def nearest_group_start_before(raw,idx):
    s=[g for g in group_starts(raw) if g<=idx]
    return max(s) if s else None
def first_line(raw,needles):
    if not raw: return None
    for i,ln in enumerate(clean_lines(raw),1):
        for n in needles:
            if n in ln: return i
    return None

def parse_titles(txt):
    titles=[]
    for raw in clean_lines(txt):
        if "📝 QID for" in raw:
            payload=raw.split("📝 QID for",1)[1].strip()
            if payload.startswith(":"): payload=payload[1:].strip()
            parts=[p.strip() for p in payload.split(",") if p.strip()]
            for p in parts:
                if p not in titles: titles.append(p)
        elif raw.strip().startswith("🍿"):
            t=raw.split("🍿",1)[1].strip()
            if t and t not in titles: titles.append(t)
    return titles

def overall_badges(update_service,status):
    md=read(RD); badges=read_block(md,"OVERALL:BADGES"); hist=read_block(md,"OVERALL:HISTORY")
    def parse_imgs(b):
        msgs,cols={},{}
        if not b: return msgs,cols
        for s in SERV:
            m=re.search(rf'\[!\[{re.escape(s)}\]\((https://img\.shields\.io/[^)]+label={re.escape(s)}[^)]*)\)\]\(([^)]*)\)',b)
            if m:
                u=m.group(1); q=dict(x.split("=",1) for x in (u.split("?",1)[1] if "?" in u else "").split("&") if "=" in x)
                message=unquote((q.get("message") or "").replace("+"," ")); color=unquote(q.get("color") or "")
                msgs[s]=message; cols[s]=color
        return msgs,cols
    msgs,cols=parse_imgs(badges); m2,c2=parse_imgs(hist)
    for s in SERV:
        msgs[s]=msgs.get(s) or m2.get(s) or "pending, —"
        cols[s]=cols.get(s) or c2.get(s) or COL["date"]
    evt=os.getenv("RUN_EVENT","").strip(); evt="cron" if evt=="schedule" else (evt or "event"); stamp=ts_now_it()
    msgs[update_service]=f"{evt}, {stamp}"
    cols[update_service]=COL["ok"] if status=="success" else (COL["err"] if status=="failure" else COL["date"])
    owner_repo=(os.getenv("GITHUB_REPOSITORY") or "").split("/",1); owner=owner_repo[0] if owner_repo else ""; repo=owner_repo[1] if len(owner_repo)==2 else ""; run_id=(os.getenv("RUN_ID") or "").strip()
    def img(s): return f"https://img.shields.io/static/v1?label={quote(s,safe='')}&message={quote(msgs[s],safe='')}&color={quote(cols[s],safe='')}&cacheSeconds=300"
    base=f"https://github.com/{owner}/{repo}/actions/runs/{run_id}" if (owner and repo and run_id) else ""
    def last_href(hist,svc):
        m=re.search(r'\[!\['+re.escape(svc)+r'\]\([^)]+\)\]\(([^)]+)\)',hist)
        return m.group(1) if m else ""
    hrefs={}
    for s in SERV:
        hrefs[s]= base if s==update_service else (last_href(hist,s) or "")
    def wrap(s,href): u=img(s); return f"[![{s}]({u})]({href})" if href else f"![{s}]({u})"
    row=" ".join(wrap(s,hrefs[s]) for s in SERV)
    md=repl_block(md,"OVERALL:BADGES",row)
    today=datetime.now(ZoneInfo("Europe/Rome")).strftime("%Y-%m-%d"); key=f"dispatch:{run_id}" if (evt=="workflow_dispatch" and run_id) else (f"cron:{today}" if evt=="cron" else f"event:{today}")
    tag=f"<!-- SESSION:{key} -->"
    hist_lines=[l.strip() for l in read_block(md,"OVERALL:HISTORY").splitlines() if l.strip() and set(l.strip())-set("<>/br ")]
    updated=False
    for i,l in enumerate(hist_lines):
        if l.endswith(tag):
            hist_lines[i]=(row+" "+tag).strip(); updated=True; break
    if not updated:
        hist_lines=[(row+" "+tag).strip()]+hist_lines
    hist_lines=hist_lines[:30]
    md=repl_block(md,"OVERALL:HISTORY","<br>\n".join(hist_lines).strip()); write(RD,md)

def update_trakt(log_path,status="success"):
    md=read(RD); txt=read(log_path,""); titles=parse_titles(txt); new_count=len(titles)
    err=("🧩 Need new refresh token!" in txt); refreshed=("🔄 Trakt token refresh completed" in txt); valid=("🔐 Trakt token valid" in txt)
    token_state="expired" if err else ("refreshed" if refreshed else ("valid" if valid else "unknown"))
    token_color=COL["err"] if token_state=="expired" else (COL["ok"] if token_state=="refreshed" else (COL["token"] if token_state=="valid" else COL["date"]))
    owner_repo=(os.getenv("GITHUB_REPOSITORY") or "").split("/",1); owner=owner_repo[0] if owner_repo else ""; repo=owner_repo[1] if len(owner_repo)==2 else ""; run_id=os.getenv("RUN_ID","").strip()
    job_id=step_idx=ln_movies=ln_token=None; raw=""
    if owner and repo and run_id:
        job_id,step_idx,_=find_job_and_step(owner,repo,run_id)
        raw=fetch_job_log(owner,repo,job_id) if job_id else ""
        if raw:
            gi=first_line(raw,["📝 QID for","🍿 "]); gs=nearest_group_start_before(raw,gi) if gi else None; ln_movies=(gi-gs+1) if (gi and gs) else None
            t_needles=("🔄 Trakt token refresh completed",) if token_state=="refreshed" else (("🔐 Trakt token valid",) if token_state=="valid" else (("🧩 Need new refresh token!",) if token_state=="expired" else ()))
            gt=first_line(raw,t_needles) if t_needles else None; st=nearest_group_start_before(raw,gt) if gt else None; ln_token=(gt-st+1) if (gt and st) else None
            if ln_movies is not None and ln_movies<1: ln_movies=1
            if ln_token is not None and ln_token<1: ln_token=1
    nm=shield("New Movie",new_count,COL["a"]); tk=shield("Token",token_state,token_color); runb=badgen_run(ts_now_it(),COL["run"])
    base=f"https://github.com/{owner}/{repo}/actions/runs/{run_id}" if (owner and repo and run_id) else ""
    href_movies=(f"{base}/job/{job_id}#step:{step_idx}:{ln_movies}" if (base and job_id and step_idx and ln_movies) else base)
    href_token=(f"{base}/job/{job_id}#step:{step_idx}:{ln_token}" if (base and job_id and step_idx and ln_token) else base)
    href_run=(base or "")
    dash=" ".join([enc_badge(nm,href_movies),enc_badge(tk,href_token),enc_badge(runb,href_run)])
    md=repl_block(md,"DASH:TRAKT",dash)
    latest="<br>\n".join(["🍿 "+t for t in titles]) if titles else ""
    md=repl_block(md,"TRAKT:OUTPUT",latest)
    sent=f"<!-- TRAKT_RUN:{run_id} -->" if run_id else ""
    prev=read_block(md,"TRAKT:HISTORY")
    if run_id: prev=re.sub(r'(?ms)^.*?<!-- TRAKT_RUN:'+re.escape(run_id)+r' -->.*?(?:\n(?!\s*!\[).*)*','',prev).strip()
    chunk=(" ".join([enc_badge(nm,href_movies),enc_badge(tk,href_token),enc_badge(runb,href_run),sent]).strip()+(("""<br>\n"""+latest) if latest else ""))
    parts=[x for x in (prev or "").split("\n\n") if x.strip()]
    new_hist=(chunk+("\n\n"+("\n\n".join(parts[:29])) if parts else "")).strip()
    md=repl_block(md,"TRAKT:HISTORY",new_hist); write(RD,md)
    overall_badges("Trakt","failure" if err else ("success" if (refreshed or valid) else "neutral"))

def parse_tv_table_and_badges(log_path):
    raw=read(log_path,""); M=D="0"; rows=[]; notes=[]; fails=[]
    if not raw:
        hb=f"{enc_badge(shield('M','0',COL['a']), '')} {enc_badge(shield('D','0',COL['a']), '')} {enc_badge(badgen_run(ts_now_it(),COL['run']), '')}"
        head="| Site | M | D | Status |\n|---|---:|---:|---|\n"
        return {"M":"0","D":"0","table":head,"notes":"","hist_badges":hb,"raw":raw}
    m=re.search(r"m_epg\.xml\s*->\s*(\d+)\s+channels",raw); M=m.group(1) if m else "0"
    d=re.search(r"d_epg\.xml\s*->\s*(\d+)\s+channels",raw); D=d.group(1) if d else "0"
    for g,site,n in re.findall(r">\s*(main|d)\s+([a-z0-9\.\-]+)\s*:\s*(\d+)\s+channels",raw): rows.append((g,site,int(n)))
    site_counts={}
    for g,site,n in rows:
        s=site_counts.setdefault(site,{"M":0,"D":0,"warn":set(),"fail":False})
        if g=="main": s["M"]+=n
        else: s["D"]+=n
    for site in list(site_counts.keys()):
        if re.search(rf"FAIL\s+(main|d)\s+{re.escape(site)}",raw): s=site_counts[site]; s["fail"]=True
    for site,chan,progs in re.findall(r"([a-z0-9\.\-]+).*?-\s*([a-z0-9\-\s]+)\s*-\s*[A-Z][a-z]{{2}}\s+\d{{1,2}},\s*\d{{4}}\s*\((\d+)\s+programs\)",raw,re.I):
        if site in site_counts and int(progs)==0: site_counts[site]["warn"].add(re.sub(r"\s+"," ",chan.strip()))
    lines=[]
    for site in sorted(site_counts.keys()):
        s=site_counts[site]; st="✅"
        if s["fail"]: st="❌"
        elif s["warn"]: st="⚠️"
        lines.append(f"| {site} | {s['M']} | {s['D']} | {st} |")
        if s["warn"]: notes.extend(sorted(s["warn"]))
        if s["fail"]: fails.append(site)
    head="| Site | M | D | Status |\n|---|---:|---:|---|\n"; table=head+("\n".join(lines) if lines else "")
    extra=[]
    if notes:
        uniq=[]; [uniq.append(x) for x in notes if x not in uniq]; extra.append(f"⚠️ Notes\n{len(uniq)} channels without EPG: {', '.join(uniq)}")
    if fails: extra.append(f"❌ Failures\n{len(set(fails))} site(s) error: {', '.join(sorted(set(fails)))}")
    hb=f"{shield('M',M,COL['a'])} {shield('D',D,COL['a'])} {badgen_run(ts_now_it(),COL['run'])}"
    return {"M":M,"D":D,"table":table,"notes":"\n\n".join(extra),"hist_badges":hb,"raw":raw}

def update_tv(log_path,status="success"):
    md=read(RD); tv=parse_tv_table_and_badges(log_path)
    owner_repo=(os.getenv("GITHUB_REPOSITORY") or "").split("/",1); owner=owner_repo[0] if owner_repo else ""; repo=owner_repo[1] if len(owner_repo)==2 else ""; run_id=os.getenv("RUN_ID","").strip()
    job_id=os.getenv("TV_JOB_ID","").strip(); step_idx=os.getenv("TV_STEP_IDX","5").strip()
    ln_m = tv.get("ln_m"); ln_d = tv.get("ln_d")
    base=f"https://github.com/{owner}/{repo}/actions/runs/{run_id}" if (owner and repo and run_id) else ""
    href_m=(f"{base}/job/{job_id}#step:{step_idx}:{ln_m}" if (base and job_id and step_idx and ln_m) else base)
    href_d=(f"{base}/job/{job_id}#step:{step_idx}:{ln_d}" if (base and job_id and step_idx and ln_d) else base)
    href_run=(base or "")
    s_m=shield('M',tv['M'],COL['a']); s_d=shield('D',tv['D'],COL['a']); s_run=badgen_run(ts_now_it(),COL['run'])
    dash=" ".join([enc_badge(s_m,href_m),enc_badge(s_d,href_d),enc_badge(s_run,href_run)])
    md=repl_block(md,"DASH:TV",dash)
    md=repl_block(md,"TV:OUTPUT",tv["table"]+("\n\n"+tv["notes"] if tv["notes"] else ""))
    hist_badges=f"{enc_badge(s_m, href_m)} {enc_badge(s_d, href_d)} {enc_badge(s_run, href_run)}"
    prev=read_block(md,"TV:HISTORY"); chunk=hist_badges + (("<br>\n"+tv["notes"]) if tv["notes"] else ""); parts=[x for x in (prev or "").split("\n\n") if x.strip()]
    new_hist=(chunk+("\n\n"+("\n\n".join(parts[:29])) if parts else "")).strip()
    md=repl_block(md,"TV:HISTORY",new_hist)
    write(RD,md); overall_badges("Live TV","success" if status=="success" else "failure")

def main():
    if len(sys.argv)<2: print("Usage:\n  dashboard.py trakt --log trakt_run.log [--status success|failure]\n  dashboard.py tv --log tv_epg.log [--status success|failure]"); sys.exit(1)
    mode=sys.argv[1].lower(); arg=lambda f,d=None: sys.argv[sys.argv.index(f)+1] if f in sys.argv else d
    if mode=="trakt":
        lp=arg("--log","trakt_run.log"); st=arg("--status","success");
        try: update_trakt(lp,st)
        except Exception as e: _dbg("fatal trakt",e); overall_badges("Trakt","failure")
    elif mode=="tv":
        lp=arg("--log","tv_epg.log"); st=arg("--status","success");
        try: update_tv(lp,st)
        except Exception as e: _dbg("fatal tv",e); overall_badges("Live TV","failure")
    else: sys.exit(2)
    msg=os.getenv("DASH_COMMIT_MSG","").strip()
    if msg:
        os.system('git config user.name "github-actions"'); os.system('git config user.email "github-actions@github.com"')
        os.system('git add README.md'); os.system(f'git commit -m "{msg}" || true'); os.system('git push || true')

if __name__=="__main__": main()
