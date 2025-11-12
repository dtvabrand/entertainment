import os,re,io,sys,zipfile,gzip,html,urllib.parse,datetime
try: import requests
except: requests=None
from zoneinfo import ZoneInfo

RD="README.md"; TZ="Europe/Rome"
NOW_UTC=datetime.datetime.utcnow().replace(microsecond=0,tzinfo=datetime.timezone.utc)
def _now_local(): 
    try: return NOW_UTC.astimezone(ZoneInfo(TZ))
    except: return NOW_UTC

MONTHS=["gen","feb","mar","apr","mag","giu","lug","ago","set","ott","nov","dic"]
def fmt_dt(dt):
    y,m,d,h,mi=dt.year,dt.month,dt.day,dt.hour,dt.minute
    ampm="am" if h<12 else "pm"; hh=h%12 or 12
    return f"{d:02d} {MONTHS[m-1]} {y} {hh}:{mi:02d} {ampm}"

def read(p): 
    try: 
        with open(p,"r",encoding="utf-8",errors="replace") as f: return f.read()
    except: return ""
def write(p,s): 
    with open(p,"w",encoding="utf-8") as f: f.write(s)
def sub_block(txt,tag,new):
    a=f"<!-- {tag} -->"; b=f"<!-- /{tag} -->"; block=f"{a}\n{new}\n{b}"
    pat=re.compile(re.escape(a)+r"[\s\S]*?"+re.escape(b),re.M)
    return pat.sub(block,txt) if pat.search(txt) else (txt+("\n" if not txt.endswith("\n") else "")+block+"\n")
def read_block(md,tag):
    a=f"<!-- {tag} -->"; b=f"<!-- /{tag} -->"; s=md.find(a); e=md.find(b)
    return "" if (s==-1 or e==-1 or e<s) else md[s+len(a):e].strip()

def _enc(s): return urllib.parse.quote(str(s or ""),safe="")
def _shield(label,msg,color): return f"https://img.shields.io/static/v1?label={_enc(label)}&message={_enc(msg)}&color={_enc(color)}&cacheSeconds=300"
def _img(url,href=None,alt="X"): return f"[![{alt}]({url})]({href})" if href else f"![{alt}]({url})"
def _badgen_run(ts,color="f1c40f",href=None): return _img(f"https://badgen.net/badge/Run/{_enc(ts)}/{_enc(color)}",href)

ANSI=re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x1b]*\x1b\\|\x1b\][^\x07]*\x07")
def _clean(t): return ANSI.sub("",(t or "").replace("\r","")) if isinstance(t,str) else ""
def _list_jobs(owner,repo,run_id):
    if not requests: return []
    u=f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}/jobs?per_page=100"
    try:
        r=requests.get(u,headers={"Accept":"application/vnd.github+json","User-Agent":"dash"},timeout=60)
        return r.json().get("jobs") if r and r.status_code==200 else []
    except: return []
def _fetch_job_raw(owner,repo,job_id):
    if not requests: return ""
    u=f"https://api.github.com/repos/{owner}/{repo}/actions/jobs/{job_id}/logs"
    try:
        r=requests.get(u,headers={"Accept":"*/*","User-Agent":"dash"},timeout=120)
        b=r.content if r else b""
        try:
            z=zipfile.ZipFile(io.BytesIO(b)); txt=[]
            for n in sorted(z.namelist()):
                with z.open(n) as f: txt.append(f.read().decode("utf-8","replace"))
            return "\n".join(txt)
        except:
            try: return b.decode("utf-8","replace")
            except:
                try: return gzip.decompress(b).decode("utf-8","replace")
                except: return b.decode("latin-1","replace")
    except: return ""
def _find_trakt_job(owner,repo,run_id):
    jobs=_list_jobs(owner,repo,run_id); job=None
    prefs=("trakt","trakt lists","trakt_lists")
    for p in prefs:
        job=next((j for j in jobs if p in (j.get("name","").lower())),None)
        if job: break
    job=job or (jobs[0] if jobs else None)
    if not job: return None,None,None
    steps=job.get("steps") or []; idx=None
    for i,s in enumerate(steps,start=1):
        nm=(s.get("name") or "").strip()
        if nm in ("Run trakt","Run script"): idx=i; break
    if not idx:
        for i,s in enumerate(steps,start=1):
            if (s.get("name") or "").strip().startswith("Run "): idx=i; break
    idx=idx or 1
    return job.get("id"),idx,job

