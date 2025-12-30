import sys, io, requests, re, time, os, json, tempfile
from datetime import datetime
from typing import Any, List
from lxml import html
from urllib.parse import unquote
from collections import namedtuple, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

SITE_WORKERS=8
WD_WORKERS=16
HTTP_TIMEOUT=(4,10)

sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8',line_buffering=True)
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
WFilm=namedtuple('WFilm','title date_iso url page is_full link_state',defaults=(True,''))
TODAY=datetime.now().date();
S=requests.Session(); S.headers["User-Agent"]=UA
ad=HTTPAdapter(max_retries=Retry(total=2,backoff_factor=0.6,status_forcelist=(429,500,502,503,504),allowed_methods=frozenset({"GET","POST"})),pool_connections=64,pool_maxsize=64)
S.mount("https://",ad); S.mount("http://",ad)
MONTHS=("january","february","march","april","may","june","july","august","september","october","november","december")
DATE_FULL_RE=re.compile(r"\b("+"|".join(m.capitalize() for m in MONTHS)+r")\s+(\d{1,2}),\s*(\d{4})\b",re.IGNORECASE)
YEAR_RE=re.compile(r"\b((?:19|20)\d{2})\b")

SITES=[
    ("https://en.wikipedia.org/wiki/List_of_films_based_on_Marvel_Comics_publications","✪ Marvel Comics: Live-Action Films","", "marvel-comics-live-action-films",0),
    ("https://en.wikipedia.org/wiki/List_of_films_based_on_DC_Comics_publications","🌌 DC Comics: Live-Action Films","", "dc-comics-live-action-films",0),
    ("https://en.wikipedia.org/wiki/List_of_adaptations_of_works_by_Stephen_King","👀 Stephen King","", "stephen-king",[0,1,4]),    
    ("https://en.wikipedia.org/wiki/List_of_Walt_Disney_Animation_Studios_films","🪄 Ink & Magic – A Disney Animation Journey","WDAS","ink-magic-a-disney-animation-journey",0),
    ("https://en.wikipedia.org/wiki/List_of_Disney_Television_Animation_productions","🪄 Ink & Magic – A Disney Animation Journey","DTVA","ink-magic-a-disney-animation-journey",[4,5]),
    ("https://en.wikipedia.org/wiki/Disneytoon_Studios","🪄 Ink & Magic – A Disney Animation Journey","DTS","ink-magic-a-disney-animation-journey",0),
    ("https://en.wikipedia.org/wiki/List_of_Disney%2B_original_films","🪄 Ink & Magic – A Disney Animation Journey","D+","ink-magic-a-disney-animation-journey",{"tables":0,"href_contains":"animated"}),
    ("https://en.wikipedia.org/wiki/List_of_Pixar_films","🪄 Ink & Magic – A Disney Animation Journey","Pixar","ink-magic-a-disney-animation-journey",0),
    ("https://en.wikipedia.org/wiki/List_of_Warner_Bros._Pictures_Animation_productions","🐰 Warner Bros. Toons — Films & TV","WBPA","warner-bros-toons-films-tv",0),    
    ("https://en.wikipedia.org/wiki/List_of_Warner_Bros._Animation_productions","🐰 Warner Bros. Toons — Films & TV","WBA","warner-bros-toons-films-tv",[0,1,4]),
]

