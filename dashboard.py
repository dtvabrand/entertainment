import os,re,io,sys,zipfile,gzip,requests,xml.etree.ElementTree as ET
from urllib.parse import quote,unquote
from datetime import datetime
from zoneinfo import ZoneInfo

RD=os.getenv("README_PATH","README.md"); DBG=os.getenv("DEBUG_DASH","0").strip() not in ("","0","false","False","no","No")
COL={"ok":"2cc36b","warn":"f1d70f","token":"34a6db","date":"95a5a6","run":"f1d70f","err":"e74c3c"}

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
    z=datetime.now(ZoneInfo("Europe/Rome")); d=f"{z.day} {IT_MONTH[z.month-1]} {z.year}"; h=z.hour%12 or 12; m=f"{z.minute:02d}"; ap="am" if z.hour<12 else "pm"; return f"{d} {h}:{m} {ap}"

def shield(label,val,color): return f"https://img.shields.io/badge/{quote(label,safe='')}-{quote(str(val),safe='')}-{quote(color,safe='')}?cacheSeconds=300"
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

def find_tv_job_and_step(owner,repo,run_id):
    jobs=list_jobs(owner,repo,run_id)
    job=next((j for j in jobs if "build epg" in (j.get("name","").lower())),None) or (jobs[0] if jobs else None)
    if not job: return None,None
    steps=job.get("steps") or []; idx=None
    for i,s in enumerate(steps,1):
        if (s.get("name") or "").strip()=="Build EPG": idx=i; break
    if not idx: idx=int(os.getenv("TV_STEP_IDX","5") or "5")
    return job.get("id"),idx

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

def first_line_re(raw,pat):
    if not raw: return None
    rg=re.compile(pat)
    for i,ln in enumerate(clean_lines(raw),1):
        if rg.search(ln): return i
    return None

def last_line_re_excluding(raw,pat,exclude_subs=()):
    if not raw: return None
    rg=re.compile(pat); idx=None
    for i,ln in enumerate(clean_lines(raw),1):
        if rg.search(ln) and not any(x in ln for x in exclude_subs): idx=i
    return idx

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
    nm=shield("New Movie",new_count,COL["warn"]); tk=shield("Token",token_state,token_color)
    ts=ts_now_it(); evt=os.getenv("RUN_EVENT","").strip(); evt="cron" if evt=="schedule" else (evt or "event"); msg=f"{evt}, {ts}"
    run_color=COL["ok"] if status=="success" else COL["err"]; runb=shield("Run",msg,run_color)
    base=f"https://github.com/{owner}/{repo}/actions/runs/{run_id}" if (owner and repo and run_id) else ""
    href_movies=(f"{base}/job/{job_id}#step:{step_idx}:{ln_movies}" if (base and job_id and step_idx and ln_movies) else base)
    href_token=(f"{base}/job/{job_id}#step:{step_idx}:{ln_token}" if (base and job_id and step_idx and ln_token) else base)
    href_run=(base or "")
    dash=" ".join([enc_badge(nm,href_movies),enc_badge(tk,href_token),enc_badge(runb,href_run)])
    md=repl_block(md,"DASH:TRAKT",dash)
    line_movies="🍿 "+", ".join(titles) if titles else ""
    latest=("#### ✨ _New movies!_\n"+line_movies) if line_movies else ""
    md=repl_block(md,"TRAKT:OUTPUT",latest)
    sent=f"<!-- TRAKT_RUN:{run_id} -->" if run_id else ""
    prev=read_block(md,"TRAKT:HISTORY")
    if run_id: prev=re.sub(r'(?ms)^.*?<!-- TRAKT_RUN:'+re.escape(run_id)+r' -->.*?(?:\n(?!\s*!\[).*)*','',prev).strip()
    chunk=" ".join([enc_badge(nm,href_movies),enc_badge(tk,href_token),enc_badge(runb,href_run),sent]).strip()
    if line_movies: chunk=chunk+("<br>\n"+line_movies)
    parts=[x for x in (prev or "").split("\n\n") if x.strip()]
    new_hist=(chunk+("\n\n"+("\n\n".join(parts[:29])) if parts else "")).strip()
    md=repl_block(md,"TRAKT:HISTORY",new_hist); write(RD,md)

