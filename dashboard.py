import os,re,datetime,urllib.parse,sys,locale
RD="README.md"; NOW=datetime.datetime.utcnow().replace(microsecond=0)
RUN_URL=os.getenv("RUN_URL",""); RUN_AT_RAW=os.getenv("RUN_AT",NOW.isoformat(sep=" "))
RUN_EVENT=os.getenv("RUN_EVENT",""); RUN_ID=os.getenv("RUN_ID",""); TRAKT_STEP=int(os.getenv("TRAKT_STEP","5")); TV_STEP=int(os.getenv("TV_STEP","6"))
IT_MONTH=["gen","feb","mar","apr","mag","giu","lug","ago","set","ott","nov","dic"]
def _enc(s): return urllib.parse.quote(str(s),safe="")
def _iso_to_dt(s): 
    try: return datetime.datetime.fromisoformat(s.replace("Z",""))
    except: return NOW
def _fmt_day(dt): return f"{dt.day:02d} {IT_MONTH[dt.month-1]} {dt.year}"
RUN_DT=_iso_to_dt(RUN_AT_RAW); RUN_DAY=_fmt_day(RUN_DT)
def read(p): 
    with open(p,"r",encoding="utf-8") as f: return f.read()
def write(p,s): 
    with open(p,"w",encoding="utf-8") as f: f.write(s)
def sub_block(txt,tag,new):
    a=f"<!-- {tag} -->"; b=f"<!-- /{tag} -->"
    return re.sub(f"{re.escape(a)}[\\s\\S]*?{re.escape(b)}",f"{a}\n{new}\n{b}",txt,flags=re.M)
def badge_static(label,message,color,href): 
    return f"[![{label}](https://img.shields.io/static/v1?label={_enc(label)}&message={_enc(message)}&color={_enc(color)}&cacheSeconds=300)]({href})"
def badge(label,val,color,href): 
    return f"[![X](https://img.shields.io/badge/{_enc(label)}-{_enc(val)}-{_enc(color)}?cacheSeconds=300)]({href})"
def badgen_run(date_str,href,color="f1c40f"):
    return f"[![X](https://badgen.net/badge/Run/{_enc(date_str)}/{_enc(color)})]({href})"
def _find_line(raw,pattern,flags=0):
    m=re.search(pattern,raw,flags); 
    if not m: return None
    return raw[:m.start()].count("\n")+1
def parse_trakt(log):
    if not log or not os.path.exists(log): 
        return {"new":"0","token":"unknown","out":"","hist_badges":"","status":"failure","nm_url":RUN_URL,"tok_url":RUN_URL}
    raw=read(log); token="unknown"; status="success"
    if re.search(r"🧩 Need new refresh token!",raw): token="failed"; status="failure"
    elif re.search(r"Trakt token refresh completed",raw): token="refreshed"
    elif re.search(r"🔐 Trakt token valid",raw): token="valid"
    else: status="failure"
    m=re.search(r"New Movie\(s\):\s*(\d+)",raw,re.I); new=m.group(1) if m else "0"
    titles=[t.strip() for t in re.findall(r"🍿\s*(.+)",raw)]
    out=("🍿 "+", ".join(titles)) if titles else ""
    tok_color="2ecc71" if token=="refreshed" else "3498db" if token=="valid" else "e67e22" if token=="unknown" else "e74c3c"
    ln_nm=_find_line(raw,r"New Movie\(s\):\s*\d+",re.I); ln_tok=_find_line(raw,r"(Need new refresh token!|Trakt token refresh completed|🔐 Trakt token valid)")
    nm_url=f"{RUN_URL}#step:{TRAKT_STEP}:{ln_nm}" if ln_nm else RUN_URL
    tok_url=f"{RUN_URL}#step:{TRAKT_STEP}:{ln_tok}" if ln_tok else RUN_URL
    hb=f"{badge('New Movie',new,'27ae60',nm_url)} {badge('Token',token,tok_color,tok_url)} {badgen_run(_fmt_day(RUN_DT),RUN_URL)}"
    return {"new":new,"token":token,"out":out,"hist_badges":hb,"status":status,"nm_url":nm_url,"tok_url":tok_url}