QIDS = [
    ("Batgirl", "Q109860581"),
    ("A Goofy Movie", "Q869993"),
    ("An Extremely Goofy Movie", "Q1537670"),
    ("Aquaman and the Lost Kingdom", "Q91226161"),
    ("Around the World with Timon & Pumbaa", "Q18192535"),
    ("Avengers: Age of Ultron", "Q14171368"),
    ("Batman Begins", "Q166262"),
    ("Batman v Superman: Dawn of Justice", "Q14772351"),
    ("Blade II", "Q159638"),
    ("Buzz Lightyear of Star Command: The Adventure Begins", "Q1703163"),
    ("Carrie", "Q162672"),
    ("Cats Don't Dance", "Q930134"),
    ("Cell", "Q17050502"),
    ("Children of the Corn 666: Isaac's Return", "Q1502325"),
    ("Children of the Corn V: Fields of Terror", "Q1548882"),
    ("Cinderella II: Dreams Come True", "Q852391"),
    ("Diary of a Wimpy Kid: The Last Straw", "Q136530239"),
    ("Dolan's Cadillac", "Q907787"),
    ("Dreamcatcher", "Q1256231"),
    ("DuckTales the Movie: Treasure of the Lost Lamp", "Q1263501"),
    ("Fantasia", "Q943192"),
    ("Finding Dory", "Q9321426"),
    ("Fun and Fancy Free", "Q853718"),
    ("Graveyard Shift", "Q944115"),
    ("Green Lantern", "Q903885"),
    ("Hercules: Zero to Hero", "Q1609593"),
    ("Home on the Range", "Q936194"),
    ("Jungle Cubs: Born to Be Wild", "Q136513480"),
    ("Kronk's New Groove", "Q937486"),
    ("Luca", "Q97925311"),
    ("Melody Time", "Q869741"),
    ("Mercy", "Q16664100"),
    ("Mickey's House of Villains", "Q1630767"),
    ("Mickey's Once Upon a Christmas", "Q1655222"),
    ("Mighty Ducks the Movie: The First Face-Off", "Q3312846"),
    ("Moana 2", "Q124457266"),
    ("Needful Things", "Q1660749"),
    ("One Hundred and One Dalmatians", "Q165512"),
    ("Osmosis Jones", "Q966690"),
    ("Pet Sematary", "Q908213"),
    ("Piglet's Big Movie", "Q1406374"),
    ("Planes", "Q1657080"),
    ("Planes: Fire & Rescue", "Q15631322"),
    ("Pooh's Grand Adventure: The Search for Christopher Robin", "Q919563"),
    ("Pooh's Heffalump Movie", "Q1361113"),
    ("Ratatouille", "Q170035"),
    ("Recess Christmas: Miracle on Third Street", "Q4357623"),
    ("Recess: All Growed Down", "Q7302373"),
    ("Recess: School's Out", "Q969270"),
    ("Recess: Taking the Fifth Grade", "Q5412173"),
    ("Saludos Amigos", "Q842306"),
    ("Secret of the Wings", "Q1702819"),
    ("Shazam! Fury of the Gods", "Q84712809"),
    ("Stitch! The Movie", "Q1468857"),
    ("The Adventures of Ichabod and Mr. Toad", "Q863963"),
    ("The Dark Half", "Q940066"),
    ("The Dark Knight", "Q163872"),
    ("The Iron Giant", "Q867283"),
    ("The Mangler", "Q1660446"),
    ("The Mangler 2", "Q1513631"),
    ("The Marvels", "Q89474225"),
    ("The Pirate Fairy", "Q15396069"),
    ("The Punisher", "Q909802"),
    ("Thinner", "Q1637939"),
    ("Tinker Bell and the Great Fairy Rescue", "Q1507306"),
    ("Tinker Bell and the Lost Treasure", "Q873598"),
    ("Watchmen", "Q162182"),
    ("Winnie the Pooh", "Q922193"),
    ("Winnie the Pooh: Seasons of Giving", "Q1440523"),
    ("X-Men: Apocalypse", "Q17042878"),
    ("Zootopia", "Q15270647"),
]

def trakt_auth_refresh():
    TOKENS_PATH = "updates/trakt_tokens.json"; trakt_data = json.load(open(TOKENS_PATH, encoding="utf-8"))
    h={"Content-Type":"application/json","trakt-api-version":"2","trakt-api-key":trakt_data["client_id"],"Authorization":f"Bearer {trakt_data['access_token']}"}; now=time.time(); exp=trakt_data["created_at"]+trakt_data["expires_in"]
    if now<=exp-300: rem=int(exp-now); print(f"🔐 Trakt token valid (~{rem//3600}h {(rem%3600)//60}m)"); return trakt_data,h
    print("⏳ Trakt token expired. Refreshing..."); r=requests.post(trakt_data["baseurl"]+"/oauth/token",json={"grant_type":"refresh_token","refresh_token":trakt_data["refresh_token"],"client_id":trakt_data["client_id"],"client_secret":trakt_data["client_secret"]})
    if r.status_code!=200:
        print("❌ Trakt refresh failed:", r.status_code, (r.text or "")[:300])
        sys.exit(1)
    trakt_data.update(r.json()); trakt_data["created_at"]=time.time(); h["Authorization"]=f"Bearer {trakt_data['access_token']}"; print("🔄 Trakt token refresh completed")
    open(TOKENS_PATH,"w",encoding="utf-8").write(json.dumps(trakt_data,ensure_ascii=False,indent=2))
    return trakt_data,h
    
def gh_sync_qid_issue(missing_titles):
    try:
        tok=(os.getenv("GITHUB_TOKEN") or "").strip()
        repo=(os.getenv("GITHUB_REPOSITORY") or "").strip()
        if not tok or not repo: return
        ISSUE_TITLE="Missing QIDs"
        h={"Authorization":f"Bearer {tok}","Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"}
        base="https://api.github.com"
        q=f'repo:{repo} is:issue in:title "{ISSUE_TITLE}"'
        r=requests.get(f"{base}/search/issues",params={"q":q},headers=h,timeout=HTTP_TIMEOUT)
        items=(r.json() or {}).get("items") or []
        hit=next((it for it in items if (it.get("title") or "")==ISSUE_TITLE), None)
        num=hit.get("number") if hit else None

        cur_body=""; cur_state=""
        if num:
            rr=requests.get(f"{base}/repos/{repo}/issues/{num}",headers=h,timeout=HTTP_TIMEOUT)
            j=rr.json() or {}
            cur_body=(j.get("body") or "").strip()
            cur_state=(j.get("state") or "").strip()

        if missing_titles:
            body="\n".join(["Missing QIDs:"]+[f"- {t}" for t in missing_titles]).strip()
            if num:
                payload={}
                if cur_body!=body: payload["body"]=body
                if cur_state!="open": payload["state"]="open"
                if payload: requests.patch(f"{base}/repos/{repo}/issues/{num}",json=payload,headers=h,timeout=HTTP_TIMEOUT)
            else:
                requests.post(f"{base}/repos/{repo}/issues",json={"title":ISSUE_TITLE,"body":body,"state":"open","labels":["automation","qid"]},headers=h,timeout=HTTP_TIMEOUT)
        else:
            if num and cur_state=="open":
                requests.patch(f"{base}/repos/{repo}/issues/{num}",json={"state":"closed"},headers=h,timeout=HTTP_TIMEOUT)
    except Exception as e:
        print("⚠️ GitHub issue sync failed:", type(e).__name__)