def load_site_channels():
    base=os.path.dirname(os.path.abspath(__file__)); pretty={}; m_sites={}; d_sites={}
    for fn,store in (("m_channels.xml",m_sites),("d_channels.xml",d_sites)):
        p=os.path.join(base,fn)
        if not os.path.exists(p): continue
        try: root=ET.parse(p).getroot()
        except: continue
        for ch in root.findall("channel"):
            site=(ch.get("site") or "").strip().lower()
            sid=(ch.get("site_id") or "").strip()
            if not site or not sid: continue
            disp=None
            for dn in ch.findall("display-name"):
                t=(dn.text or "").strip()
                if t: disp=t; break
            if not disp:
                t=(ch.text or "").strip()
                if t: disp=t
            if not disp: disp=sid
            if (site,sid) not in pretty: pretty[(site,sid)]=disp
            store.setdefault(site,set()).add(sid)
    sites={}
    for site in sorted(set(m_sites.keys())|set(d_sites.keys())):
        m_ids=m_sites.get(site,set()); d_ids=d_sites.get(site,set()); all_ids=sorted(m_ids|d_ids)
        rows=[]
        for sid in all_ids:
            disp=pretty.get((site,sid),sid)
            in_m=sid in m_ids; in_d=sid in d_ids
            tag="B" if (in_m and in_d) else ("M" if in_m else "D")
            rows.append((disp,tag))
        sites[site]=rows
    return sites,pretty

def parse_tv_table_and_badges(log_path):
    raw=read(log_path,""); M=D="0"; rows=[]; notes=[]; fails=[]; sc={}
    site_ch,pretty=load_site_channels()
    if not raw:
        ts=ts_now_it(); evt=os.getenv("RUN_EVENT","").strip(); evt="cron" if evt=="schedule" else (evt or "event"); msg=f"{evt}, {ts}"
        hb=f"{enc_badge(shield('M','0',COL['warn']), '')} {enc_badge(shield('D','0',COL['warn']), '')} {enc_badge(shield('Run',msg,COL['run']), '')}"
        return {"M":"0","D":"0","table":"<table></table>","notes":"","raw":raw,"times":{},"hist_badges":hb}
    m=re.search(r"m_epg\.xml\s*->\s*(\d+)\s+channels",raw); M=m.group(1) if m else "0"
    d=re.search(r"d_epg\.xml\s*->\s*(\d+)\s+channels",raw); D=d.group(1) if d else "0"
    for g,site,n in re.findall(r">\s*(m|d)\s+([a-z0-9\.\-]+)\s*:\s*(\d+)\s+channels",raw):
        rows.append((g,site,int(n)))
    for g,site,n in rows:
        s=sc.setdefault(site,{"M":0,"D":0,"warn":set(),"fail":False})
        if g=="m": s["M"]+=n
        else: s["D"]+=n
    times={}
    for site,val in re.findall(r"TIME\s+([a-z0-9\.\-]+)\s+(\d+)s",raw,re.I):
        try: times[site]=int(val)
        except: continue
    for site,sid,progs in re.findall(r"\]\s+([a-z0-9\.\-]+)\s*\([^)]+\)\s*-\s*([a-z0-9\-\._]+)\s*-\s*[A-Z][a-z]{2}\s+\d{1,2},\s*\d{4}\s*\((\d+)\s+programs\)",raw,re.I):
        sk=site.strip().lower(); key=(sk,sid.strip())
        disp=pretty.get(key,sid.strip())
        if sk in sc and int(progs)==0: sc[sk]["warn"].add(disp)
    for site in list(sc.keys()):
        if re.search(rf"FAIL\s+\S+\s+{re.escape(site)}",raw): sc[site]["fail"]=True
    rows_html=[]
    for site in sorted(sc.keys()):
        s=sc[site]; st="❌" if s["fail"] else ("⚠️" if s["warn"] else "✅")
        entries=site_ch.get(site.lower(),[])
        if entries:
            lines=[]
            for disp,tag in entries:
                dot="🟡" if tag=="B" else ("🔴" if tag=="M" else "🔵")
                lines.append(f"{dot} {disp}")
            cell=f"<details><summary>{site}</summary>\n"+ "<br>".join(lines) +"\n</details>"
        else:
            cell=site
        tval=times.get(site,"")
        rows_html.append(f"<tr><td>{cell}</td><td align=\"center\">{s['M']}</td><td align=\"center\">{s['D']}</td><td align=\"center\">{(str(tval)+'s') if tval!='' else ''}</td><td align=\"center\">{st}</td></tr>")
        notes.extend(sorted(s["warn"]))
        if s["fail"]: fails.append(site)
    table="<table><thead><tr><th>Site</th><th>M</th><th>D</th><th>Time</th><th>Status</th></tr></thead><tbody>"+"\n".join(rows_html)+"</tbody></table>"
    extra=[]; uniq=[]
    [uniq.append(x) for x in notes if x not in uniq]
    if uniq: extra.append(f"⚠️ Notes<br>{len(uniq)} channels without EPG: {', '.join(uniq)}")
    if fails: extra.append(f"❌ Failures<br>{len(set(fails))} site(s): {', '.join(sorted(set(fails)))}")
    ts=ts_now_it(); evt=os.getenv("RUN_EVENT","").strip(); evt="cron" if evt=="schedule" else (evt or "event"); msg=f"{evt}, {ts}"
    hb=f"{shield('M',M,COL['warn'])} {shield('D',D,COL['warn'])} {shield('Run',msg,COL['run'])}"
    return {"M":M,"D":D,"table":table,"notes":"\n\n".join(extra),"raw":raw,"times":times,"hist_badges":hb}

