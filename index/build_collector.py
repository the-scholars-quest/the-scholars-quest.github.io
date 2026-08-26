import pandas as pd
import re
import os
import sys

# --- CONFIGURATION ---
INPUT_CSV = "final_sorted_database.csv"
COLLECTIONS_FILE = "collections.html"
OUT_DIR = "1000"

# --- 1. THE JAVASCRIPT SEARCH & PAGINATION ENGINE ---
JS_ENGINE = """
<script>
document.addEventListener("DOMContentLoaded", () => {
    const searchInput = document.getElementById("dbSearch");
    const catFilter = document.getElementById("dbCategoryFilter");
    const typeFilter = document.getElementById("dbTypeFilter");
    const loadMoreBtn = document.getElementById("loadMoreBtn");
    const categoryButtons = document.getElementById("categoryButtons");
    
    const allItems = Array.from(document.querySelectorAll(".db-item"));
    let currentMatches = [...allItems];
    let visibleCount = 0;
    const CHUNK_SIZE = 50;

    function renderChunk() {
        const nextLimit = Math.min(visibleCount + CHUNK_SIZE, currentMatches.length);
        for (let i = visibleCount; i < nextLimit; i++) {
            currentMatches[i].style.display = "block";
        }
        visibleCount = nextLimit;
        
        if (visibleCount < currentMatches.length) {
            loadMoreBtn.style.display = "block";
        } else {
            loadMoreBtn.style.display = "none";
        }
    }

    function applyFilters() {
        const query = searchInput ? searchInput.value.toLowerCase() : "";
        const selectedCat = catFilter ? catFilter.value : "all";
        const selectedType = typeFilter ? typeFilter.value : "all";

        if (categoryButtons) {
            categoryButtons.style.display = (query === "" && selectedCat === "all" && selectedType === "all") ? "block" : "none";
        }

        allItems.forEach(item => item.style.display = "none");

        currentMatches = allItems.filter(item => {
            const text = item.innerText.toLowerCase();
            const tags = (item.getAttribute("data-tags") || "").toLowerCase();
            const type = item.getAttribute("data-type");
            const cat = item.getAttribute("data-category");

            const matchesSearch = text.includes(query) || tags.includes(query);
            const matchesCat = (selectedCat === "all" || cat.startsWith(selectedCat));
            const matchesType = (selectedType === "all" || type === selectedType);

            return matchesSearch && matchesCat && matchesType;
        });

        visibleCount = 0;
        renderChunk();
    }

    if(searchInput) searchInput.addEventListener("input", applyFilters);
    if(catFilter) catFilter.addEventListener("change", applyFilters);
    if(typeFilter) typeFilter.addEventListener("change", applyFilters);
    if(loadMoreBtn) loadMoreBtn.addEventListener("click", renderChunk);

    applyFilters();
});
</script>
"""

# --- 2. HTML GENERATORS ---
def generate_search_ui(hide_category_filter=False):
    cat_dropdown = ""
    if not hide_category_filter:
        cat_dropdown = """
        <select id="dbCategoryFilter">
            <option value="all">All Categories</option>
            <option value="000">000 - Generalities</option><option value="100">100 - Science</option>
            <option value="200">200 - Technology</option><option value="300">300 - Sociology</option>
            <option value="400">400 - Language</option><option value="500">500 - History</option>
            <option value="600">600 - Literature</option><option value="700">700 - Philosophy</option>
            <option value="800">800 - Arts</option><option value="900">900 - Fitness</option>
        </select>
        """
        
    return f"""
    <div class="db-controls">
        <input type="text" id="dbSearch" placeholder="Search entries, tags, or links...">
        <div class="db-filters">
            {cat_dropdown}
            <select id="dbTypeFilter">
                <option value="all">All Media</option>
                <option value="Link">Links</option>
                <option value="Text">Text</option>
                <option value="Video">Video</option>
            </select>
        </div>
    </div>
    """

def row_to_html(row):
    tags = str(row.get('Tags', '')).strip().lower()
    media_type = str(row.get('Media_Type', '')).strip()
    category = str(row.get('Category', '')).strip()
    
    content = str(row.get('Merged_Content', '')).replace('\n', '<br>')
    content = re.sub(r'(https?://[^\s<>")]+)', r'<a href="\1" target="_blank">\1</a>', content)
    
    tag_list = [t.strip() for t in tags.split(',') if t.strip()]
    tags_display = " ".join([f'<span class="db-tag">#{t}</span>' for t in tag_list])
    
    return f'''
    <div class="db-item" data-tags="{tags}" data-type="{media_type}" data-category="{category}">
        <div class="db-item-meta">
            <span class="db-type-badge">{media_type}</span>
            <div class="db-tags-wrapper">{tags_display}</div>
        </div>
        <div class="db-item-content">{content}</div>
    </div>
    '''