def wikipedia_scraping(url:str,selector:Any)->List[WFilm]:
    r=S.get(url,timeout=HTTP_TIMEOUT); doc=html.fromstring(r.content); tbls=doc.xpath("//table[contains(concat(' ', @class, ' '), ' wikitable ')]"); href_filter=None; table_indices=[0]
    if isinstance(selector,dict): href_filter=(selector.get("href_contains") or "").lower(); table_indices=[selector.get("tables")] if isinstance(selector.get("tables"),int) else (selector.get("tables") or [0])
    elif isinstance(selector,list): table_indices=[i for i in selector if isinstance(i,int)]
    elif isinstance(selector,int): table_indices=[selector]
    out=[]; seen=set(); URL_YEAR=(lambda m:int(m.group(1)) if m else TODAY.year)(re.search(r"List_of_American_films_of_(\d{4})",url,re.IGNORECASE)); _txt=lambda e: re.sub(r"\s+"," ",(e.text_content() if e is not None else "")).strip()
    for ti in table_indices:
        if not (0<=ti<len(tbls)): continue
        tbl=tbls[ti]; headers=tbl.xpath(".//tr[th]"); header_row=max(headers,key=lambda tr: len(tr.xpath("./th"))) if headers else None
        header_texts=[re.sub(r"\s+"," ",(th.text_content() or "")).strip().lower() for th in (header_row.xpath("./th") if header_row is not None else [])]
        has_opening=any("opening" in h for h in header_texts); has_title=any(any(x in h for x in ["title","film"]) for h in header_texts); is_calendar=has_opening and has_title
        date_col=(next((i for i,h in enumerate(header_texts) if ("opening" in h)),None) if is_calendar else next((i for i,h in enumerate(header_texts) if any(x in h for x in ["release date","year"])),None)); title_col=next((i for i,h in enumerate(header_texts) if any(x in h for x in ["title","film"])),None); genre_col=(next((i for i,h in enumerate(header_texts) if "genre" in h),None) if href_filter else None)
        if date_col is None or title_col is None: continue
        if is_calendar: day_col=date_col+1; title_col=title_col+1
        else: day_col=date_col
        num_cols=len(header_texts); rowspan_tracker=[0]*num_cols; rowspan_values=[None]*num_cols; current_month=None; current_day=None; last_date=None
        for tr in tbl.xpath('.//tr[td or th[@scope="row"]]'):
            row=[None]*num_cols
            for i in range(num_cols):
                if rowspan_tracker[i]>0: row[i]=rowspan_values[i] if rowspan_values[i] is not None else "ROWSPAN"; rowspan_tracker[i]-=1
            col_idx=0
            for cell in tr.xpath('./th|./td'):
                while col_idx<num_cols and row[col_idx] is not None: col_idx+=1
                if col_idx>=num_cols: break
                colspan=max(1,int(cell.get('colspan') or 1)); rowspan=max(1,int(cell.get('rowspan') or 1))
                for k in range(colspan):
                    if col_idx+k>=num_cols: break
                    if k==0: row[col_idx+k]=cell
                    else: row[col_idx+k]="COLSPAN"
                    if rowspan>1: rowspan_values[col_idx+k]=cell if k==0 else None; rowspan_tracker[col_idx+k]=max(rowspan_tracker[col_idx+k],rowspan-1)
                col_idx+=colspan
            if is_calendar:
                if len(row)>0 and row[0] not in (None,"ROWSPAN","COLSPAN"): mtxt=re.sub(r"[^A-Za-z]","",_txt(row[0])).lower()
                if len(row)>0 and row[0] not in (None,"ROWSPAN","COLSPAN") and mtxt in MONTHS: current_month=mtxt.title()
                if day_col is not None and day_col<len(row) and row[day_col] not in (None,"ROWSPAN","COLSPAN"): mm=re.search(r"\b(\d{1,2})\b",_txt(row[day_col]))
                if day_col is not None and day_col<len(row) and row[day_col] not in (None,"ROWSPAN","COLSPAN") and mm: current_day=int(mm.group(1))
            title=None; page=None; link_state=""
            if title_col<len(row) and row[title_col] not in (None,"ROWSPAN","COLSPAN"):
                tc=row[title_col]; a_list=tc.xpath(".//i//a[starts-with(@href,'/wiki/')][1]") or tc.xpath(".//a[starts-with(@href,'/wiki/')][1]"); a=a_list[0] if len(a_list)>0 else None
                title=(a.text_content().strip() if a is not None else _txt(tc))
                if a is not None:
                    acls=(a.get("class") or "").split()
                    if "new" in acls: page=None; link_state="redlink"
                    else: href=a.get("href",""); page=unquote(href.split("#")[0]).replace("/wiki/","").replace(" ","_"); link_state=""
            if not title:
                for c in row:
                    if c is None or isinstance(c,str): continue
                    a_list=c.xpath(".//a[starts-with(@href,'/wiki/')][1]")
                    if len(a_list)>0:
                        a=a_list[0]; title=(a.text_content() or "").strip(); acls=(a.get("class") or "").split()
                        if "new" in acls: page=None; link_state="redlink"
                        else: href=a.get("href",""); page=unquote(href.split("#")[0]).replace("/wiki/","").replace(" ","_"); link_state=""
                        break
            if title and not page and not link_state: link_state="plain-text"
            if href_filter and genre_col is not None and genre_col<len(row) and row[genre_col] not in (None,"ROWSPAN","COLSPAN"):
                if href_filter not in (_txt(row[genre_col]).lower()): continue
            date_iso=None
            if is_calendar and current_month and current_day and title:
                try: date_iso=datetime.strptime(f"{current_month} {current_day}, {URL_YEAR}","%B %d, %Y").strftime("%Y-%m-%d"); last_date=date_iso
                except: date_iso=None
            elif day_col is not None and day_col<len(row) and row[day_col] not in (None,"ROWSPAN","COLSPAN"):
                raw=re.sub(r"\[\d+\]","",_txt(row[day_col])); low=raw.lower()
                if low in {"tba","tbd"}: date_iso=None
                else:
                    m=DATE_FULL_RE.search(raw)
                    if m: date_iso=datetime.strptime(f"{m.group(1)} {int(m.group(2))}, {int(m.group(3))}","%B %d, %Y").strftime("%Y-%m-%d"); last_date=date_iso
                    else: y=YEAR_RE.search(raw); date_iso=f"{y.group(1)}-01-01" if y else last_date
            else: date_iso=last_date
            if title: title=re.sub(r"[†‡§]+|\[\d+\]|\s+"," ",title).strip()
            if title and title.lower() in {"title","film","tba","tbd"}: title=None
            if title and date_iso:
                try: fdate=datetime.strptime(date_iso,"%Y-%m-%d").date(); full=not date_iso.endswith("-01-01")
                except: fdate=None; full=False
                if fdate and ((full and fdate<=TODAY) or ((not full) and fdate.year<=TODAY.year)):
                    key=f"{title.lower()}#{int(date_iso[:4])}"; 
                    if key not in seen: seen.add(key); out.append(WFilm(title,date_iso,url,page,full,link_state))
    return out

