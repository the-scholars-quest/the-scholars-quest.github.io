import pandas as pd
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
import json
import re
import os
import sys
import time
import requests
from bs4 import BeautifulSoup
import concurrent.futures

# --- PYDANTIC SCHEMAS ---
class GroupedEntry(BaseModel):
    Merged_Content: str = Field(description="The combined text of the grouped messages")
    Category: str = Field(description="The Dewey Decimal category chosen")
    Tags: str = Field(description="Comma-separated list of tags")
    Media_Type: str = Field(description="Link / Text / Video")

class GroupedEntryList(BaseModel):
    entries: list[GroupedEntry]

class SortedOrder(BaseModel):
    ordered_ids: list[int] = Field(description="The list of IDs sorted in optimal semantic order.")

MASTER_TAGS = "finance, geopolitics, history, sociology, architecture, agriculture, trade, energy, demographics, china, japan, russia, usa, europe, middle east, technology, media, culture, philosophy"

# --- HELPER: DISCORD SCRAPER ---
def resolve_and_scrape_url(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try: 
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            title = soup.title.string.strip() if soup.title and soup.title.string else "No Title Found"
            return url, None, title, "Live"
    except: pass
    try: 
        api_res = requests.get(f"http://archive.org/wayback/available?url={url}", timeout=5).json()
        if "closest" in api_res.get("archived_snapshots", {}):
            return url, api_res["archived_snapshots"]["closest"]["url"], "Archived Page", "Archived"
    except: pass
    return url, None, "Dead Link", "Dead"

def process_discord_row(row):
    text = row['text']
    raw_urls = set(re.findall(r'https?://[^\s<>"]+', text))
    urls = [u.rstrip('.,;:)') for u in raw_urls]
    for url in urls:
        _, arch, title, status = resolve_and_scrape_url(url)
        text += f"\n(Title: {title})"
        if status == "Archived": text += f"\n[SYSTEM NOTE: Archive Backup: {arch}]"
        elif status == "Dead": text += f"\n[SYSTEM NOTE: Link is dead. Manual review needed.]"
    return {"timestamp": row['timestamp'], "text": text}

# --- PIPELINE PHASES ---
def phase1_ingest(client, file_path):
    print(f"\n[PHASE 1] Ingesting {file_path}...")
    ext = os.path.splitext(file_path)[1].lower()
    
    # 1A: DISCORD (.csv)
    if ext == '.csv':
        df = pd.read_csv(file_path, encoding="utf-8", on_bad_lines="skip", engine="python")
        raw_rows = []
        for _, row in df.iterrows():
            text = str(row.get('Content', '')).strip()
            if text: raw_rows.append({"timestamp": str(row.get('Date', '')), "text": text})
            
        print(f"Scraping links for {len(raw_rows)} Discord messages...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=40) as executor:
            enriched = list(executor.map(process_discord_row, raw_rows))
            
        batches = [enriched[i:i+100] for i in range(0, len(enriched), 100)]
        prompt_template = "Group related messages. Categorize using Dewey Decimal. Generalize tags.\nTIMELINE:\n{}"
        
    # 1B: TWITTER (.txt)
    elif ext == '.txt':
        with open(file_path, 'r', encoding='utf-8') as f: blocks = f.read().split("========================================")
        cleaned_tweets, context = [], ""
        for b in blocks:
            if not b.strip(): continue
            author = (re.search(r'AUTHOR:\s*(.+)', b) or [None, "Unknown"])[1].strip()
            t_type = (re.search(r'TYPE:\s*(.+)', b) or [None, "Post"])[1].strip()
            url = (re.search(r'URL:\s*(.+)', b) or [None, ""])[1].strip()
            parts = b.split("----------------------------------------")
            if len(parts) < 2: continue
            
            clean_lines = [l.strip() for l in parts[1].split('\n') if l.strip() and not re.fullmatch(r'^\d+[KMB]?$', l.strip()) and l.strip() not in ["Quote", "Show more", "Show", "Relevant", "Last edited"]]
            body = " ".join(clean_lines)
            
            if "Context" in t_type:
                context = f"[CONTEXT]: {body}\n"
            else:
                cleaned_tweets.append(f"{context}[POST by {author}]: {body}\n(URL: {url})")
                context = ""
                
        batches = [cleaned_tweets[i:i+40] for i in range(0, len(cleaned_tweets), 40)]
        prompt_template = "Group related X/Twitter posts. Categorize using Dewey Decimal. Generalize tags. Extract URLs.\nTIMELINE:\n{}"
    else:
        print("❌ Unsupported file type. Use .csv (Discord) or .txt (Twitter).")
        sys.exit(1)

    # PROCESS BATCHES WITH AI
    print(f"Sending {len(batches)} batches to Gemini AI...")
    all_new_entries = []
    for i, batch in enumerate(batches):
        timeline = "\n---\n".join([str(b) for b in batch])
        success, retries = False, 0
        while not success and retries < 3:
            try:
                res = client.models.generate_content(
                    model='gemini-3.6-flash',
                    contents=prompt_template.format(timeline) + f"\nPREFERRED TAGS: {MASTER_TAGS}",
                    config=types.GenerateContentConfig(temperature=0.1, response_mime_type="application/json", response_schema=GroupedEntryList)
                )
                all_new_entries.extend(json.loads(res.text).get("entries", []))
                print(f"   ✅ Batch {i+1}/{len(batches)} tagged!")
                success = True
            except Exception as e:
                retries += 1
                print(f"   ⚠️ API Stutter: {e}. Retrying...")
                time.sleep(5)
                
    if all_new_entries:
        df_new = pd.DataFrame(all_new_entries)
        file_exists = os.path.isfile("ai_tagged_database.csv")
        df_new.to_csv("ai_tagged_database.csv", mode='a', header=not file_exists, index=False)
        print("✅ Raw AI Tagging Complete & Appended to ai_tagged_database.csv!")

def phase2_organize(client):
    print("\n[PHASE 2] Compiling and Semantically Sorting Master Database...")
    df = pd.read_csv("ai_tagged_database.csv").dropna(subset=['Category'])
    df = df[~df['Category'].str.contains("--- SYSTEM REPORT ---|REPORT:|--- END OF REPORT ---", na=False)]
    
    final_rows = []
    for category, group_df in df.groupby('Category'):
        cat_rows = []
        for media_type, sub_group in group_df.groupby('Media_Type'):
            unique_tags = list(sub_group['Tags'].unique())
            item_map = "\n".join([f"ID {i} | Tags: {t}" for i, t in enumerate(unique_tags)])
            
            prompt = f"Sort these unique TAG GROUPS in Category: '{category}', Media Type: '{media_type}' logically from general to specific.\n{item_map}"
            
            if len(unique_tags) > 1:
                try:
                    res = client.models.generate_content(
                        model='gemini-3.6-flash', contents=prompt,
                        config=types.GenerateContentConfig(temperature=0.0, response_mime_type="application/json", response_schema=SortedOrder)
                    )
                    ordered_ids = json.loads(res.text).get("ordered_ids", [])
                    final_order = ordered_ids + list(set(range(len(unique_tags))) - set(ordered_ids))
                except:
                    final_order = list(range(len(unique_tags))) # Fallback
            else:
                final_order = [0]
                
            for tag_id in final_order:
                if tag_id < len(unique_tags):
                    cat_rows.extend(sub_group[sub_group['Tags'] == unique_tags[tag_id]].to_dict('records'))
                    
        # Append Category Reports
        cat_tags = {t.strip().lower() for r in cat_rows for t in str(r.get("Tags", "")).split(",") if t.strip()}
        dead = [r["Merged_Content"][:100] for r in cat_rows if "Manual review needed" in str(r.get("Merged_Content"))]
        
        final_rows.extend(cat_rows)
        final_rows.extend([
            {"Merged_Content": f"=== END OF {category.upper()} ===", "Category": "--- CATEGORY REPORT ---", "Tags": "---", "Media_Type": "---"},
            {"Merged_Content": f"TOTAL ENTRIES: {len(cat_rows)}", "Category": "REPORT: Stats", "Tags": "", "Media_Type": ""},
            {"Merged_Content": f"UNIQUE TAGS:\n{', '.join(sorted(list(cat_tags)))}", "Category": "REPORT: Tag Pool", "Tags": "", "Media_Type": ""},
            {"Merged_Content": f"DEAD LINKS FOUND:\n" + ("\n".join(dead) if dead else "None"), "Category": "REPORT: Alerts", "Tags": "", "Media_Type": ""},
            {"Merged_Content": "=======================================\n\n", "Category": "---", "Tags": "---", "Media_Type": "---"}
        ])

    pd.DataFrame(final_rows).to_csv("final_sorted_database.csv", index=False)
    print("✅ Master Database compiled to final_sorted_database.csv!")

def phase3_build():
    print("\n[PHASE 3] Generating Website HTML...")
    df = pd.read_csv("final_sorted_database.csv")
    df = df[~df['Category'].str.contains("---", na=False)]
    df = df[~df['Category'].str.contains("REPORT:", na=False)].dropna(subset=['Category'])

    # Standard Search Engine & HTML Gen functions (Minified for builder)
    search_ui = '''<div class="db-controls"><input type="text" id="dbSearch" placeholder="Search entries, tags..."><div class="db-filters"><select id="dbCategoryFilter"><option value="all">All Categories</option><option value="000">000</option><option value="100">100</option><option value="200">200</option><option value="300">300</option><option value="400">400</option><option value="500">500</option><option value="600">600</option><option value="700">700</option><option value="800">800</option><option value="900">900</option></select><select id="dbTypeFilter"><option value="all">All Media</option><option value="Link">Links</option><option value="Text">Text</option><option value="Video">Video</option></select></div></div>'''
    
    js_engine = '''<script>document.addEventListener("DOMContentLoaded",()=>{const e=document.getElementById("dbSearch"),t=document.getElementById("dbCategoryFilter"),l=document.getElementById("dbTypeFilter"),n=document.getElementById("loadMoreBtn"),d=document.getElementById("categoryButtons"),c=Array.from(document.querySelectorAll(".db-item"));let o=[...c],a=0;function s(){const e=Math.min(a+50,o.length);for(let t=a;t<e;t++)o[t].style.display="block";a=e,n&&(n.style.display=a<o.length?"block":"none")}function y(){const n=e?e.value.toLowerCase():"",y=t?t.value:"all",r=l?l.value:"all";d&&(d.style.display=""===n&&"all"===y&&"all"===r?"block":"none"),c.forEach((e=>e.style.display="none")),o=c.filter((e=>{const t=e.innerText.toLowerCase(),l=(e.getAttribute("data-tags")||"").toLowerCase(),d=e.getAttribute("data-type"),c=e.getAttribute("data-category");return(t.includes(n)||l.includes(n))&&("all"===y||c.startsWith(y))&&("all"===r||d===r)})),a=0,s()}e&&e.addEventListener("input",y),t&&t.addEventListener("change",y),l&&l.addEventListener("change",y),n&&n.addEventListener("click",s),y()});</script>'''

    def row_html(row):
        t, m, c, txt = str(row.get('Tags','')).lower(), str(row.get('Media_Type','')), str(row.get('Category','')), str(row.get('Merged_Content','')).replace('\n', '<br>')
        txt = re.sub(r'(https?://[^\s<>")]+)', r'<a href="\1" target="_blank">\1</a>', txt)
        tags = " ".join([f'<span class="db-tag">#{x.strip()}</span>' for x in t.split(',') if x.strip()])
        return f'<div class="db-item" data-tags="{t}" data-type="{m}" data-category="{c}"><div class="db-item-meta"><span class="db-type-badge">{m}</span><div class="db-tags-wrapper">{tags}</div></div><div class="db-item-content">{txt}</div></div>\n'

    # Master Collections
    master_html = '<div id="ai-database-container">\n' + "".join([row_html(row) for _, row in df.iterrows()]) + '<button id="loadMoreBtn" class="load-more-btn">Load 50 More ⬇</button></div>' + js_engine
    try:
        with open("collections.html", "r", encoding="utf-8") as f: code = f.read()
        if "<!-- INJECT_SEARCH_UI_HERE -->" in code: code = code.split("<!-- INJECT_SEARCH_UI_HERE -->")[0] + "<!-- INJECT_SEARCH_UI_HERE -->\n" + search_ui + "\n" + code.split("<!-- INJECT_SEARCH_UI_HERE -->")[1]
        if "<!-- INJECT_MASTER_DATABASE_HERE -->" in code: code = code.split("<!-- INJECT_MASTER_DATABASE_HERE -->")[0] + "<!-- INJECT_MASTER_DATABASE_HERE -->\n" + master_html + "\n</div></div></div></body></html>"
        with open("collections.html", "w", encoding="utf-8") as f: f.write(code)
    except Exception as e: print("Error updating collections.html:", e)

    # 1000/ Subpages
    if not os.path.exists("1000"): os.makedirs("1000")
    for category, group in df.groupby('Category'):
        prefix = str(category).split('-')[0].strip()
        cat_html = f'<div id="ai-database-container">\n{search_ui.replace("dbCategoryFilter", "hiddenFilter")}' + "".join([row_html(r) for _, r in group.iterrows()]) + '<button id="loadMoreBtn" class="load-more-btn">Load 50 More ⬇</button></div>' + js_engine
        
        template = f"""<!DOCTYPE html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>The Scholar - {prefix}</title><link rel="stylesheet" href="../chile.css"><div class="videoseal"><video autoplay loop muted playsinline src="../vids/bg1.mp4" class="video1"></video><div class="overlay"><header class="overlayheader"><u1><l1><a class="headertext" href="../../main.html">Home </a></l1><l1><a class="headertext" href="../personal.html">Personal </a></l1><l1><a class="headertext" href="../collections.html">Collections</a></l1></u1></header><div class="maintextchile2"><div class="main2text"><h1 style="background-image:url(../imgs/{prefix}.png);background-position:90% 15%;"><a>{category}</a></h1></div><hr><p><a href="../collections.html">Back! |</a><a href="000.html">000 |</a><a href="100.html">100 |</a><a href="200.html">200 |</a><a href="300.html">300 |</a><a href="400.html">400 |</a><a href="500.html">500 |</a><a href="600.html">600 |</a><a href="700.html">700 |</a><a href="800.html">800 |</a><a href="900.html">900 |</a></p><br>{cat_html}</div></div></div></html>"""
        with open(f"1000/{prefix}.html", "w", encoding="utf-8") as f: f.write(template)

    print("✅ Web pages successfully rebuilt!")

# --- MAIN MENU ---
if __name__ == "__main__":
    print("========================================")
    print("  THE SCHOLAR - UNIFIED DATA PIPELINE   ")
    print("========================================\n")
    
    api_key = input("🔑 1. Paste your Gemini API Key: ").strip()
    client = genai.Client(api_key=api_key)
    
    print("\n📁 2. Enter the path to your raw data file")
    print("      (e.g., discord_log.csv OR twitter_archive.txt)")
    file_path = input("      Path: ").strip().strip('"').strip("'")
    
    phase1_ingest(client, file_path)
    phase2_organize(client)
    phase3_build()
    
    print("\n🎉 ALL DONE! Your database has been merged and your HTML files are updated.")
    print("👉 Just run: git add . -> git commit -m 'update' -> git push")