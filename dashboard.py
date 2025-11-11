import os,re,datetime,html

RD="README.md"
NOW=datetime.datetime.utcnow().replace(microsecond=0)
RUN_URL=os.getenv("RUN_URL","")
RUN_AT=os.getenv("RUN_AT",NOW.isoformat(sep=" "))

def read(p): 
    with open(p,"r",encoding="utf-8") as f: return f.read()
def write(p,s): 
    with open(p,"w",encoding="utf-8") as f: f.write(s)
def sub_block(txt,tag,new):
    a=f"<!-- {tag} -->"; b=f"<!-- /{tag} -->"
    return re.sub(f"{re.escape(a)}[\\s\\S]*?{re.escape(b)}",f"{a}\n{new}\n{b}",txt,flags=re.M)
def badge(label,val,color):
    return f"[![X](https://img.shields.io/badge/{html.escape(label)}-{html.escape(val)}-{color}?cacheSeconds=300)]({RUN_URL})"
def badgen_run(ts,color="f1c40f"):
    return f"[![X](https://badgen.net/badge/Run/{html.escape(ts)}/{color})]({RUN_URL})"

def parse_trakt(log):
    if not log or not os.path.exists(log): 
        return {"new":"0","token":"unknown","out":"","hist_badges":""}
    raw=read(log)
    token="unknown"
    if re.search(r"🧩 Need new refresh token!",raw): token="failed"
    elif re.search(r"Trakt token refresh completed",raw): token="refreshed"
    elif re.search(r"🔐 Trakt token valid",raw): token="valid"
    m=re.search(r"New Movie\(s\):\s*(\d+)",raw,re.I)
    new=m.group(1) if m else "0"
    titles=[t.strip() for t in re.findall(r"🍿\s*(.+)",raw)]
    out=("🍿 "+", ".join(titles)) if titles else ""
    tok_color= "2ecc71" if token=="refreshed" else "3498db" if token=="valid" else "e67e22" if token=="unknown" else "e74c3c"
    hb=f"{badge('New Movie',new,'27ae60')} {badge('Token',token,tok_color)} {badgen_run(RUN_AT)}"
    return {"new":new,"token":token,"out":out,"hist_badges":hb}

def parse_tv(log):
    if not log or not os.path.exists(log):
        hb=f"{badge('M','0','95a5a6')} {badge('D','0','95a5a6')} {badgen_run(RUN_AT)}"
        head="| Site | M | D | Status |\n|---|---:|---:|---|\n"
        return {"M":"0","D":"0","table":head,"notes":"","hist_badges":hb}
    raw=read(log)
    m=re.search(r"m_epg\.xml\s*->\s*(\d+)\s+channels",raw); M=m.group(1) if m else "0"
    d=re.search(r"d_epg\.xml\s*->\s*(\d+)\s+channels",raw); D=d.group(1) if d else "0"
    site_counts={}
    for g,site,n in re.findall(r">\s*(main|d)\s+([a-z0-9\.\-]+)\s*:\s*(\d+)\s+channels",raw):
        s=site_counts.setdefault(site,{"M":0,"D":0,"warn":set(),"fail":False})
        (s["M"] if g=="main" else s["D"]).__iadd__(int(n))
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
    head="| Site | M | D | Status |\n|---|---:|---:|---|\n"
    table=head+("\n".join(rows) if rows else "")
    extra=[]
    if notes:
        uniq=[]; [uniq.append(x) for x in notes if x not in uniq]
        extra.append(f"⚠️ Notes\n{len(uniq)} channels without EPG: {', '.join(uniq)}")
    if fails:
        extra.append(f"❌ Failures\n{len(set(fails))} site(s) error: {', '.join(sorted(set(fails)))}")
    hb=f"{badge('M',M,'27ae60')} {badge('D',D,'27ae60')} {badgen_run(RUN_AT)}"
    return {"M":M,"D":D,"table":table,"notes":"\n\n".join(extra),"hist_badges":hb}

def append_history(txt,tag,entry):
    prev=re.search(f"<!-- {re.escape(tag)} -->([\\s\\S]*?)<!-- /{re.escape(tag)} -->",txt)
    return sub_block(txt,tag,(f"{entry} <!-- {tag.split(':')[0]}_RUN:{os.getenv('GITHUB_RUN_ID','')} -->\n"+(prev.group(1).strip() if prev else "")))

def update_overall(txt,trakt_badges,tv_badges):
    combined=f"{trakt_badges} {tv_badges}".strip()
    return append_history(sub_block(txt,"OVERALL:BADGES",combined),"OVERALL:HISTORY",combined)

def run():
    if os.getenv("NO_DASH","0")=="1": print("NO_DASH=1, skipping commit"); return
    trakt_log=os.getenv("TRAKT_LOG","trakt_run.log")
    tv_log=os.getenv("TV_LOG","tv_epg.log")
    rd=read(RD)
    t=parse_trakt(trakt_log)
    tv=parse_tv(tv_log)
    rd=sub_block(rd,"DASH:TRAKT",f"{badge('New Movie',t['new'],'27ae60')} {badge('Token',t['token'],('2ecc71' if t['token']=='refreshed' else '3498db' if t['token']=='valid' else 'e67e22' if t['token']=='unknown' else 'e74c3c'))} {badgen_run(RUN_AT)}")
    rd=sub_block(rd,"TRAKT:OUTPUT",t["out"])
    rd=append_history(rd,"TRAKT:HISTORY",t["hist_badges"]+(" <br>\n"+t["out"] if t["out"] else ""))
    rd=sub_block(rd,"DASH:TV",f"{badge('M',tv['M'],'27ae60')} {badge('D',tv['D'],'27ae60')} {badgen_run(RUN_AT)}")
    rd=sub_block(rd,"TV:OUTPUT",tv["table"]+("\n\n"+tv["notes"] if tv["notes"] else ""))
    rd=append_history(rd,"TV:HISTORY",tv["hist_badges"])
    write(RD,rd)
    os.system('git config user.name "github-actions"')
    os.system('git config user.email "github-actions@github.com"')
    os.system('git add README.md')
    os.system(f'git commit -m "docs(dashboard): update {NOW.isoformat()} UTC" || true')
    os.system('git push || true')

if __name__=="__main__": run()