def trakt_sync_list(per_site_films, per_site_pos, per_site_label, per_site_slug,
                    page_to_qid, qid_to_tmdb, title_lower_to_qid, per_site_url, TRAKT_HEADERS):
    norm_key=lambda s: re.sub(r'[^a-z0-9]+','',(s or '').lower())
    ck=lambda s:(s or "").replace(" ","_")

    def _safe_json_response(resp):
        try: js=resp.json()
        except Exception: js={}
        return js or {}

    def _trakt_post_with_retry(session,url,headers,payload,what,max_retries=6,base_sleep=0.8,timeout=(4,10)):
        _TRANSIENT={429,500,502,503,504}; attempt=0; total_wait=0.0
        while True:
            attempt+=1
            try:
                resp=session.post(url,headers=headers,json=payload,timeout=timeout)
            except requests.RequestException:
                if attempt<=max_retries:
                    wait_s=base_sleep*(2**(attempt-1)); time.sleep(wait_s); total_wait+=wait_s; continue
                return 0,{},total_wait,False
            status=resp.status_code
            if status in _TRANSIENT:
                ra=resp.headers.get("Retry-After")
                if ra:
                    try: wait_s=float(ra)
                    except: wait_s=base_sleep*(2**(attempt-1))
                else:
                    wait_s=base_sleep*(2**(attempt-1))
                time.sleep(wait_s); total_wait+=wait_s
                if attempt<=max_retries: continue
                js=_safe_json_response(resp); return status,js,total_wait,(status==429)
            js=_safe_json_response(resp); return status,js,total_wait,(status==429)

    def _fetch_trakt_items(base,headers):
        cur=[]; pg=1
        while True:
            r=S.get(base+"/items/movies",headers=headers,params={"extended":"full","page":pg,"limit":100},timeout=(4,10))
            js=_safe_json_response(r); js=js if isinstance(js,list) else []; cur+=js
            pc=int(r.headers.get("X-Pagination-Page-Count","1") or "1")
            if pg>=pc or not js: break
            pg+=1
        return cur

    def _pick_one(arr):
        if not arr: return None
        for v in arr:
            sv=str(v).strip()
            if sv: return sv
        return None

    def _tmdb_from_qid(qid):
        if not qid: return None
        return _pick_one(qid_to_tmdb.get(qid,[]))

    qids_manual_map={}
    for t,q in QIDS:
        k=norm_key(t)
        if (q or "").strip():
            qids_manual_map[k]=q.strip()

    title_lower_to_qid_norm={ norm_key(k):v for k,v in title_lower_to_qid.items() }

    def tmdb_id_for_film(f):
        nk=norm_key(getattr(f,'title','') or '')
        qid_manual=qids_manual_map.get(nk)
        if qid_manual:
            tm=_tmdb_from_qid(qid_manual)
            if tm: return tm
        if getattr(f,'page',None):
            qid=page_to_qid.get(ck(f.page)); tm=_tmdb_from_qid(qid)
            if tm: return tm
        qid_auto=title_lower_to_qid_norm.get(nk); tm=_tmdb_from_qid(qid_auto)
        if tm: return tm
        return None

    idxs=list(range(len(per_site_films)))
    groups_by_slug={}
    for i in idxs: groups_by_slug.setdefault(per_site_slug[i], []).append(i)

    label2first_idx={}
    for i in idxs: label2first_idx.setdefault(per_site_label[i], i)

    canonical_label={
        "ink-magic-a-disney-animation-journey": "🪄 Ink & Magic – A Disney Animation Journey",
        "warner-bros-toons-films-tv": "🐰 Warner Bros. Toons — Films & TV"
    }

    label2idx_display={}
    for slug, idx_list in groups_by_slug.items():
        label_out=canonical_label.get(slug, per_site_label[idx_list[0]])
        label2idx_display[label_out]=min(idx_list)

    def variant_tag(label:str):
        L=label.lower()
        if "wdas" in L: return "WDAS"
        if "dtva" in L: return "DTVA"
        if "dts"  in L: return "DTS"
        if " d+ " in f" {label} ": return "D+"
        if "pixar" in L: return "Pixar"
        if "pictures animation" in L: return "WBPA"
        if "animation" in L: return "WBA"
        return label

    all_missing_rows=[]; all_trakt_missing_rows=[]; titles_for_qids_global=set()
    collisions_agg=defaultdict(lambda: {"titles": set(), "sites": set(), "site_idxs": set(), "pos_by_site": {}})
    missing_agg=defaultdict(lambda: {"labels": set(), "site_idxs": set(), "pos_by_site": {}, "min_pos": 10**9})
    trakt_missing_agg=defaultdict(lambda: {"labels": set(), "site_idxs": set(), "pos_by_site": {}, "min_pos": 10**9})

    tmdb_global_map=defaultdict(set)
    for i in idxs:
        for f in per_site_films.get(i,[]):
            tm=tmdb_id_for_film(f)
            if tm: tmdb_global_map[tm].add(f.title)

    tmdb_in_collision={tm for tm,tits in tmdb_global_map.items() if len({t.strip() for t in tits})>=2}

    for slug, idx_list in groups_by_slug.items():
        uniq=[]; seen=set(); pos_union={}
        for i in idx_list:
            films=per_site_films.get(i,[])
            for f in films:
                k=(f.title.strip().lower(), f.date_iso[:4] if f.date_iso else None)
                if k in seen: continue
                seen.add(k); pos_union[k]=len(uniq); uniq.append(f)

        title_to_year={}
        for f in uniq:
            y=(f.date_iso[:4] if f and f.date_iso else None); title_to_year.setdefault(f.title.strip().lower(), y)

        tm_to_titles_local=defaultdict(set); tmdb2title={}
        for f in uniq:
            tm=tmdb_id_for_film(f)
            if tm:
                tm_to_titles_local[tm].add(f.title)
                tmdb2title.setdefault(tm,f.title)

        blocked_tm={ tm for tm in tm_to_titles_local if tm in tmdb_in_collision }

        for tm,titles in tm_to_titles_local.items():
            if tm in blocked_tm:
                for i in idx_list:
                    lbl=per_site_label[i]
                    for t in titles:
                        key=(t.strip().lower(), title_to_year.get(t.strip().lower()))
                        if key in per_site_pos.get(i,{}):
                            collisions_agg[tm]["titles"].add(t); collisions_agg[tm]["sites"].add(lbl); collisions_agg[tm]["site_idxs"].add(i)
                            pos_i=per_site_pos[i][key]; prev=collisions_agg[tm]["pos_by_site"].get(i, 10**9)
                            if pos_i<prev: collisions_agg[tm]["pos_by_site"][i]=pos_i

        site_tmdb_target={ tm for tm in tm_to_titles_local if tm not in blocked_tm }

        base=None; r=S.get(f"https://api.trakt.tv/users/dtvabrand/lists/{slug}",headers=TRAKT_HEADERS,timeout=(4,10)); 
        if r.status_code<400: base=r.request.url
        if base is None:
            label0=per_site_label[idx_list[0]]; name_for_trakt=re.sub(r'^[^\w]+','',label0).strip()
            urls_for_slug=sorted({ per_site_url.get(i) for i in idx_list if per_site_url.get(i) }); desc="\n".join(urls_for_slug)
            _,created,_,_=_trakt_post_with_retry(S,"https://api.trakt.tv/users/dtvabrand/lists",TRAKT_HEADERS,{"name":name_for_trakt,"description":desc,"privacy":"public","display_numbers":False,"allow_comments":False,"sort_by":"released","sort_how":"asc"},"create list")
            got=((created.get("ids") or {}).get("slug") if isinstance(created,dict) else None); base=f"https://api.trakt.tv/users/dtvabrand/lists/{got or slug}"

        before=_fetch_trakt_items(base,TRAKT_HEADERS)
        existing_tmdb=set(); extraneous_trakt_ids=[]
        for it in before:
            mv=(it.get("movie") or {}); ids=(mv.get("ids") or {})
            tm=ids.get("tmdb"); tid=ids.get("trakt")
            if tm is None:
                if tid is not None: extraneous_trakt_ids.append(int(tid))
            else:
                existing_tmdb.add(str(tm))

        wrong_ids=sorted({tm for tm in existing_tmdb if tm not in site_tmdb_target and tm and tm.isdigit()}, key=int)
        to_rm=[{"ids":{"tmdb":int(tm)}} for tm in wrong_ids]
        to_rm_trakt=[{"ids":{"trakt":tid}} for tid in extraneous_trakt_ids]
        to_add=[{"ids":{"tmdb":int(tm)}} for tm in site_tmdb_target if tm not in existing_tmdb and tm and tm.isdigit()]

        if to_rm_trakt:
            for j in range(0,len(to_rm_trakt),100):
                _trakt_post_with_retry(S,base+"/items/remove",TRAKT_HEADERS,{"movies":to_rm_trakt[j:j+100]},"remove items (non-TMDb)")
        if to_rm:
            for j in range(0,len(to_rm),100):
                _trakt_post_with_retry(S,base+"/items/remove",TRAKT_HEADERS,{"movies":to_rm[j:j+100]},"remove items")
        if to_add:
            for j in range(0,len(to_add),100):
                _trakt_post_with_retry(S,base+"/items",TRAKT_HEADERS,{"movies":to_add[j:j+100]},"add items")

        after=_fetch_trakt_items(base,TRAKT_HEADERS)
        after_tmdb={str((it.get("movie") or {}).get("ids",{}).get("tmdb")) for it in after if (it.get("movie") or {}).get("ids",{}).get("tmdb") is not None}

        missing_no_tmdb=[]
        for f in uniq:
            tm=tmdb_id_for_film(f)
            if not tm:
                key=(f.title.strip().lower(), (f.date_iso or "")[:4]); pos=pos_union.get(key,10**9)
                missing_no_tmdb.append((pos,f.title))

        want_not_in_after = sorted({tm for tm in site_tmdb_target if tm not in after_tmdb},
                                   key=lambda x: int(x) if str(x).isdigit() else 10**12)

        trakt_missing=[]
        for tm in want_not_in_after:
            rep_title = tmdb2title.get(tm, f"TMDb:{tm}")
            key=(rep_title.strip().lower(), (next((ff.date_iso for ff in uniq if ff.title==rep_title), "")[:4]))
            pos=pos_union.get(key,10**9); trakt_missing.append((pos,rep_title))

        total_films=len(uniq); in_list=len(after_tmdb)

        def breakdown_counts():
            per_tag={}; title_to_tag={}
            for i in idx_list:
                tag=variant_tag(per_site_label[i])
                for f in per_site_films.get(i,[]): title_to_tag.setdefault(f.title, tag)
            def add(tag):
                if tag: per_tag[tag]=per_tag.get(tag,0)+1
            for _,t in missing_no_tmdb: add(title_to_tag.get(t,""))
            for _,t in trakt_missing:   add(title_to_tag.get(t,""))
            parts=[f"{n} {tg}" for tg,n in per_tag.items() if n>0]
            return f" ({', '.join(parts)})" if parts else ""

        label_out=canonical_label.get(slug, per_site_label[idx_list[0]])
        miss_total=len(missing_no_tmdb)+len(trakt_missing)
        is_multi=len(idx_list)>1 and slug in ("ink-magic-a-disney-animation-journey","warner-bros-toons-films-tv")
        if is_multi:
            print(f"{label_out} – {total_films} film  |  🧩 Trakt list: {in_list}  |  ⚠️ Missing: {miss_total}{breakdown_counts()}")
        else:
            print(f"{label_out} – {total_films} film  |  🧩 Trakt list: {in_list}  |  ⚠️ Missing: {miss_total}")

        for (_pos,title) in missing_no_tmdb:
            dat=missing_agg[title]; dat["min_pos"]=min(dat["min_pos"], _pos)
            for i in idx_list:
                key=(title.strip().lower(), title_to_year.get(title.strip().lower()))
                if key in per_site_pos.get(i,{}):
                    dat["labels"].add(label_out); dat["site_idxs"].add(i)
                    pos_i=per_site_pos[i][key]; prev=dat["pos_by_site"].get(i, 10**9)
                    if pos_i<prev: dat["pos_by_site"][i]=pos_i

        for (_pos,title) in trakt_missing:
            dat=trakt_missing_agg[title]; dat["min_pos"]=min(dat["min_pos"], _pos)
            for i in idx_list:
                key=(title.strip().lower(), title_to_year.get(title.strip().lower()))
                if key in per_site_pos.get(i,{}):
                    dat["labels"].add(label_out); dat["site_idxs"].add(i)
                    pos_i=per_site_pos[i][key]; prev=dat["pos_by_site"].get(i, 10**9)
                    if pos_i<prev: dat["pos_by_site"][i]=pos_i

        for _,t in missing_no_tmdb: titles_for_qids_global.add(t)
        for _,t in trakt_missing: titles_for_qids_global.add(t)

    for dat in collisions_agg.values():
        for tt in dat["titles"]: titles_for_qids_global.add(tt)

    print("")
    if missing_agg:
        def _key_missing(item):
            title, dat=item; msi=min(dat["site_idxs"]) if dat["site_idxs"] else 10**9
            pos=dat["pos_by_site"].get(msi, dat["min_pos"]); return (msi, pos, title.lower())
        print(f"⚠️ TMDb Movie ID missing ({len(missing_agg)})")
        for title, dat in sorted(missing_agg.items(), key=_key_missing):
            labels_sorted=sorted(dat["labels"], key=lambda lbl: label2idx_display.get(lbl, 10**9))
            print(f"• {title} — {', '.join(labels_sorted)}")
        print("")

    if collisions_agg:
        def _key_collision(item):
            _tm, dat=item; msi=min(dat["site_idxs"]) if dat["site_idxs"] else 10**9
            pos=dat["pos_by_site"].get(msi, 10**9)
            titles_joined=", ".join(sorted(dat["titles"], key=str.lower))
            return (msi, pos, titles_joined.lower())
        print(f"⚠️ TMDb Movie ID collisions ({len(collisions_agg)})")
        for _tm, dat in sorted(collisions_agg.items(), key=_key_collision):
            titles_joined=", ".join(sorted(dat["titles"], key=str.lower))
            sites_sorted=sorted(dat["sites"], key=lambda lbl: label2first_idx.get(lbl, 10**9))
            print(f"• {titles_joined} — {', '.join(sites_sorted)}")
        print("")

    if trakt_missing_agg:
        def _key_trakt(item):
            title, dat=item; msi=min(dat["site_idxs"]) if dat["site_idxs"] else 10**9
            pos=dat["pos_by_site"].get(msi, dat["min_pos"]); return (msi, pos, title.lower())
        print(f"⚠️ Trakt film missing ({len(trakt_missing_agg)})")
        for title, dat in sorted(trakt_missing_agg.items(), key=_key_trakt):
            labels_sorted=sorted(dat["labels"], key=lambda lbl: label2idx_display.get(lbl, 10**9))
            print(f"• {title} — {', '.join(labels_sorted)}")

    def _title_order_info():
        info={}
        def upd(t, site_idxs, pos_by_site, min_pos):
            if site_idxs: msi=min(site_idxs); pos=pos_by_site.get(msi, min_pos); cur=(msi, pos)
            else: cur=(10**9, min_pos)
            prev=info.get(t, (10**9,10**9))
            if cur<prev: info[t]=cur
        for title, dat in missing_agg.items(): upd(title, dat["site_idxs"], dat["pos_by_site"], dat["min_pos"])
        for title, dat in trakt_missing_agg.items(): upd(title, dat["site_idxs"], dat["pos_by_site"], dat["min_pos"])
        for _tm, dat in collisions_agg.items():
            for t in dat["titles"]: upd(t, dat["site_idxs"], dat["pos_by_site"], 10**9)
        return info

    order_info=_title_order_info()

    manual_exact={t:q for (t,q) in QIDS if (q or "").strip()}
    existing_by_norm={ norm_key(t): q for (t,q) in QIDS if (q or "").strip() }

    def q_for_title(t):
        nk=norm_key(t)
        return (manual_exact.get(t,"") or existing_by_norm.get(nk,"") or title_lower_to_qid_norm.get(nk,""))

    scraped_title_norms=set()
    for i in per_site_films:
        for f in per_site_films.get(i,[]) or []:
            scraped_title_norms.add(norm_key(getattr(f,'title','') or ''))

    preserved_manual=[(t,q) for (t,q) in QIDS
                      if (q or "").strip() and norm_key(t) in scraped_title_norms]

    preserved_titles=set(t for (t,_) in preserved_manual)
    wanted_titles=set(titles_for_qids_global) | preserved_titles

    def sort_key_title(t):
        return (order_info.get(t,(10**9,10**9))[0], order_info.get(t,(10**9,10**9))[1], t.lower())

    sorted_titles=sorted(wanted_titles, key=sort_key_title)

    out=[]
    seen_norm=set()
    for t in sorted_titles:
        nk=norm_key(t)
        if nk in seen_norm: continue
        q_manual=next((q for (tt,q) in preserved_manual if tt==t and (q or "").strip()), "")
        q_auto=q_for_title(t)
        q = q_manual or q_auto or ""
        out.append((t,q))
        seen_norm.add(nk)

    missing_titles=[t for (t,q) in out if not (q or "").strip()]
    if missing_titles: print("📝 Missing QIDs:", ", ".join(f'"{t}"' for t in missing_titles))
    gh_sync_qid_issue(missing_titles)
    p=os.path.realpath(__file__); s=open(p,encoding="utf-8").read()
    def _dump_QIDS():
        esc=lambda x: json.dumps(str(x),ensure_ascii=False)
        return "QIDS = [\n" + "\n".join(f"    ({esc(m)}, {esc(q)})," for (m,q) in out) + "\n]\n"
    pat = re.compile(r"(?ms)^QIDS\s*=\s*\[.*?\]\s*(?:\r?\n)*")
    block=_dump_QIDS()
    s_new = pat.sub(block + "\n", s) if pat.search(s) else re.sub(r"(?ms)(^SITES\s*=\s*\[.*?\]\s*)", r"\1\n"+block+"\n", s)
    if s_new!=s:
        fd,tmp=tempfile.mkstemp(dir=os.path.dirname(p) or ".",suffix=".py")
        os.fdopen(fd,"w",encoding="utf-8").write(s_new)
        os.replace(tmp,p)