def _group_starts(raw): 
    L=_clean(raw).splitlines()
    return [i for i,l in enumerate(L,1) if "##[group]Run " in l or l.strip().startswith("::group::Run ")]
def _nearest_group_start_before(raw,ln):
    starts=[s for s in _group_starts(raw) if s<=ln]; return max(starts) if starts else None
def _first_line_idx(raw,needles):
    L=_clean(raw).splitlines()
    for i,ln in enumerate(L,1):
        for n in needles:
            if n in ln: return i
    return None

def _run_env():
    repo=os.getenv("GITHUB_REPOSITORY",""); owner,repo=(repo.split("/",1)+[""])[:2]
    run_id=os.getenv("GITHUB_RUN_ID") or os.getenv("RUN_ID") or ""
    evt=os.getenv("GITHUB_EVENT_NAME") or os.getenv("RUN_EVENT") or ""
    href=f"https://github.com/{owner}/{repo}/actions/runs/{run_id}" if (owner and repo and run_id) else ""
    return owner,repo,run_id,evt,href

def parse_trakt(log):
    raw=read(log); token="unknown"
    if "🧩 Need new refresh token!" in raw: token="failed"
    elif "Trakt token refresh completed" in raw: token="refreshed"
    elif "🔐 Trakt token valid" in raw or "Trakt token valid" in raw: token="valid"
    m=re.search(r"New Movie\(s\):\s*(\d+)",raw,re.I); new=m.group(1) if m else "0"
    titles=[t.strip() for t in re.findall(r"🍿\s*(.+)",raw)]; out=("🍿 "+", ".join(titles)) if titles else ""
    return {"new":new,"token":token,"out":out,"raw":raw}

def parse_tv(log):
    if not os.path.exists(log): 
        return {"M":"0","D":"0","table":"| Site | M | D | Status |\n|---|---:|---:|---|\n","notes":""}
    raw=read(log)
    m=re.search(r"m_epg\.xml\s*->\s*(\d+)\s+channels",raw); M=m.group(1) if m else "0"
    d=re.search(r"d_epg\.xml\s*->\s*(\d+)\s+channels",raw); D=d.group(1) if d else "0"
    site_counts={}
    for g,site,n in re.findall(r">\s*(main|d)\s+([a-z0-9\.\-]+)\s*:\s*(\d+)\s+channels",raw): s=site_counts.setdefault(site,{"M":0,"D":0,"warn":set(),"fail":False}); (s["M"] if g=="main" else s["D"]).__iadd__(int(n))
    for site in list(site_counts.keys()):
        if re.search(rf"FAIL\s+(main|d)\s+{re.escape(site)}",raw): site_counts[site]["fail"]=True
    for site,chan,progs in re.findall(r"([a-z0-9\.\-]+).*?-\s*([a-z0-9\-\s]+)\s*-\s*[A-Z][a-z]{{2}}\s+\d{{1,2}},\s*\d{{4}}\s*\((\d+)\s+programs\)",raw,re.I):
        if site in site_counts and int(progs)==0: site_counts[site]["warn"].add(re.sub(r"\s+"," ",chan.strip()))
    rows=[]; notes=[]; fails=[]
    for site in sorted(site_counts.keys()):
        s=site_counts[site]; status="✅"
        if s["fail"]: status="❌"
        elif s["warn"]: status="⚠️"
        rows.append(f"| {site} | {s['M']} | {s['D']} | {status} |")
        if s["warn"]: notes.extend(sorted(s["warn"]))
        if s["fail"]: fails.append(site)
    head="| Site | M | D | Status |\n|---|---:|---:|---|\n"; table=head+("\n".join(rows) if rows else "")
    extra=[]; 
    if notes:
        uniq=[]; [uniq.append(x) for x in notes if x not in uniq]; extra.append(f"⚠️ Notes\n{len(uniq)} channels without EPG: {', '.join(uniq)}")
    if fails: extra.append(f"❌ Failures\n{len(set(fails))} site(s) error: {', '.join(sorted(set(fails)))}")
    return {"M":M,"D":D,"table":table,"notes":"\n\n".join(extra)}