# --- 3. BUILD THE SITE ---
print("Loading Database...")
df = pd.read_csv(INPUT_CSV, encoding="utf-8")
df = df[~df['Category'].str.contains("---", na=False)]
df = df[~df['Category'].str.contains("REPORT:", na=False)].dropna(subset=['Category'])

if not os.path.exists(OUT_DIR): os.makedirs(OUT_DIR)

# A. Build the Master List for Collections.html
print("Injecting master list into collections.html...")
master_html = '<div id="ai-database-container">\n'
for _, row in df.iterrows():
    master_html += row_to_html(row)
master_html += '<button id="loadMoreBtn" class="load-more-btn">Load 50 More Results ⬇</button>\n</div>\n' + JS_ENGINE

try:
    with open(COLLECTIONS_FILE, 'r', encoding='utf-8') as f:
        collections_code = f.read()
    
    # We replace the markers you placed in collections.html previously
    if "<!-- INJECT_SEARCH_UI_HERE -->" in collections_code:
        collections_code = collections_code.split("<!-- INJECT_SEARCH_UI_HERE -->")[0] + "<!-- INJECT_SEARCH_UI_HERE -->\n" + generate_search_ui() + "\n" + collections_code.split("<!-- INJECT_SEARCH_UI_HERE -->")[1]
    
    # Replace everything after the database marker with the fresh database
    if "<!-- INJECT_MASTER_DATABASE_HERE -->" in collections_code:
        collections_code = collections_code.split("<!-- INJECT_MASTER_DATABASE_HERE -->")[0] + "<!-- INJECT_MASTER_DATABASE_HERE -->\n" + master_html + "\n  </div>\n  </div>\n</div>\n</body>\n</html>"
    
    with open("collections_updated.html", 'w', encoding='utf-8') as f:
        f.write(collections_code)
except Exception as e:
    print(f"Error updating collections.html: {e}")

# B. Build the Individual Category Pages (000.html, 100.html, etc.)
print("Generating individual category pages...")
for category, group in df.groupby('Category'):
    cat_prefix = str(category).split('-')[0].strip()
    short_title = str(category).split('-')[1].strip() if '-' in str(category) else str(category)
    
    cat_items_html = '<div id="ai-database-container">\n' + generate_search_ui(hide_category_filter=True)
    for _, row in group.iterrows():
        cat_items_html += row_to_html(row)
    cat_items_html += '<button id="loadMoreBtn" class="load-more-btn">Load 50 More Results ⬇</button>\n</div>\n' + JS_ENGINE

    page_html = f"""<!DOCTYPE html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width">
<title>The Scholar - {cat_prefix}</title>
<link rel="stylesheet" href="../chile.css">
<link rel="icon" type="image/x-icon" href="../imgs/favicon.ico">

<div class="videoseal">
  <video autoplay loop muted playsinline preload="auto" src="../vids/bg1.mp4" class="video1"></video>
  <div class="overlay"> 
    <header class="overlayheader"> 
        <u1>
            <l1><a rel="home" class="headertext" href="../../main.html">Home&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</a></l1>
            <l1><a rel="personal" class="headertext" href="../personal.html">Personal&nbsp;&nbsp;&nbsp;&nbsp;</a></l1>
            <l1><a rel="linkroll" class="headertext" href="../linkroll.html">Linkroll&nbsp;&nbsp;&nbsp;&nbsp;</a></l1>
            <l1><a rel="collections" class="headertext" href="../collections.html">Collections</a></l1>
        </u1>
    </header>
  <div class="maintextchile2">
        <div class="main2text">
          <h1 style="background-image: url(../imgs/{cat_prefix}.png);background-position:90% 15%;">
          <a>{cat_prefix} - {short_title}</a>
          </h1>
        </div>
      <hr>
      <p><a href="../collections.html">Back! |</a>
      <a href="000.html">000 |</a><a href="100.html">100 |</a><a href="200.html">200 |</a>
      <a href="300.html">300 |</a><a href="400.html">400 |</a><a href="500.html">500 |</a>
      <a href="600.html">600 |</a><a href="700.html">700 |</a><a href="800.html">800 |</a><a href="900.html">900 |</a></p>
      <br>
      
      {cat_items_html}
      
    </div>
  </div>
</div>
</html>"""

    file_path = os.path.join(OUT_DIR, f"{cat_prefix}.html")
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(page_html)
    print(f"   ✅ Created {file_path}")

print("🎉 Complete! Rename collections_updated.html to collections.html, and push your files to GitHub!")