def parse_tv(log):
    if not log or not os.path.exists(log):
        hb=f"{badge('M','0','95a5a6',RUN_URL)} {badge('D','0','95a5a6',RUN_URL)} {badgen_run(_fmt_day(RUN_DT),RUN_URL)}"
        head="| Site | M | D | Status |\n|---|---:|---:|---|\n"
        return {"M":"0","D":"0","table":head,"notes":"","hist_badges":hb,"status":"failure"}
    raw=read(log); status="success"
    m=re.search(r"m_epg\.xml\s*->\s*(\d+)\s+channels",raw); M=m.group(1) if m else "0"
    d=re.search(r"d_epg\.xml\s*->\s*(\d+)\s+channels",raw); D=d.group(1) if d else "0"
    site_counts={}
    for g,site,n in re.findall(r">\s*(main|d)\s+([a-z0-9\.\-]+)\s*:\s*(\d+)\s+channels",raw): s=site_counts.setdefault(site,{"M":0,"D":0,"warn":set(),"fail":False}); (s["M"] if g=="main" else s["D"]).__iadd__(int(n))
    for site in list(site_counts.keys()):
        if re.search(rf"FAIL\s+(main|d)\s+{re.escape(site)}",raw): site_counts[site]["fail"]=True; status="failure"
    for site,chan,progs in re.findall(r"([a-z0-9\.\-]+).*?-\s*([a-z0-9\-\s]+)\s*-\s*[A-Z][a-z]{{2}}\s+\d{{1,2}},\s*\d{{4}}\s*\((\d+)\s+programs\)",raw,re.I):
        if site in site_counts and int(progs)==0: site_counts[site]["warn"].add(re.sub(r"\s+"," ",chan.strip()))
    rows=[]; notes=[]; fails=[]
    for site in sorted(site_counts.keys()):
        s=site_counts[site]; st="✅"; 
        if s["fail"]: st="❌"
        elif s["warn"]: st="⚠️"
        rows.append(f"| {site} | {s['M']} | {s['D']} | {st} |")
        if s["warn"]: notes.extend(sorted(s["warn"]))
        if s["fail"]: fails.append(site)
    head="| Site | M | D | Status |\n|---|---:|---:|---|\n"; table=head+("\n".join(rows) if rows else "")
    extra=[]
    if notes:
        uniq=[]; [uniq.append(x) for x in notes if x not in uniq]; extra.append(f"⚠️ Notes\n{len(uniq)} channels without EPG: {', '.join(uniq)}")
    if fails: extra.append(f"❌ Failures\n{len(set(fails))} site(s) error: {', '.join(sorted(set(fails)))}")
    hb=f"{badge('M',M,'27ae60',RUN_URL)} {badge('D',D,'27ae60',RUN_URL)} {badgen_run(_fmt_day(RUN_DT),RUN_URL)}"
    return {"M":M,"D":D,"table":table,"notes":"\n\n".join(extra),"hist_badges":hb,"status":status}
def append_history(txt,tag,entry):
    prev=re.search(f"<!-- {re.escape(tag)} -->([\\s\\S]*?)<!-- /{re.escape(tag)} -->",txt)
    new_entry=f"{entry} <!-- {tag.split(':')[0]}_RUN:{RUN_ID} -->\n\n"
    return sub_block(txt,tag,new_entry+((prev.group(1).strip()+"\n") if prev and prev.group(1).strip() else ""))