def _link_targets_for_trakt(titles_badge=True,token_badge=True):
    owner,repo,run_id,_,_= _run_env()
    if not (owner and repo and run_id and requests): return None,None,None,None
    job_id,step_idx,_=_find_trakt_job(owner,repo,run_id)
    raw=_fetch_job_raw(owner,repo,job_id) if job_id else ""
    gi=_first_line_idx(raw,["📝 QID for","🍿 "]) if titles_badge else None
    gs=_nearest_group_start_before(raw,gi) if gi else None
    rel_titles=(gi-gs+1) if (gi and gs) else None
    gtok=_first_line_idx(raw,["🔐 Trakt token valid","⏳ Trakt token expired. Refreshing...","🔄 Trakt token refresh completed","Trakt token valid","Trakt token expired","Trakt token refresh completed"]) if token_badge else None
    gs2=_nearest_group_start_before(raw,gtok) if gtok else None
    rel_token=(gtok-gs2+1) if (gtok and gs2) else None
    if rel_titles is not None and rel_titles<1: rel_titles=1
    if rel_token is not None and rel_token<1: rel_token=1
    return job_id,step_idx,rel_titles,rel_token

def _run_link(owner,repo,run_id,job=None,step=None,line=None):
    if not (owner and repo and run_id): return None
    base=f"https://github.com/{owner}/{repo}/actions/runs/{run_id}"
    if job and step and line: return f"{base}/job/{job}#step:{step}:{line}"
    if job and step: return f"{base}/job/{job}#step:{step}"
    if job: return f"{base}/job/{job}"
    return base

def append_history(txt,tag,entry):
    prev=read_block(txt,tag); rid=os.getenv("GITHUB_RUN_ID") or ""
    new_entry=f"{entry} <!-- {tag.split(':')[0]}_RUN:{rid} -->"
    pieces=[new_entry]+([p for p in prev.split("\n\n") if p.strip()] if prev else [])
    return sub_block(txt,tag,("\n\n".join(pieces[:30])).strip())

def update_overall(txt,svc,status,link_href):
    badges=read_block(txt,"OVERALL:BADGES"); hist=read_block(txt,"OVERALL:HISTORY")
    def parse_one(lbl,block):
        m=re.search(rf'\[!\[{re.escape(lbl)}\]\(([^)]+)\)\](?:\(([^)]+)\))?',block or "")
        if not m:
            m2=re.search(rf'!\[{re.escape(lbl)}\]\(([^)]+)\)',block or "")
            return (urllib.parse.unquote_plus("pending,%20%E2%80%94"),"95a5a6",None)
        url=m.group(1); href=m.group(2) if m.lastindex and m.lastindex>=2 else None
        q=urllib.parse.parse_qs(urllib.parse.urlparse(url).query); msg=(q.get("message") or ["pending, —"])[0]; col=(q.get("color") or ["95a5a6"])[0]
        return (urllib.parse.unquote(msg),urllib.parse.unquote(col),href)
    def mk(lbl,msg,col,href): return _img(_shield(lbl,msg,col),href,alt=lbl)
    cur_tr,cur_tr_col,cur_tr_href=parse_one("Trakt",badges)
    cur_tv,cur_tv_col,cur_tv_href=parse_one("Live TV",badges)
    other="Live TV" if svc=="Trakt" else "Trakt"
    ev=os.getenv("GITHUB_EVENT_NAME") or os.getenv("RUN_EVENT") or ""
    ev="cron" if ev=="schedule" else (ev if ev else "event")
    ts=fmt_dt(_now_local())
    if svc=="Trakt":
        new_tr=(f"{ev}, {ts}",("2ecc71" if status=="success" else "e74c3c"),link_href)
        new_tv=(cur_tv,cur_tv_col,cur_tv_href) if ("pending" not in cur_tv) else ("pending, —","95a5a6",None)
    else:
        new_tv=(f"{ev}, {ts}",("2ecc71" if status=="success" else "e74c3c"),link_href)
        new_tr=(cur_tr,cur_tr_col,cur_tr_href) if ("pending" not in cur_tr) else ("pending, —","95a5a6",None)
    row=" ".join([mk("Trakt",new_tr[0],new_tr[1],new_tr[2]), mk("Live TV",new_tv[0],new_tv[1],new_tv[2])])
    txt=sub_block(txt,"OVERALL:BADGES",row)
    prev=read_block(txt,"OVERALL:HISTORY")
    if svc=="Trakt":
        line=" ".join([mk("Trakt",new_tr[0],new_tr[1],new_tr[2]), mk("Live TV",new_tv[0],new_tv[1],new_tv[2])])
    else:
        line=" ".join([mk("Trakt",new_tr[0],new_tr[1],new_tr[2]), mk("Live TV",new_tv[0],new_tv[1],new_tv[2])])
    lines=[line]+([l for l in (prev.split("<br>\n") if prev else []) if l.strip()])
    txt=sub_block(txt,"OVERALL:HISTORY","<br>\n".join(lines[:30]))
    return txt