def _best_epg_line(raw,label):
    pat=rf'\b{label}_epg\.xml\s*->\s*\d+\s+channels\b'
    i=last_line_re_excluding(raw,pat,exclude_subs=('echo','$(','"'))
    if i: return i
    return last_line_re_excluding(raw,pat,exclude_subs=())

def _build_epg_seconds(owner,repo,run_id):
    jobs=list_jobs(owner,repo,run_id)
    if not jobs: return None
    job=next((j for j in jobs if "build epg" in (j.get("name") or "").lower()),None) or jobs[0]
    steps=job.get("steps") or []; step=None
    for s in steps:
        if (s.get("name") or "").strip()=="Build EPG":
            step=s; break
    if not step: return None
    st=step.get("started_at"); et=step.get("completed_at")
    if not (st and et): return None
    def _p(x):
        try:
            if x.endswith("Z"): x=x[:-1]+"+00:00"
            return datetime.fromisoformat(x)
        except: return None
    ds=_p(st); de=_p(et)
    if not ds or not de: return None
    sec=int((de-ds).total_seconds())
    return sec if sec>=0 else None

def update_tv(log_path,status="success"):
    md=read(RD); tv=parse_tv_table_and_badges(log_path)
    owner_repo=(os.getenv("GITHUB_REPOSITORY") or "").split("/",1); owner=owner_repo[0] if owner_repo else ""; repo=owner_repo[1] if len(owner_repo)==2 else ""; run_id=os.getenv("RUN_ID","").strip()
    job_id=os.getenv("TV_JOB_ID","").strip(); step_idx=os.getenv("TV_STEP_IDX","5").strip()
    if not job_id or not step_idx:
        j,s=find_tv_job_and_step(owner,repo,run_id)
        if j: job_id=str(j)
        if s: step_idx=str(s)
    ln_m=ln_d=ln_build=None; rawlog=None
    if owner and repo and run_id and job_id:
        rawlog=fetch_job_log(owner,repo,job_id)
        if rawlog:
            im=_best_epg_line(rawlog,'m'); idl=_best_epg_line(rawlog,'d')
            gs_m=nearest_group_start_before(rawlog,im) if im else None
            gs_d=nearest_group_start_before(rawlog,idl) if idl else None
            ln_m=(im-gs_m+1) if (im and gs_m) else None
            ln_d=(idl-gs_d+1) if (idl and gs_d) else None
            if ln_m is not None and ln_m<1: ln_m=1
            if ln_d is not None and ln_d<1: ln_d=1
            gb=None
            for i,ln in enumerate(clean_lines(rawlog),1):
                if "##[group]Grab" in ln:
                    gb=i; break
            if gb:
                gs_step=nearest_group_start_before(rawlog,gb)
                ln_build=(gb-gs_step+1) if gs_step else None
                if ln_build is not None and ln_build<1: ln_build=1
    base=f"https://github.com/{owner}/{repo}/actions/runs/{run_id}" if (owner and repo and run_id) else ""
    href_m=(f"{base}/job/{job_id}#step:{step_idx}:{ln_m}" if (base and job_id and step_idx and ln_m) else base)
    href_d=(f"{base}/job/{job_id}#step:{step_idx}:{ln_d}" if (base and job_id and step_idx and ln_d) else base)
    href_run=(base or "")
    href_build=(f"{base}/job/{job_id}#step:{step_idx}:{ln_build}" if (base and job_id and step_idx and ln_build) else href_run)
    s_m=shield('M',tv['M'],COL['warn']); s_d=shield('D',tv['D'],COL['warn'])
    secs=_build_epg_seconds(owner,repo,run_id) if (owner and repo and run_id) else None
    be_val=f"{secs}s" if isinstance(secs,int) and secs>=0 else "-"
    s_build=shield('Build EPG',be_val,COL["run"])
    ts=ts_now_it(); evt=os.getenv("RUN_EVENT","").strip(); evt="cron" if evt=="schedule" else (evt or "event"); msg=f"{evt}, {ts}"
    run_color=COL["ok"] if status=="success" else COL["err"]; s_run=shield('Run',msg,run_color)
    dash=" ".join([enc_badge(s_m,href_m),enc_badge(s_d,href_d),enc_badge(s_build,href_build),enc_badge(s_run,href_run)])
    md=repl_block(md,"DASH:TV",dash)
    md=repl_block(md,"TV:OUTPUT",tv["table"]+("\n\n"+tv["notes"] if tv["notes"] else ""))
    hist_badges=f"{enc_badge(s_m, href_m)} {enc_badge(s_d, href_d)} {enc_badge(s_build, href_build)} {enc_badge(s_run, href_run)}"
    prev=read_block(md,"TV:HISTORY"); chunk=hist_badges + (("<br>\n"+tv["notes"]) if tv["notes"] else ""); parts=[x for x in (prev or "").split("\n\n") if x.strip()]
    new_hist=(chunk+("\n\n"+("\n\n".join(parts[:29])) if parts else "")).strip()
    md=repl_block(md,"TV:HISTORY",new_hist); write(RD,md)

def main():
    if len(sys.argv)<2: print("Usage:\n  dashboard.py trakt --log trakt_run.log [--status success|failure]\n  dashboard.py tv --log tv_epg.log [--status success|failure]"); sys.exit(1)
    mode=sys.argv[1].lower(); arg=lambda f,d=None: sys.argv[sys.argv.index(f)+1] if f in sys.argv else d
    if mode=="trakt":
        lp=arg("--log","trakt_run.log"); st=arg("--status","success");
        try: update_trakt(lp,st)
        except Exception as e: _dbg("fatal trakt",e)
    elif mode=="tv":
        lp=arg("--log","tv_epg.log"); st=arg("--status","success");
        try: update_tv(lp,st)
        except Exception as e: _dbg("fatal tv",e)
    else: sys.exit(2)
    msg=os.getenv("DASH_COMMIT_MSG","").strip()
    if msg:
        os.system('git config user.name "github-actions"'); os.system('git config user.email "github-actions@github.com"')
        os.system('git add README.md'); os.system(f'git commit -m "{msg}" || true'); os.system('git push || true')

if __name__=="__main__": main()