def update_overall(txt,trak_stat,live_stat):
    ev="workflow_dispatch" if RUN_EVENT=="workflow_dispatch" else "cron"
    t_color="2ecc71" if trak_stat=="success" else "e74c3c"
    v_color="2ecc71" if live_stat=="success" else "e74c3c"
    t_badge=badge_static("Trakt",f"{ev}, {RUN_DAY}",t_color,RUN_URL)
    v_badge=badge_static("Live TV",f"{ev}, {RUN_DAY}",v_color,RUN_URL)
    combined=f"{t_badge} {v_badge}".strip()
    return append_history(sub_block(txt,"OVERALL:BADGES",combined),"OVERALL:HISTORY",combined)
def run(mode,trakt_log,tv_log):
    rd=read(RD)
    if mode=="trakt":
        t=parse_trakt(trakt_log)
        rd=sub_block(rd,"DASH:TRAKT",f"{badge('New Movie',t['new'],'27ae60',t['nm_url'])} {badge('Token',t['token'],('2ecc71' if t['token']=='refreshed' else '3498db' if t['token']=='valid' else 'e67e22' if t['token']=='unknown' else 'e74c3c'),t['tok_url'])} {badgen_run(RUN_DAY,RUN_URL)}")
        rd=sub_block(rd,"TRAKT:OUTPUT",t["out"]); rd=append_history(rd,"TRAKT:HISTORY",t["hist_badges"]+(" <br>\n"+t["out"] if t["out"] else ""))
        tv=parse_tv(tv_log); rd=update_overall(rd,t["status"],tv["status"])
    elif mode=="tv":
        tv=parse_tv(tv_log)
        rd=sub_block(rd,"DASH:TV",f"{badge('M',tv['M'],'27ae60',RUN_URL)} {badge('D',tv['D'],'27ae60',RUN_URL)} {badgen_run(RUN_DAY,RUN_URL)}")
        rd=sub_block(rd,"TV:OUTPUT",tv["table"]+("\n\n"+tv["notes"] if tv["notes"] else "")); rd=append_history(rd,"TV:HISTORY",tv["hist_badges"])
        t=parse_trakt(trakt_log); rd=update_overall(rd,t["status"],tv["status"])
    else:
        t=parse_trakt(trakt_log); tv=parse_tv(tv_log)
        rd=sub_block(rd,"DASH:TRAKT",f"{badge('New Movie',t['new'],'27ae60',t['nm_url'])} {badge('Token',t['token'],('2ecc71' if t['token']=='refreshed' else '3498db' if t['token']=='valid' else 'e67e22' if t['token']=='unknown' else 'e74c3c'),t['tok_url'])} {badgen_run(RUN_DAY,RUN_URL)}")
        rd=sub_block(rd,"TRAKT:OUTPUT",t["out"]); rd=append_history(rd,"TRAKT:HISTORY",t["hist_badges"]+(" <br>\n"+t["out"] if t["out"] else ""))
        rd=sub_block(rd,"DASH:TV",f"{badge('M',tv['M'],'27ae60',RUN_URL)} {badge('D',tv['D'],'27ae60',RUN_URL)} {badgen_run(RUN_DAY,RUN_URL)}")
        rd=sub_block(rd,"TV:OUTPUT",tv["table"]+("\n\n"+tv["notes"] if tv["notes"] else "")); rd=append_history(rd,"TV:HISTORY",tv["hist_badges"])
        rd=update_overall(rd,t["status"],tv["status"])
    write(RD,rd)
    msg=os.getenv("DASH_COMMIT_MSG","")
    if msg:
        os.system('git config user.name "github-actions"'); os.system('git config user.email "github-actions@github.com"')
        os.system('git add README.md'); os.system(f'git commit -m "{msg}" || true'); os.system('git push || true')
if __name__=="__main__":
    mode="both"; trakt_log=os.getenv("TRAKT_LOG","trakt_run.log"); tv_log=os.getenv("TV_LOG","tv_epg.log"); args=sys.argv[1:]
    if args: mode=args[0].lower()
    if "--log" in args:
        i=args.index("--log")
        if i+1<len(args):
            if mode=="trakt": trakt_log=args[i+1]
            elif mode=="tv": tv_log=args[i+1]
    run(mode,trakt_log,tv_log)