def section_trakt(rd,log,status):
    t=parse_trakt(log); owner,repo,run_id,evt,base=_run_env()
    job,step,rel_titles,rel_token=_link_targets_for_trakt()
    nm=_img(_shield("New Movie",t["new"],"27ae60"),_run_link(owner,repo,run_id,job,step,rel_titles))
    tok_color="2ecc71" if t["token"]=="refreshed" else "3498db" if t["token"]=="valid" else "e67e22" if t["token"]=="unknown" else "e74c3c"
    tk=_img(_shield("Token",t["token"],tok_color),_run_link(owner,repo,run_id,job,step,rel_token))
    run_badge=_badgen_run(fmt_dt(_now_local()),"f1c40f",base)
    rd=sub_block(rd,"DASH:TRAKT"," ".join([nm,tk,run_badge]))
    rd=sub_block(rd,"TRAKT:OUTPUT",(t["out"] or ""))
    rd=append_history(rd,"TRAKT:HISTORY"," ".join([nm,tk,run_badge]) + ((" <br>\n"+t["out"]) if t["out"] else ""))
    rd=update_overall(rd,"Trakt",status,base if run_id else None)
    return rd

def section_tv(rd,log,status):
    tv=parse_tv(log); owner,repo,run_id,evt,base=_run_env()
    run_badge=_badgen_run(fmt_dt(_now_local()),"f1c40f",base)
    dash=" ".join([_img(_shield("M",tv["M"],"27ae60"),base),_img(_shield("D",tv["D"],"27ae60"),base),run_badge])
    rd=sub_block(rd,"DASH:TV",dash)
    rd=sub_block(rd,"TV:OUTPUT",tv["table"]+("\n\n"+tv["notes"] if tv["notes"] else ""))
    rd=append_history(rd,"TV:HISTORY",dash)
    rd=update_overall(rd,"Live TV",status,base if run_id else None)
    return rd

def run(mode,trakt_log,tv_log,status):
    rd=read(RD)
    if mode=="trakt": rd=section_trakt(rd,trakt_log,status)
    elif mode=="tv": rd=section_tv(rd,tv_log,status)
    else:
        rd=section_trakt(rd,trakt_log,status); rd=section_tv(rd,tv_log,status)
    write(RD,rd)
    msg=os.getenv("DASH_COMMIT_MSG","").strip()
    if msg:
        os.system('git config user.name "github-actions"'); os.system('git config user.email "github-actions@github.com"')
        os.system('git add README.md'); os.system(f'git commit -m "{msg}" || true'); os.system('git push || true')

if __name__=="__main__":
    mode="both"; trakt_log=os.getenv("TRAKT_LOG","trakt_run.log"); tv_log=os.getenv("TV_LOG","tv_epg.log")
    status=os.getenv("STATUS") or os.getenv("TRAKT_STATUS") or "success"
    args=sys.argv[1:]; 
    if args: mode=args[0].lower()
    if "--log" in args:
        i=args.index("--log")
        if i+1<len(args):
            if mode=="trakt": trakt_log=args[i+1]
            elif mode=="tv": tv_log=args[i+1]
    run(mode,trakt_log,tv_log,status)