def main():
    _,TRAKT_HEADERS=trakt_auth_refresh()
    variant_label=lambda base,variant: ("🏰 Ink & Magic – WDAS" if variant=="WDAS" else ("🪄 Ink & Magic – DTVA" if variant=="DTVA" else ("🔮 Ink & Magic – DTS" if variant=="DTS" else ("🌠 Ink & Magic – D+" if variant=="D+" else ("💡 Ink & Magic – Pixar" if variant=="Pixar" else ("🐰 Warner Bros. Pictures Animation" if variant=="WBPA" else ("🥕 Warner Bros. Animation" if variant=="WBA" else base)))))))
    per_site_films={}; per_site_pos={}; per_site_label={}; per_site_slug={}; per_site_url={}
    with ThreadPoolExecutor(max_workers=SITE_WORKERS) as ex:
        futs={ex.submit(wikipedia_scraping,u,sel):(i,name,variant,slug) for i,(u,name,variant,slug,sel) in enumerate(SITES)}
        for fu in as_completed(futs):
            i,name,variant,slug=futs[fu]
            try: films=fu.result()
            except Exception: films=[]
            label=variant_label(name,variant); seen=set(); uniq=[]; pos={}
            for f in films:
                key=(f.title.strip().lower(), f.date_iso[:4] if f.date_iso else None)
                if key in seen: continue
                seen.add(key); pos[key]=len(uniq); uniq.append(f)
            per_site_films[i]=uniq; per_site_pos[i]=pos; per_site_label[i]=label; per_site_slug[i]=slug; per_site_url[i]=SITES[i][0]

    all_films=[]
    for i in range(len(SITES)): all_films.extend(per_site_films.get(i,[]))

    ck=lambda s:(s or "").replace(" ","_")

    pages=list(dict.fromkeys([f.page for f in all_films if f.page])); page_to_qid={}
    with ThreadPoolExecutor(max_workers=WD_WORKERS) as ex:
        futs=[ex.submit(S.get,"https://en.wikipedia.org/w/api.php",
                        params={"action":"query","prop":"pageprops","ppprop":"wikibase_item","format":"json",
                                "titles":"|".join(pages[i:i+50]),"redirects":1},
                        timeout=HTTP_TIMEOUT) for i in range(0,len(pages),50)]
        for fu in as_completed(futs):
            try:
                q=fu.result().json().get("query") or {}; canon={}
                for pg in (q.get("pages") or {}).values():
                    t=(pg.get("title") or "").strip(); qid=((pg.get("pageprops") or {}).get("wikibase_item"))
                    if t: canon[t]=qid; page_to_qid[ck(t)]=qid
                for rdir in (q.get("normalized") or [])+(q.get("redirects") or []):
                    f=(rdir.get("from") or "").strip(); t=(rdir.get("to") or "").strip()
                    if f and t:
                        qid=canon.get(t) or page_to_qid.get(ck(t))
                        if qid is not None: page_to_qid[ck(f)]=qid
            except: pass

    qids_from_pages=[page_to_qid.get(ck(f.page)) for f in all_films if f.page and page_to_qid.get(ck(f.page))]
    qids_from_qids=[(q or "").strip() for (_t,q) in QIDS if (q or "").strip()]
    qids=sorted({*qids_from_pages,*qids_from_qids})

    qid_to_tmdb={}
    with ThreadPoolExecutor(max_workers=WD_WORKERS) as ex:
        futs=[ex.submit(S.get,"https://www.wikidata.org/w/api.php",
                        params={"action":"wbgetentities","format":"json","formatversion":2,
                                "ids":"|".join(qids[i:i+50]),"props":"claims"},
                        timeout=HTTP_TIMEOUT) for i in range(0,len(qids),50)]
        for fu in as_completed(futs):
            try:
                for e in (fu.result().json().get("entities") or {}).values():
                    cl=(e.get("claims") or {})
                    vals=lambda p:[(c.get("mainsnak",{}).get("datavalue") or {}).get("value") for c in cl.get(p,[]) if c.get("mainsnak",{}).get("datavalue")]
                    tmdb=[str(v) for v in vals("P4947") if v is not None]
                    qid_to_tmdb[e.get("id") or ""]=tmdb
            except: pass

    title_lower_to_qid={}
    for i in range(len(SITES)):
        for f in per_site_films.get(i,[]):
            if f.page:
                qid=page_to_qid.get(ck(f.page))
                if qid: title_lower_to_qid.setdefault(f.title.strip().lower(),qid)
    for t,q in QIDS:
        qq=(q or "").strip()
        if qq:
            tl=t.strip().lower()
            if tl and tl not in title_lower_to_qid:
                title_lower_to_qid[tl]=qq

    trakt_sync_list(per_site_films, per_site_pos, per_site_label, per_site_slug,
                    page_to_qid, qid_to_tmdb, title_lower_to_qid, per_site_url, TRAKT_HEADERS)

if __name__ == "__main__":
    main()
