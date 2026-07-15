import xml.etree.ElementTree as ET
import os
import json
import re
import glob
import urllib.request
from html import unescape

def find_feed_file():
    feed_files = glob.glob('Blogs/**/feed.atom', recursive=True)
    if not feed_files:
        raise FileNotFoundError("Could not find feed.atom in any Blogs subfolder.")
    return feed_files[0]

def format_date(date_str):
    try:
        # e.g., '2024-05-07T07:28:00.001Z'
        dt = date_str.split('T')[0]
        y, m, d = dt.split('-')
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        return f"{months[int(m)-1]} {int(d)}, {y}"
    except Exception:
        return date_str

def clean_excerpt(html_content, max_len=160):
    # Strip HTML tags
    text = re.sub(r'<[^>]+>', ' ', html_content)
    # Decode HTML entities
    text = unescape(text)
    # Clean up whitespace
    text = ' '.join(text.split())
    if len(text) > max_len:
        return text[:max_len].strip() + '...'
    return text

def find_cover_image(content):
    img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content)
    if img_match:
        return img_match.group(1)
    return None

def calculate_read_time(content):
    text = re.sub(r'<[^>]+>', ' ', content)
    words = len(text.split())
    return max(1, round(words / 200))

def rewrite_internal_links(content, current_depth):
    rel_prefix = '../' * current_depth if current_depth > 0 else './'
    # Rewrite blogspot posts
    pattern = r'https?://[^/]+(?:blogspot\.com)?/(\d{4}/\d{2}/[^"\'>]+\.html)'
    content = re.sub(pattern, lambda m: rel_prefix + m.group(1), content)
    # Rewrite blogspot pages
    page_pattern = r'https?://[^/]+(?:blogspot\.com)?/p/([^"\'>]+\.html)'
    content = re.sub(page_pattern, lambda m: rel_prefix + 'p/' + m.group(1), content)
    return content

def inject_contextual_links(content, current_url, posts_metadata, rel_path):
    injected = 0
    candidates = []
    
    for p in posts_metadata:
      p_url = p.get('url')
      if not p_url or p_url == current_url:
        continue
      terms = [p['title']]
      if p.get('tags'):
        terms.extend(p['tags'])
      for term in terms:
        if len(term) > 5:
          candidates.append((term, p_url))
          
    candidates.sort(key=lambda x: len(x[0]), reverse=True)
    
    for kw, target_url in candidates:
      if injected >= 2:
        break
      pattern = re.compile(rf'\b({re.escape(kw)})\b', re.IGNORECASE)
      parts = re.split(r'(<[^>]+>)', content)
      modified = False
      for idx in range(len(parts)):
        if idx % 2 == 0 and not parts[idx].startswith('<'):
          text_part = parts[idx]
          match = pattern.search(text_part)
          if match:
            matched_text = match.group(1)
            relative_target = rel_path + target_url.lstrip('/')
            parts[idx] = pattern.sub(f'<a href="{relative_target}" style="color: var(--accent-color); text-decoration: underline;">{matched_text}</a>', text_part, count=1)
            injected += 1
            modified = True
            break
      if modified:
        content = "".join(parts)
    return content

def sanitize_blogger_html(content, post_title=None):
    alt_text = post_title.replace('"', '&quot;') if post_title else "puru world official image"
    
    # 1. Convert Blogger tr-caption-container tables to modern figure/figcaption elements
    table_pattern = r'<table[^>]*class="[^"]*tr-caption-container[^"]*"[^>]*>\s*<tbody>\s*<tr>\s*<td[^>]*>(.*?)</td>\s*</tr>\s*<tr>\s*<td[^>]*class="tr-caption"[^>]*>(.*?)</td>\s*</tr>\s*</tbody>\s*</table>'
    
    def replace_table(match):
        img_td_content = match.group(1)
        caption_content = match.group(2).strip()
        
        # Strip width, height, border, style attributes from anchor and image tags inside TD
        img_td_content = re.sub(r'\bwidth="\d+"', '', img_td_content)
        img_td_content = re.sub(r'\bheight="\d+"', '', img_td_content)
        img_td_content = re.sub(r'\bborder="\d+"', '', img_td_content)
        img_td_content = re.sub(r'style="[^"]*"', '', img_td_content)
        
        # If alt tag is missing, inject the post title
        if 'alt=' not in img_td_content:
            img_td_content = re.sub(r'<img\s+', f'<img alt="{alt_text}" ', img_td_content)
        
        # Inject standard post-image styles and lazy load markers
        img_td_content = re.sub(
            r'<img\s+([^>]*?)>',
            lambda m: f'<img {m.group(1)} loading="lazy" decoding="async" class="post-image">',
            img_td_content
        )
        return f'<figure class="post-figure">{img_td_content}<figcaption class="post-figcaption">{caption_content}</figcaption></figure>'

    content = re.sub(table_pattern, replace_table, content, flags=re.DOTALL | re.IGNORECASE)

    # 2. Convert standard paragraphs that are center-aligned layout separators
    content = re.sub(r'<div[^>]*class="[^"]*separator[^"]*"[^>]*style="[^"]*"[^>]*>', r'<div class="separator">', content, flags=re.IGNORECASE)
    content = re.sub(r'<div[^>]*class="[^"]*mobile-photo[^"]*"[^>]*style="[^"]*"[^>]*>', r'<div class="mobile-photo">', content, flags=re.IGNORECASE)

    # 3. Clean and lazy-load all remaining image tags
    def clean_standalone_img(match):
        img_tag = match.group(0)
        if 'class="post-image"' in img_tag or 'class=\'post-image\'' in img_tag:
            return img_tag

        img_tag = re.sub(r'\bwidth="\d+"', '', img_tag)
        img_tag = re.sub(r'\bheight="\d+"', '', img_tag)
        img_tag = re.sub(r'\bborder="\d+"', '', img_tag)
        img_tag = re.sub(r'style="[^"]*"', '', img_tag)

        attrs = []
        if 'alt=' not in img_tag:
            attrs.append(f'alt="{alt_text}"')
        if 'loading=' not in img_tag:
            attrs.append('loading="lazy"')
        if 'decoding=' not in img_tag:
            attrs.append('decoding="async"')
        if 'class=' not in img_tag:
            attrs.append('class="post-image"')
        else:
            img_tag = re.sub(r'class="([^"]*)"', r'class="\1 post-image"', img_tag)

        attr_str = ' ' + ' '.join(attrs)
        if img_tag.endswith('/>'):
            return img_tag[:-2] + attr_str + ' />'
        elif img_tag.endswith('>'):
            return img_tag[:-1] + attr_str + '>'
        return img_tag

    content = re.sub(r'<img\s+[^+]+>', clean_standalone_img, content, flags=re.IGNORECASE)
    return content

def classify_video(title):
    t_lower = title.lower()
    
    # Gaming keywords
    gaming_keywords = [
        "match", "gameplay", "wukong", "level devil", "cod", "pubg", 
        "free fire", "ranked", "boss", "ending", "gaming", "troll", 
        "moye moye", "clutch", "gta", "survival", "minecraft", "counter strike",
        "csgo", "valorant", "bgmi", "gamer", "fighting"
    ]
    # Coding & Tech keywords
    tech_keywords = [
        "java", "tutorial", "code", "command prompt", "star wars", 
        "programming", "python", "developer", "c++", "cmd", "setup",
        "star wars in cmd", "hack", "scripts"
    ]
    
    if any(k in t_lower for k in gaming_keywords):
        return "Gaming"
    elif any(k in t_lower for k in tech_keywords):
        return "Coding & Tech"
    else:
        return "Others"

def parse_videos_from_contents(contents):
    videos = []
    continuation_token = None
    
    for item in contents:
        # Check for video item
        rich_item = item.get('richItemRenderer', {})
        lockup = rich_item.get('content', {}).get('lockupViewModel', {})
        if lockup:
            video_id = lockup.get('contentId')
            metadata = lockup.get('metadata', {}).get('lockupMetadataViewModel', {})
            title = metadata.get('title', {}).get('content')
            
            meta_rows = metadata.get('metadata', {}).get('contentMetadataViewModel', {}).get('metadataRows', [])
            views = ""
            time_ago = ""
            if meta_rows:
                parts = meta_rows[0].get('metadataParts', [])
                if len(parts) > 0:
                    views = parts[0].get('text', {}).get('content', '')
                if len(parts) > 1:
                    time_ago = parts[1].get('text', {}).get('content', '')
                    
            category = classify_video(title)
            
            videos.append({
                'id': video_id,
                'title': title,
                'views': views,
                'timeAgo': time_ago,
                'thumbnail': f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
                'category': category
            })
            
        # Check for continuation item
        cont_item = item.get('continuationItemRenderer', {})
        if cont_item:
            continuation_token = cont_item.get('continuationEndpoint', {}).get('continuationCommand', {}).get('token')
            
    return videos, continuation_token

def fetch_youtube_videos(channel_id):
    # Fetch all video items programmatically using continuation tokens
    url = f"https://www.youtube.com/@PuruWorld/videos"
    print(f"Ingesting all videos from: {url}")
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8')
            
        # Extract INNERTUBE API Key
        api_key_match = re.search(r'"innertubeApiKey":"([^"]+)"', html)
        if not api_key_match:
            api_key_match = re.search(r'"apiKey":"([^"]+)"', html)
        api_key = api_key_match.group(1) if api_key_match else None
        
        # Parse initial page JSON
        pattern = r'var ytInitialData\s*=\s*({.*?});'
        match = re.search(pattern, html)
        if not match:
            print("Warning: ytInitialData not found on YouTube page.")
            return []
            
        data = json.loads(match.group(1))
        tabs = data['contents']['twoColumnBrowseResultsRenderer']['tabs']
        videos_tab = None
        for tab in tabs:
            tab_r = tab.get('tabRenderer', {})
            if tab_r.get('title') == 'Videos' or tab_r.get('selected'):
                videos_tab = tab_r
                break
                
        if not videos_tab:
            print("Warning: Videos tab not found in YouTube layout.")
            return []
            
        contents = videos_tab['content']['richGridRenderer']['contents']
        all_videos, continuation_token = parse_videos_from_contents(contents)
        print(f"  Scraped page 0: Extracted {len(all_videos)} videos. Continuation token: {continuation_token is not None}")
        
        # Loop pagination pages using tokens
        page = 1
        while continuation_token and api_key:
            api_url = f"https://www.youtube.com/youtubei/v1/browse?key={api_key}"
            payload = {
                "continuation": continuation_token,
                "context": {
                    "client": {
                        "clientName": "WEB",
                        "clientVersion": "2.20240101.00.00",
                        "originalUrl": "https://www.youtube.com/@PuruWorld/videos",
                        "visitorData": "CgtWRmNYcEkySV9udyjAy4etBg%3D%3D"
                    }
                }
            }
            
            req_data = json.dumps(payload).encode('utf-8')
            api_req = urllib.request.Request(
                api_url,
                data=req_data,
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                }
            )
            
            with urllib.request.urlopen(api_req, timeout=10) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                
            actions = res_data.get('onResponseReceivedActions', [])
            if not actions:
                break
                
            items = actions[0].get('appendContinuationItemsAction', {}).get('continuationItems', [])
            if not items:
                break
                
            videos, continuation_token = parse_videos_from_contents(items)
            all_videos.extend(videos)
            print(f"  Scraped page {page}: Extracted {len(videos)} videos. Next token: {continuation_token is not None}")
            page += 1
            
        print(f"Scrape successful. Ingested total {len(all_videos)} YouTube videos.")
        return all_videos
    except Exception as e:
        print(f"Warning: Failed to fetch videos scraper: {e}. Falling back to default list.")
        return []

# --- SHARED STYLESHEET ---
SHARED_CSS = """/* Modern Variables & Colors */
:root {
  --bg-primary: #f8fafc;
  --bg-secondary: #ffffff;
  --bg-glass: rgba(255, 255, 255, 0.75);
  --text-primary: #0f172a;
  --text-secondary: #475569;
  --text-muted: #64748b;
  --accent-color: #6366f1;
  --accent-gradient: linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%);
  --border-color: #e2e8f0;
  --shadow-sm: 0 1px 3px rgba(0,0,0,0.05);
  --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.05), 0 2px 4px -1px rgba(0,0,0,0.03);
  --shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.05), 0 4px 6px -2px rgba(0,0,0,0.02);
  --card-hover: translateY(-6px);
  --header-height: 70px;
}

[data-theme="dark"] {
  --bg-primary: #0b0f19;
  --bg-secondary: #131c2e;
  --bg-glass: rgba(19, 28, 46, 0.85);
  --text-primary: #f1f5f9;
  --text-secondary: #cbd5e1;
  --text-muted: #94a3b8;
  --accent-color: #8b5cf6;
  --accent-gradient: linear-gradient(135deg, #a78bfa 0%, #8b5cf6 100%);
  --border-color: #1e293b;
  --shadow-sm: 0 1px 3px rgba(0,0,0,0.2);
  --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.25), 0 2px 4px -1px rgba(0,0,0,0.15);
  --shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.4), 0 4px 6px -2px rgba(0,0,0,0.2);
}

/* Global Reset */
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background-color: var(--bg-primary);
  color: var(--text-primary);
  line-height: 1.6;
  transition: background-color 0.3s ease, color 0.3s ease, border-color 0.3s ease;
}

h1, h2, h3, h4, h5, h6 {
  font-family: 'Outfit', sans-serif;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.25;
}

a {
  color: var(--accent-color);
  text-decoration: none;
  transition: color 0.2s ease;
}
a:hover {
  text-decoration: underline;
}

/* Custom scrollbar */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}
::-webkit-scrollbar-track {
  background: var(--bg-primary);
}
::-webkit-scrollbar-thumb {
  background: var(--border-color);
  border-radius: 4px;
}
::-webkit-scrollbar-thumb:hover {
  background: var(--text-muted);
}

/* Base Layout & Header */
.container {
  max-width: 1280px;
  margin: 0 auto;
  padding: 0 16px;
}

header {
  position: sticky;
  top: 0;
  height: var(--header-height);
  background-color: var(--bg-glass);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border-color);
  z-index: 100;
  display: flex;
  align-items: center;
  transition: background-color 0.3s, border-color 0.3s;
}

header .header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.logo {
  font-family: 'Outfit', sans-serif;
  font-size: 1.5rem;
  font-weight: 800;
  background: var(--accent-gradient);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  display: flex;
  align-items: center;
  gap: 8px;
}

.nav-links {
  display: flex;
  align-items: center;
  gap: 20px;
}

.nav-link {
  color: var(--text-secondary);
  font-weight: 500;
  font-size: 0.95rem;
}
.nav-link:hover {
  color: var(--accent-color);
  text-decoration: none;
}

/* Theme Toggle Button */
.theme-toggle-btn {
  background: none;
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  padding: 8px;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  transition: background-color 0.2s, border-color 0.2s, color 0.2s;
}
.theme-toggle-btn:hover {
  background-color: var(--border-color);
  color: var(--text-primary);
}
.theme-toggle-btn svg {
  width: 18px;
  height: 18px;
}
.theme-toggle-btn .sun-icon { display: none; }
[data-theme="dark"] .theme-toggle-btn .sun-icon { display: block; }
[data-theme="dark"] .theme-toggle-btn .moon-icon { display: none; }

/* Scroll Progress Bar */
.scroll-progress-container {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 100%;
  height: 3px;
  background: transparent;
}
.scroll-progress-bar {
  height: 100%;
  width: 0%;
  background: var(--accent-gradient);
  transition: width 0.1s ease-out;
}

/* Hero Section */
.hero {
  position: relative;
  padding: 30px 0 15px;
  text-align: center;
  overflow: hidden;
}
.hero-bg-blobs {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: -1;
  display: flex;
  justify-content: center;
  gap: 100px;
  opacity: 0.12;
}
[data-theme="dark"] .hero-bg-blobs {
  opacity: 0.22;
}
.hero-blob {
  width: 350px;
  height: 350px;
  border-radius: 50%;
  filter: blur(90px);
  animation: float-blob 8s infinite alternate ease-in-out;
}
.hero-blob-1 {
  background: #8b5cf6;
  animation-delay: 0s;
}
.hero-blob-2 {
  background: #3b82f6;
  animation-delay: 3s;
}
@keyframes float-blob {
  0% { transform: translateY(0) scale(1); }
  100% { transform: translateY(-40px) scale(1.15); }
}

.hero h1 {
  font-size: 2.2rem;
  margin-bottom: 12px;
  background: var(--accent-gradient);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  letter-spacing: -0.04em;
  line-height: 1.15;
}
.hero p {
  color: var(--text-secondary);
  font-size: 1rem;
  max-width: 550px;
  margin: 0 auto;
}
.blog-stats {
  display: flex;
  justify-content: center;
  gap: 32px;
  margin-top: 24px;
  color: var(--text-muted);
  font-size: 0.95rem;
  font-weight: 500;
}
.blog-stats span {
  display: flex;
  align-items: center;
  gap: 6px;
}
.blog-stats svg {
  width: 16px;
  height: 16px;
}

/* Tab Switcher Styles */
.tabs-container {
  display: flex;
  justify-content: center;
  gap: 16px;
  margin: -10px auto 40px;
  max-width: 500px;
}
.tab-btn {
  background-color: var(--bg-secondary);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  padding: 12px 24px;
  border-radius: 12px;
  font-family: 'Outfit', sans-serif;
  font-weight: 600;
  font-size: 1rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  justify-content: center;
  transition: all 0.25s ease;
  box-shadow: var(--shadow-sm);
}
.tab-btn svg {
  width: 18px;
  height: 18px;
  fill: currentColor;
}
.tab-btn:hover {
  border-color: var(--accent-color);
  color: var(--accent-color);
}
.tab-btn.active {
  background: var(--accent-gradient);
  border-color: transparent;
  color: white;
  box-shadow: 0 4px 15px rgba(99, 102, 241, 0.25);
}

/* Search & Tags Section */
.search-filter-section {
  margin-bottom: 30px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.search-box-wrapper {
  position: relative;
  width: 100%;
}
.search-box {
  width: 100%;
  padding: 16px 50px 16px 52px;
  font-size: 1.05rem;
  border-radius: 14px;
  border: 1px solid var(--border-color);
  background-color: var(--bg-secondary);
  color: var(--text-primary);
  box-shadow: var(--shadow-sm);
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.search-box:focus {
  border-color: var(--accent-color);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15);
}
.search-icon {
  position: absolute;
  left: 18px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-muted);
  pointer-events: none;
}
.search-icon svg {
  width: 20px;
  height: 20px;
}

.search-box-wrapper .clear-icon {
  position: absolute;
  right: 18px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-muted);
  cursor: pointer;
  font-size: 1.5rem;
  font-weight: bold;
  display: none;
  line-height: 1;
  transition: color 0.2s;
}
.search-box-wrapper .clear-icon:hover {
  color: var(--text-primary);
}

.search-info-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: var(--bg-secondary);
  border: 1px solid var(--border-color);
  padding: 12px 20px;
  border-radius: 12px;
  margin-bottom: 24px;
  font-size: 0.95rem;
  color: var(--text-secondary);
  animation: fadeIn 0.2s ease-in-out;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(5px); }
  to { opacity: 1; transform: translateY(0); }
}
.clear-search-btn-bar {
  background: none;
  border: none;
  color: var(--accent-color);
  font-weight: 600;
  cursor: pointer;
  font-size: 0.9rem;
}
.clear-search-btn-bar:hover {
  text-decoration: underline;
}

.search-highlight {
  background-color: rgba(253, 224, 71, 0.35);
  color: inherit;
  padding: 0 2px;
  border-radius: 4px;
}
[data-theme="dark"] .search-highlight {
  background-color: rgba(234, 179, 8, 0.25);
}

/* Sidebar Navigation Panels */
.blog-page-layout, .videos-page-layout {
  display: grid;
  grid-template-columns: 1fr;
  gap: 30px;
  margin-top: 20px;
}

@media (min-width: 992px) {
  .blog-page-layout, .videos-page-layout {
    grid-template-columns: 250px 1fr;
  }
}

.blog-sidebar, .videos-sidebar {
  display: flex;
  flex-direction: column;
  gap: 8px;
  position: sticky;
  top: calc(var(--header-height) + 20px);
  height: fit-content;
}

.filter-tag, .video-category-btn {
  background-color: var(--bg-secondary);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  padding: 12px 16px;
  border-radius: 10px;
  font-family: 'Outfit', sans-serif;
  font-weight: 600;
  font-size: 0.95rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  transition: all 0.2s ease;
  box-shadow: var(--shadow-sm);
  width: 100%;
  text-align: left;
}

.filter-tag svg, .video-category-btn svg {
  width: 18px;
  height: 18px;
  fill: currentColor;
}

.filter-tag:hover, .video-category-btn:hover {
  border-color: var(--accent-color);
  color: var(--accent-color);
}

.filter-tag.active, .video-category-btn.active {
  background: var(--accent-gradient);
  border-color: transparent;
  color: white;
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.2);
}

.filter-tag .tag-count, .video-category-btn .category-count {
  font-size: 0.75rem;
  background-color: var(--border-color);
  color: var(--text-muted);
  padding: 2px 8px;
  border-radius: 20px;
  transition: all 0.2s;
}

.filter-tag.active .tag-count, .video-category-btn.active .category-count {
  background-color: rgba(255, 255, 255, 0.2);
  color: white;
}

@media (max-width: 991px) {
  .blog-sidebar, .videos-sidebar {
    flex-direction: row;
    overflow-x: auto;
    padding-bottom: 10px;
    position: static;
    scrollbar-width: none;
  }
  .blog-sidebar::-webkit-scrollbar, .videos-sidebar::-webkit-scrollbar {
    display: none;
  }
  .filter-tag, .video-category-btn {
    flex-shrink: 0;
    width: auto;
  }
}

/* Featured Post Layout */
.featured-post-card {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  background-color: var(--bg-secondary);
  border-radius: 20px;
  border: 1px solid var(--border-color);
  overflow: hidden;
  box-shadow: var(--shadow-md);
  margin-bottom: 10px;
  transition: transform 0.3s ease, box-shadow 0.3s ease, border-color 0.3s;
}
.featured-post-card:hover {
  transform: var(--card-hover);
  box-shadow: var(--shadow-lg);
  border-color: var(--accent-color);
}
.featured-image-wrapper {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 380px;
  background: linear-gradient(135deg, #1e1b4b 0%, #311042 100%);
  overflow: hidden;
}
.featured-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.5s ease;
}
.featured-post-card:hover .featured-image {
  transform: scale(1.03);
}
.featured-badge {
  position: absolute;
  top: 20px;
  left: 20px;
  background: var(--accent-gradient);
  color: white;
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  padding: 6px 12px;
  border-radius: 20px;
  letter-spacing: 0.05em;
  box-shadow: 0 4px 10px rgba(99, 102, 241, 0.3);
}
.featured-content {
  padding: 40px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}
.featured-title {
  font-size: 2.25rem;
  margin-bottom: 16px;
  line-height: 1.2;
}
.featured-title a {
  color: var(--text-primary);
}
.featured-title a:hover {
  color: var(--accent-color);
  text-decoration: none;
}
.featured-excerpt {
  color: var(--text-secondary);
  font-size: 1.05rem;
  margin-bottom: 24px;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

@media (max-width: 992px) {
  .featured-post-card {
    grid-template-columns: 1fr;
  }
  .featured-image-wrapper {
    min-height: 250px;
    aspect-ratio: 16/9;
  }
  .featured-content {
    padding: 30px;
  }
  .featured-title {
    font-size: 1.75rem;
  }
}

/* Main Post Grid */
.posts-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(270px, 1fr));
  gap: 20px;
  margin-bottom: 50px;
}

.post-card {
  background-color: var(--bg-secondary);
  border-radius: 16px;
  border: 1px solid var(--border-color);
  overflow: hidden;
  box-shadow: var(--shadow-sm);
  display: flex;
  flex-direction: column;
  height: 100%;
  transition: transform 0.3s ease, box-shadow 0.3s ease, border-color 0.3s;
}
.post-card:hover {
  transform: var(--card-hover);
  box-shadow: var(--shadow-lg);
  border-color: var(--accent-color);
}

/* Performance class for off-screen cards */
.post-card-lazy {
  content-visibility: auto;
  contain-intrinsic-size: auto 450px;
}

.card-image-wrapper {
  position: relative;
  aspect-ratio: 16/9;
  width: 100%;
  background: linear-gradient(135deg, #1e1b4b 0%, #311042 100%);
  overflow: hidden;
}
.card-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.5s ease;
}
.post-card:hover .card-image {
  transform: scale(1.05);
}
.card-image-fallback {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-family: 'Outfit', sans-serif;
  font-weight: 800;
  font-size: 1.5rem;
  background: var(--accent-gradient);
  opacity: 0.85;
}

.card-content {
  padding: 24px;
  display: flex;
  flex-direction: column;
  flex-grow: 1;
}

.card-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 0.8rem;
  color: var(--text-muted);
  margin-bottom: 12px;
}
.card-meta span {
  display: flex;
  align-items: center;
  gap: 4px;
}
.card-meta svg {
  width: 12px;
  height: 12px;
}

.card-title {
  font-size: 1.25rem;
  margin-bottom: 10px;
  line-height: 1.35;
}
.card-title a {
  color: var(--text-primary);
}
.card-title a:hover {
  color: var(--accent-color);
  text-decoration: none;
}

.card-excerpt {
  color: var(--text-secondary);
  font-size: 0.9rem;
  margin-bottom: 20px;
  flex-grow: 1;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.card-tag {
  background-color: var(--bg-primary);
  border: 1px solid var(--border-color);
  color: var(--text-muted);
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 500;
}

/* Play button overlay on Video Card */
.play-overlay {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 54px;
  height: 54px;
  background-color: rgba(99, 102, 241, 0.9);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  opacity: 0;
  transition: opacity 0.3s ease, transform 0.3s ease;
  box-shadow: 0 4px 15px rgba(99, 102, 241, 0.4);
}
.play-overlay svg {
  width: 22px;
  height: 22px;
  margin-left: 3px;
}
.video-card:hover .play-overlay {
  opacity: 1;
  transform: translate(-50%, -50%) scale(1.1);
}

/* Video Subscribe Shortcut */
.video-subscribe-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background-color: #ef4444;
  color: white !important;
  font-family: 'Outfit', sans-serif;
  font-weight: 700;
  font-size: 0.8rem;
  padding: 6px 12px;
  border-radius: 6px;
  text-decoration: none !important;
  transition: background-color 0.2s ease, transform 0.1s ease;
  box-shadow: 0 2px 6px rgba(239, 68, 68, 0.2);
  margin-top: 10px;
  width: fit-content;
}
.video-subscribe-btn:hover {
  background-color: #dc2626;
  transform: translateY(-1px);
}
.video-subscribe-btn:active {
  transform: translateY(0);
}

/* Pagination */
.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 10px;
  margin-top: 60px;
  margin-bottom: 160px;
}
.page-btn {
  background-color: var(--bg-secondary);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  width: 40px;
  height: 40px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-weight: 600;
  transition: all 0.2s;
}
.page-btn:hover:not(:disabled) {
  border-color: var(--accent-color);
  color: var(--accent-color);
}
.page-btn.active {
  background: var(--accent-gradient);
  border-color: transparent;
  color: white;
}
.page-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* Blog Post Detail Page */
.post-layout {
  padding: 40px 0 80px;
}
.back-btn-wrapper {
  margin-bottom: 24px;
}
.back-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--text-secondary);
  font-weight: 500;
  font-size: 0.95rem;
  padding: 8px 16px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background-color: var(--bg-secondary);
  transition: all 0.2s;
}
.back-btn:hover {
  border-color: var(--accent-color);
  color: var(--accent-color);
  text-decoration: none;
}
.back-btn svg {
  width: 16px;
  height: 16px;
}

.post-header {
  margin-bottom: 32px;
  text-align: center;
}
.post-header-title {
  font-size: 2.75rem;
  margin-bottom: 16px;
  letter-spacing: -0.03em;
}
.post-header-meta {
  display: flex;
  justify-content: center;
  align-items: center;
  flex-wrap: wrap;
  gap: 20px;
  color: var(--text-muted);
  font-size: 0.9rem;
  margin-bottom: 16px;
}
.post-header-meta span {
  display: flex;
  align-items: center;
  gap: 6px;
}
.post-header-meta svg {
  width: 16px;
  height: 16px;
}

.post-header-tags {
  display: flex;
  justify-content: center;
  flex-wrap: wrap;
  gap: 8px;
}

.post-hero-image {
  width: 100%;
  max-height: 480px;
  object-fit: cover;
  border-radius: 16px;
  box-shadow: var(--shadow-md);
  margin-bottom: 40px;
}

.post-content-container {
  display: grid;
  grid-template-columns: 1fr;
  gap: 40px;
}

@media (min-width: 992px) {
  .post-content-container {
    grid-template-columns: 3fr 1fr;
  }
}

.post-main-content {
  background-color: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  padding: 40px;
  box-shadow: var(--shadow-sm);
  font-size: 1.1rem;
  line-height: 1.8;
  color: var(--text-primary);
  overflow-wrap: break-word;
}
.post-main-content p {
  margin-bottom: 24px;
}
.post-main-content h2 {
  font-size: 1.75rem;
  margin: 40px 0 20px;
}
.post-main-content h3 {
  font-size: 1.4rem;
  margin: 30px 0 15px;
}
.post-main-content blockquote {
  border-left: 4px solid var(--accent-color);
  padding-left: 20px;
  font-style: italic;
  color: var(--text-secondary);
  margin: 30px 0;
  background-color: var(--bg-primary);
  padding: 20px;
  border-radius: 0 8px 8px 0;
}
.post-main-content ul, .post-main-content ol {
  margin-bottom: 24px;
  padding-left: 24px;
}
.post-main-content li {
  margin-bottom: 8px;
}
.post-main-content img {
  max-width: 100%;
  height: auto;
  border-radius: 12px;
  margin: 20px auto;
  display: block;
}
.post-main-content code {
  background-color: var(--bg-primary);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: monospace;
  font-size: 0.9em;
}
.post-main-content pre {
  background-color: var(--bg-primary);
  padding: 20px;
  border-radius: 8px;
  overflow-x: auto;
  margin-bottom: 24px;
  border: 1px solid var(--border-color);
}
.post-main-content pre code {
  background-color: transparent;
  padding: 0;
  font-size: 0.9em;
}

/* Table of Contents and Sidebar Widgets */
.post-sidebar {
  display: flex;
  flex-direction: column;
  gap: 30px;
}
.sidebar-widget {
  background-color: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  padding: 24px;
  box-shadow: var(--shadow-sm);
}
.sidebar-widget h3 {
  font-size: 1.15rem;
  margin-bottom: 16px;
  border-bottom: 2px solid var(--border-color);
  padding-bottom: 8px;
}

.toc-links {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.toc-link {
  color: var(--text-secondary);
  font-size: 0.9rem;
  font-weight: 500;
  line-height: 1.4;
  padding: 4px 0 4px 12px;
  border-left: 2px solid transparent;
  transition: all 0.2s ease;
  display: block;
}
.toc-link:hover {
  color: var(--accent-color);
  text-decoration: none;
  padding-left: 16px;
}
.toc-link.active {
  color: var(--accent-color);
  border-left-color: var(--accent-color);
  font-weight: 600;
  padding-left: 16px;
}
.toc-link.toc-h3 {
  padding-left: 24px;
  font-size: 0.85rem;
}
.toc-link.toc-h3:hover, .toc-link.toc-h3.active {
  padding-left: 28px;
}

#toc-widget {
  position: sticky;
  top: calc(var(--header-height) + 20px);
  max-height: calc(100vh - var(--header-height) - 60px);
  overflow-y: auto;
}

.share-links {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.share-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  background-color: var(--bg-primary);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  padding: 10px 16px;
  border-radius: 8px;
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}
.share-btn:hover {
  background-color: var(--border-color);
  color: var(--text-primary);
}
.share-btn svg {
  width: 16px;
  height: 16px;
}

/* Figure & Figure Captions styling */
.post-figure {
  margin: 28px 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}
.post-figure a {
  display: block;
  max-width: 100%;
}
.post-figure img {
  max-width: 100%;
  height: auto;
  border-radius: 12px;
  box-shadow: var(--shadow-md);
}
.post-figcaption {
  font-size: 0.85rem;
  color: var(--text-muted);
  font-style: italic;
  text-align: center;
  max-width: 80%;
}

/* Code block wrapper and copy button */
.code-block-wrapper {
  position: relative;
  margin-bottom: 24px;
}
.code-block-wrapper pre {
  margin-bottom: 0;
}
.copy-code-btn {
  position: absolute;
  top: 10px;
  right: 10px;
  background-color: var(--bg-secondary);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  padding: 6px 12px;
  font-size: 0.75rem;
  font-weight: 600;
  border-radius: 6px;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.2s, background-color 0.2s, color 0.2s;
  z-index: 10;
}
.code-block-wrapper:hover .copy-code-btn {
  opacity: 1;
}
.copy-code-btn:hover {
  background-color: var(--border-color);
  color: var(--text-primary);
}
.copy-code-btn.copied {
  background-color: #10b981;
  color: white;
  border-color: #10b981;
}

/* Lightbox Modal */
.lightbox-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background-color: rgba(11, 15, 25, 0.9);
  backdrop-filter: blur(8px);
  z-index: 1000;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.3s ease;
  cursor: zoom-out;
}
.lightbox-overlay.active {
  opacity: 1;
}
.lightbox-img {
  max-width: 90%;
  max-height: 80%;
  border-radius: 12px;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
  transform: scale(0.95);
  transition: transform 0.3s ease;
  cursor: default;
}
.lightbox-overlay.active .lightbox-img {
  transform: scale(1);
}
.lightbox-close {
  position: absolute;
  top: 24px;
  right: 24px;
  color: white;
  background: none;
  border: none;
  font-size: 2.5rem;
  cursor: pointer;
  line-height: 1;
  opacity: 0.7;
  transition: opacity 0.2s;
}
.lightbox-close:hover {
  opacity: 1;
}

/* Embedded Video Player Styles */
.lightbox-video-container {
  width: 85%;
  max-width: 800px;
  aspect-ratio: 16/9;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.55);
  background-color: #000;
  transform: scale(0.95);
  transition: transform 0.3s ease;
}
.lightbox-overlay.active .lightbox-video-container {
  transform: scale(1);
}
.lightbox-video {
  width: 100%;
  height: 100%;
  border: none;
}

@media (max-width: 768px) {
  .lightbox-video-container {
    width: 95%;
  }
}

/* Related Posts Section */
.related-posts-section {
  margin-top: 60px;
  padding-top: 40px;
  border-top: 1px solid var(--border-color);
}
.related-posts-section h2 {
  font-size: 1.75rem;
  margin-bottom: 30px;
}

/* Footer styling */
footer {
  border-top: 1px solid var(--border-color);
  background-color: var(--bg-secondary);
  padding: 40px 0;
  color: var(--text-muted);
  text-align: center;
  font-size: 0.9rem;
}
footer p {
  margin-bottom: 8px;
}

/* Responsive adjust */
@media (max-width: 768px) {
  .hero h1 {
    font-size: 2.5rem;
  }
  .post-header-title {
    font-size: 2rem;
  }
  .post-main-content {
    padding: 24px;
  }
  .tabs-container {
    flex-direction: row;
    gap: 10px;
    padding: 0 10px;
  }
  .tab-btn {
    padding: 10px 16px;
    font-size: 0.9rem;
  }
}

/* Standalone Page Layout */
.page-layout {
  padding: 40px 0 80px;
  max-width: 800px;
  margin: 0 auto;
}
.page-header {
  margin-bottom: 30px;
  text-align: center;
}
.page-title {
  font-family: 'Outfit', sans-serif;
  font-size: 2.5rem;
  font-weight: 800;
  line-height: 1.2;
  margin-bottom: 8px;
  color: var(--text-primary);
}
.page-content {
  font-size: 1.05rem;
  line-height: 1.75;
  color: var(--text-secondary);
}
.page-content p {
  margin-bottom: 1.5rem;
}
.page-content h2 {
  font-family: 'Outfit', sans-serif;
  font-size: 1.6rem;
  font-weight: 700;
  margin: 2.5rem 0 1rem 0;
  color: var(--text-primary);
}
.page-content ul, .page-content ol {
  margin-bottom: 1.5rem;
  padding-left: 20px;
}
.page-content li {
  margin-bottom: 0.5rem;
}

/* Compact Scroll-free view for Interactive Tools/Games */
.game-page.page-layout {
  padding: 10px 0 30px !important;
}
.game-page .page-header {
  margin-bottom: 12px !important;
}
.game-page .page-title {
  font-size: 1.6rem !important;
}

/* Top line search display configurations */
#header-search-container {
  display: none !important;
}
.header-Index #header-search-container {
  display: block !important;
}

/* Premium Glowing Borders */
.post-card, .sidebar-widget, .search-box, .tab-btn, .cell, .mode-btn, .reset-btn, .spin-button {
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
}
.post-card:hover, .sidebar-widget:hover, .search-box:focus, .tab-btn.active, .cell:hover, .mode-btn.active {
  border-color: #8b5cf6 !important;
  box-shadow: 0 0 12px rgba(139, 92, 246, 0.25) !important;
}
[data-theme="dark"] .post-card:hover,
[data-theme="dark"] .sidebar-widget:hover,
[data-theme="dark"] .search-box:focus,
[data-theme="dark"] .tab-btn.active,
[data-theme="dark"] .cell:hover,
[data-theme="dark"] .mode-btn.active {
  box-shadow: 0 0 16px rgba(139, 92, 246, 0.45) !important;
}

@media (max-width: 768px) {
  .page-title {
    font-size: 2rem;
  }
}

/* Mobile Responsive Header, Grid and Games fixes */
@media (max-width: 600px) {
  header .header-content {
    flex-direction: column !important;
    gap: 12px !important;
    align-items: stretch !important;
    padding: 10px 16px !important;
  }
  .logo-search-wrapper {
    flex-direction: column !important;
    gap: 10px !important;
    width: 100% !important;
    align-items: stretch !important;
  }
  .header-search-box-wrapper {
    width: 100% !important;
  }
  .nav-links {
    width: 100% !important;
    justify-content: space-around !important;
    padding-top: 8px !important;
    border-top: 1px solid var(--border-color);
  }
  /* Grid padding adjustments */
  .posts-grid {
    grid-template-columns: 1fr !important;
    gap: 16px !important;
  }
  .post-card {
    border-radius: 12px !important;
  }
  /* Responsive Game Views scales to fit container width without scroll */
  .bottle-container, #tictactoe-game, .coin-container {
    max-width: 100% !important;
    overflow-x: hidden !important;
  }
  #tictactoe-game .board {
    gap: 6px !important;
    padding: 6px !important;
  }
  #tictactoe-game .cell {
    font-size: 2.2rem !important;
  }
}
"""

# --- SHARED JAVASCRIPT ---
SHARED_JS = """// Theme toggling and state synchronization
(function() {
  const savedTheme = localStorage.getItem('theme') || 'light';
  document.documentElement.setAttribute('data-theme', savedTheme);
})();

document.addEventListener('DOMContentLoaded', () => {
  // Theme Toggle Elements
  const themeToggleBtns = document.querySelectorAll('.theme-toggle-btn');
  themeToggleBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const currentTheme = document.documentElement.getAttribute('data-theme');
      const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', newTheme);
      localStorage.setItem('theme', newTheme);
    });
  });

  // Reading Progress Bar
  const progressBar = document.querySelector('.scroll-progress-bar');
  if (progressBar) {
    window.addEventListener('scroll', () => {
      const windowHeight = window.innerHeight;
      const docHeight = document.documentElement.scrollHeight;
      const scrollPos = window.scrollY;
      const scrolled = (scrollPos / (docHeight - windowHeight)) * 100;
      progressBar.style.width = scrolled + '%';
    });
  }

  // Home Page logic (Search, filters, pagination)
  const postsGrid = document.getElementById('posts-grid');
  if (postsGrid) {
    initHomePage();
  }

  // Videos Grid logic (Standalone fallback)
  const videosGrid = document.getElementById('videos-grid');
  if (videosGrid) {
    initVideosPage();
  }

  // Apps Grid logic (Standalone apps page)
  const appsGrid = document.getElementById('apps-grid');
  if (appsGrid) {
    renderAppsGrid();
  }

  // Global search bar enter key listener for redirection
  const searchBox = document.getElementById('search-box');
  if (searchBox) {
    const isHomePage = document.getElementById('posts-grid') !== null;
    const isVideosPage = document.getElementById('videos-grid') !== null;
    
    if (!isHomePage && !isVideosPage) {
      searchBox.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          const query = searchBox.value.trim();
          if (query) {
            const depth = window.relPathDepth || '';
            window.location.href = `${depth}index.html?search=${encodeURIComponent(query)}`;
          }
        }
      });
    }
  }

  // Dynamic View Counter for Article Detail Page
  const titleEl = document.querySelector('.post-header-title');
  if (titleEl) {
    const postTitle = titleEl.textContent;
    let seed = Math.abs(hashCode(postTitle));
    const baseline = Math.floor(80 + seededRandom(seed++) * 1200);
    const realTracked = getRealTrackedLogs();
    let count = baseline;
    const cleanPath = window.location.pathname.replace(/^\./, '');
    realTracked.forEach(log => {
      if (log.path.replace(/^\./, '').includes(cleanPath)) count++;
    });
    const valEl = document.getElementById('view-count-number');
    if (valEl) valEl.textContent = count.toLocaleString();
  }

  // Post Detail Page widgets
  initTableOfContents();
  initImageLightbox();
  initCodeBlockCopyButtons();
});

let allPosts = [];
let filteredPosts = [];
let activeTag = null;
let searchQuery = '';
let currentPage = 1;
const postsPerPage = 12;

let allVideos = [];
let filteredVideos = [];
let currentVideoPage = 1;
const videosPerPage = 12;
let activeVideoCategory = 'All';
let activeTab = 'blog';

// Helper to generate a seeded baseline view count + localStorage visits
function getPostViews(post) {
  let seed = Math.abs(hashCode(post.title || post.url || ''));
  const baseline = Math.floor(80 + seededRandom(seed++) * 1200);
  
  let count = baseline;
  const realTracked = getRealTrackedLogs();
  const itemPath = (post.url || '').replace(/^\./, '');
  if (itemPath !== '') {
    realTracked.forEach(log => {
      if (log.path.replace(/^\./, '').includes(itemPath)) {
        count++;
      }
    });
  }
  return count;
}

function initHomePage() {
  try {
    allPosts = window.postsData || [];
    filteredPosts = [...allPosts];
    
    // Bind search and filter events
    const searchBox = document.getElementById('search-box');
    if (searchBox) {
      searchBox.value = '';
      searchBox.placeholder = 'Search articles...';
      
      // Load search from URL query param if present
      const urlParams = new URLSearchParams(window.location.search);
      const searchParam = urlParams.get('search');
      if (searchParam) {
        searchBox.value = searchParam;
        searchQuery = searchParam.toLowerCase().trim();
      }
      
      searchBox.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase().trim();
        searchQuery = query;
        currentPage = 1;
        applyFilters();

        const clearIcon = document.getElementById('clear-search-icon');
        if (clearIcon) {
          clearIcon.style.display = query ? 'block' : 'none';
        }
      });
      
      if (searchQuery) {
        applyFilters();
      }
    }

    renderTags();
  } catch (error) {
    console.error('Failed to load database:', error);
  }
}

const allApps = [
  {
    title: "Coin Flipper",
    description: "Flip a virtual coin with realistic 3D jump physics. Perfect for quick decision-making and random draws.",
    url: "./p/flip-coin.html",
    icon: "monetization_on",
    tag: "Interactive Tool"
  },
  {
    title: "Tic Tac Toe",
    description: "Play the classic Tic Tac Toe game with a friend or challenge the AI bot.",
    url: "./p/tic-tac-toe.html",
    icon: "grid_on",
    tag: "Casual Game"
  },
  {
    title: "Spin the Bottle",
    description: "An interactive spin-the-bottle party game with smooth CSS rotation physics.",
    url: "./p/spin-bottle.html",
    icon: "cached",
    tag: "Party Game"
  },
  {
    title: "JSON Formatter",
    description: "A developer tool to format, validate, and beautify raw JSON strings easily.",
    url: "./p/json-formatter.html",
    icon: "code",
    tag: "Developer Tool"
  },
  {
    title: "JSON to Apex Converter",
    description: "Convert raw JSON payloads directly into Salesforce Apex class structures.",
    url: "https://json2apex.com",
    icon: "cloud_queue",
    tag: "External Tool",
    isExternal: true
  },
  {
    title: "Python Visualizer",
    description: "Visualize python execution flows and trace memory stack frames in real-time.",
    url: "https://purujeet.github.io/pythonVisualizer/",
    icon: "visibility",
    tag: "External Tool",
    isExternal: true
  },
  {
    title: "SFDX Data Dictionary",
    description: "Convert Salesforce SFDX metadata/object definitions directly into formatted Excel sheets.",
    url: "https://purujeet.github.io/SFMetaToExcel/",
    icon: "table_chart",
    tag: "Salesforce Tool",
    isExternal: true
  },
  {
    title: "Local Barter & Swap",
    description: "Post listings and swap goods or services locally without money on this decentralized barter platform.",
    url: "https://purujeet.github.io/Barter-platform/",
    icon: "swap_horiz",
    tag: "Web App",
    isExternal: true
  },
  {
    title: "Orbit Drop",
    description: "Challenge friends to a multiplayer space-themed physics arcade game powered by Phaser and PeerJS.",
    url: "https://purujeet.github.io/orbit-drop/",
    icon: "rocket_launch",
    tag: "Arcade Game",
    isExternal: true
  },
  {
    title: "Image to PDF Converter",
    description: "Convert multiple image files (JPG, PNG) into a single optimized PDF document in your browser.",
    url: "https://purujeet.github.io/Image2Pdf/",
    icon: "picture_as_pdf",
    tag: "Utility Tool",
    isExternal: true
  },
  {
    title: "Universal Text Converter",
    description: "Convert text formats (XML, CSV, JSON, XLSX, YAML) seamlessly in your browser with automated structure parsing.",
    url: "https://purujeet.github.io/universaltextconverter/",
    icon: "transform",
    tag: "Developer Tool",
    isExternal: true
  }
];

function renderAppsGrid() {
  const grid = document.getElementById('apps-grid');
  if (!grid) return;
  
  grid.innerHTML = allApps.map(app => {
    const targetAttr = app.isExternal ? 'target="_blank"' : '';
    const iconHtml = `
      <div class="card-image-fallback" style="background: var(--accent-gradient); min-height: 160px; display: flex; flex-direction: column; justify-content: center; align-items: center; color: white; border-radius: 12px 12px 0 0; position: relative;">
        <span class="material-icons" style="font-size: 3rem; margin-bottom: 8px;">${app.icon}</span>
        <span class="card-tag" style="background: rgba(255,255,255,0.25); color: white; border-color: transparent; font-family: 'Outfit', sans-serif;">${app.tag}</span>
      </div>
    `;
    
    return `
      <article class="post-card" style="display: flex; flex-direction: column;">
        <div class="card-image-wrapper">
          ${iconHtml}
        </div>
        <div class="card-content" style="display: flex; flex-direction: column; flex-grow: 1; padding: 20px;">
          <h2 class="card-title" style="margin: 0 0 10px 0;"><a href="${app.url}" ${targetAttr} style="color: var(--text-primary); text-decoration: none; font-family: 'Outfit', sans-serif;">${app.title}</a></h2>
          <p class="card-excerpt" style="font-size: 0.9rem; color: var(--text-secondary); line-height: 1.5; margin-bottom: 20px; flex-grow: 1;">${app.description}</p>
          <div style="margin-top: auto; display: flex; justify-content: space-between; align-items: center;">
            <a href="${app.url}" ${targetAttr} class="back-btn" style="padding: 6px 12px; font-size: 0.85rem; border-color: var(--accent-color); color: var(--accent-color); font-weight: 600; text-decoration: none; display: inline-flex; align-items: center; gap: 4px; border-radius: 6px; border: 1px solid var(--accent-color); transition: all 0.2s;">
              Launch ${app.isExternal ? 'Site' : 'App'}
              <svg viewBox="0 0 24 24" style="width: 14px; height: 14px; fill: currentColor;"><path d="M5 13h11.86l-5.43 5.43 1.42 1.42L21.14 12l-8.29-8.29-1.42 1.42 5.43 5.43H5v2z"/></svg>
            </a>
          </div>
        </div>
      </article>
    `;
  }).join('');
}

function switchTab(tab) {
  activeTab = tab;
  
  const tabBlog = document.getElementById('tab-blog');
  const tabApps = document.getElementById('tab-apps');
  const blogPageLayout = document.getElementById('blog-page-layout');
  const appsPageLayout = document.getElementById('apps-page-layout');
  const pagination = document.getElementById('pagination');
  const searchFilterSection = document.getElementById('search-filter-section');
  const searchBox = document.getElementById('search-box');
  
  if (tabBlog) tabBlog.classList.toggle('active', tab === 'blog');
  if (tabApps) tabApps.classList.toggle('active', tab === 'apps');
  
  if (blogPageLayout) blogPageLayout.style.display = tab === 'blog' ? 'grid' : 'none';
  if (appsPageLayout) appsPageLayout.style.display = tab === 'apps' ? 'grid' : 'none';
  
  if (pagination) pagination.style.display = tab === 'blog' ? 'flex' : 'none';
  if (searchFilterSection) searchFilterSection.style.display = tab === 'apps' ? 'none' : 'block';
  
  if (tab === 'blog') {
    if (searchBox) {
      searchBox.placeholder = 'Search articles & videos...';
      searchBox.value = searchQuery;
    }
    applyFilters();
  }
  
  // Update clear icon state
  const clearIcon = document.getElementById('clear-search-icon');
  if (clearIcon && searchBox) {
    clearIcon.style.display = searchBox.value ? 'block' : 'none';
  }
}

function renderTags() {
  const sidebar = document.getElementById('blog-sidebar');
  if (!sidebar) return;

  const tagCounts = {};
  allPosts.forEach(post => {
    if (post.tags) {
      post.tags.forEach(tag => {
        tagCounts[tag] = (tagCounts[tag] || 0) + 1;
      });
    }
  });

  // Sort tags by frequency, show top 10 categories
  const sortedTags = Object.keys(tagCounts).sort((a, b) => tagCounts[b] - tagCounts[a]).slice(0, 10);

  let html = `
    <button class="filter-tag ${activeTag === null ? 'active' : ''}" onclick="selectTag(null)">
      <span style="display:flex; align-items:center; gap:8px;">
        <svg viewBox="0 0 24 24"><path d="M4 6H2v14c0 1.1.9 2 2 2h14v-2H4V6zm16-4H8c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H8V4h12v12z"/></svg>
        All Articles & Videos
      </span>
      <span class="tag-count">${allPosts.length}</span>
    </button>
  `;

  sortedTags.forEach(tag => {
    const count = tagCounts[tag] || 0;
    const isActive = activeTag === tag;
    html += `
      <button class="filter-tag ${isActive ? 'active' : ''}" onclick="selectTag('${tag}')">
        <span style="display:flex; align-items:center; gap:8px;">
          <svg viewBox="0 0 24 24"><path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/></svg>
          ${tag}
        </span>
        <span class="tag-count">${count}</span>
      </button>
    `;
  });

  sidebar.innerHTML = html;
}

function selectTag(tag) {
  activeTag = tag;
  currentPage = 1;
  renderTags();
  applyFilters();
}

function renderVideoCategories() {
  const sidebar = document.getElementById('videos-sidebar');
  if (!sidebar) return;

  const counts = { All: allVideos.length, Gaming: 0, 'Coding & Tech': 0, Others: 0 };
  allVideos.forEach(v => {
    const cat = v.category || 'Others';
    if (counts[cat] !== undefined) {
      counts[cat]++;
    } else {
      counts.Others++;
    }
  });

  const categories = [
    { name: 'All', icon: '<svg viewBox="0 0 24 24"><path d="M4 6H2v14c0 1.1.9 2 2 2h14v-2H4V6zm16-4H8c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H8V4h12v12z"/></svg>' },
    { name: 'Gaming', icon: '<svg viewBox="0 0 24 24"><path d="M21 6H3c-1.1 0-2 .9-2 2v8c0 1.1.9 2 2 2h18c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2zm-10 7H8v3H6v-3H3v-2h3V8h2v3h3v2zm4.5 2c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5zm4-3c-.83 0-1.5-.67-1.5-1.5S19.67 10 20.5 10s1.5.67 1.5 1.5-.67 1.5-1.5 1.5z"/></svg>' },
    { name: 'Coding & Tech', icon: '<svg viewBox="0 0 24 24"><path d="M9.4 16.6L4.8 12l4.6-4.6L8 6l-6 6 6 6 1.4-1.4zm5.2 0l4.6-4.6-4.6-4.6L16 6l6 6-6 6-1.4-1.4z"/></svg>' },
    { name: 'Others', icon: '<svg viewBox="0 0 24 24"><path d="M10 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/></svg>' }
  ];

  sidebar.innerHTML = categories.map(cat => {
    const count = counts[cat.name] || 0;
    const isActive = activeVideoCategory === cat.name;
    return `
      <button class="video-category-btn ${isActive ? 'active' : ''}" onclick="selectVideoCategory('${cat.name}')">
        <span style="display:flex; align-items:center; gap:8px;">
          ${cat.icon}
          ${cat.name}
        </span>
        <span class="category-count">${count}</span>
      </button>
    `;
  }).join('');
}

function selectVideoCategory(cat) {
  activeVideoCategory = cat;
  currentVideoPage = 1;
  renderVideoCategories();
  applyVideoFilters();
}

function applyFilters() {
  if (!searchQuery) {
    filteredPosts = allPosts.filter(post => !activeTag || (post.tags && post.tags.includes(activeTag)));
    renderPostsGrid();
    return;
  }

  const queryWords = searchQuery.toLowerCase().split(/\s+/).filter(w => w.length > 1);
  
  const scoredPosts = allPosts.map(post => {
    let score = 0;
    
    // Check active tag filter
    const matchesTag = !activeTag || (post.tags && post.tags.includes(activeTag));
    if (!matchesTag) return { post, score: -1 };

    const titleLower = post.title.toLowerCase();
    const excerptLower = post.excerpt.toLowerCase();

    // 1. Exact phrase matching
    if (titleLower.includes(searchQuery)) score += 15;
    if (excerptLower.includes(searchQuery)) score += 6;

    // 2. Keyword relevance weights
    if (queryWords.length > 0) {
      queryWords.forEach(word => {
        if (titleLower.includes(word)) score += 6;
        if (excerptLower.includes(word)) score += 2;
        if (post.tags && post.tags.some(t => t.toLowerCase().includes(word))) score += 10;
      });
    } else {
      // Fallback for very short queries
      if (titleLower.includes(searchQuery)) score += 1;
    }

    return { post, score };
  });

  filteredPosts = scoredPosts
    .filter(item => item.score > 0)
    .sort((a, b) => b.score - a.score)
    .map(item => item.post);

  renderPostsGrid();
}

function applyVideoFilters() {
  const videosGrid = document.getElementById('videos-grid');
  const videosPagination = document.getElementById('videos-pagination');
  if (!videosGrid) return;

  const query = document.getElementById('search-box')?.value.toLowerCase().trim() || '';

  if (!query) {
    filteredVideos = allVideos.filter(video => activeVideoCategory === 'All' || video.category === activeVideoCategory);
  } else {
    const queryWords = query.split(/\s+/).filter(w => w.length > 1);
    
    const scoredVideos = allVideos.map(video => {
      let score = 0;
      
      const matchesCategory = activeVideoCategory === 'All' || video.category === activeVideoCategory;
      if (!matchesCategory) return { video, score: -1 };

      const titleLower = video.title.toLowerCase();

      // Exact phrase match
      if (titleLower.includes(query)) score += 12;
      
      if (queryWords.length > 0) {
        queryWords.forEach(word => {
          if (titleLower.includes(word)) score += 6;
        });
      } else {
        if (titleLower.includes(query)) score += 1;
      }

      return { video, score };
    });

    filteredVideos = scoredVideos
      .filter(item => item.score > 0)
      .sort((a, b) => b.score - a.score)
      .map(item => item.video);
  }

  if (filteredVideos.length === 0) {
    videosGrid.innerHTML = '<p style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 40px 0;">No videos found matching your search.</p>';
    updateSearchInfoBar(0);
    if (videosPagination) videosPagination.innerHTML = '';
    return;
  }

  updateSearchInfoBar(filteredVideos.length);

  // Paginated videos grid
  const startIndex = (currentVideoPage - 1) * videosPerPage;
  const endIndex = startIndex + videosPerPage;
  const pageVideos = filteredVideos.slice(startIndex, endIndex);

  videosGrid.innerHTML = pageVideos.map(video => {
    const displayTitle = query ? highlightText(video.title, query) : video.title;

    return `
      <article class="post-card video-card" onclick="playVideo('${video.id}')" style="cursor: pointer;">
        <div class="card-image-wrapper">
          <img class="card-image" src="${video.thumbnail}" alt="${video.title}" width="480" height="360" loading="lazy">
          <div class="play-overlay">
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path d="M8 5v14l11-7z"/>
            </svg>
          </div>
        </div>
        <div class="card-content">
          <div class="card-meta">
            <span>
              <svg fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 14.5v-9l6 4.5-6 4.5z"/></svg>
              ${video.views || '0 views'}
            </span>
            <span>
              <svg fill="currentColor" viewBox="0 0 24 24"><path d="M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 2 22 6.48 22 12s-4.48-10-10-10zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z"/></svg>
              ${video.timeAgo || 'recent'}
            </span>
          </div>
          <h2 class="card-title" style="font-size: 1.15rem; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; margin-bottom: 0;">${displayTitle}</h2>
        </div>
      </article>
    `;
  }).join('');

  renderVideoPagination(filteredVideos.length);
}

function renderVideoPagination(totalCount) {
  const paginationWrapper = document.getElementById('videos-pagination');
  if (!paginationWrapper) return;

  const totalPages = Math.ceil(totalCount / videosPerPage);
  if (totalPages <= 1) {
    paginationWrapper.innerHTML = '';
    return;
  }

  let html = `
    <button class="page-btn" onclick="changeVideoPage(${currentVideoPage - 1})" ${currentVideoPage === 1 ? 'disabled' : ''}>&lt;</button>
  `;

  const startPage = Math.max(1, currentVideoPage - 2);
  const endPage = Math.min(totalPages, currentVideoPage + 2);

  if (startPage > 1) {
    html += `<button class="page-btn" onclick="changeVideoPage(1)">1</button>`;
    if (startPage > 2) html += `<span style="color: var(--text-muted)">...</span>`;
  }

  for (let i = startPage; i <= endPage; i++) {
    html += `
      <button class="page-btn ${i === currentVideoPage ? 'active' : ''}" onclick="changeVideoPage(${i})">${i}</button>
    `;
  }

  if (endPage < totalPages) {
    if (endPage < totalPages - 1) html += `<span style="color: var(--text-muted)">...</span>`;
    html += `<button class="page-btn" onclick="changeVideoPage(${totalPages})">${totalPages}</button>`;
  }

  html += `
    <button class="page-btn" onclick="changeVideoPage(${currentVideoPage + 1})" ${currentVideoPage === totalPages ? 'disabled' : ''}>&gt;</button>
  `;

  paginationWrapper.innerHTML = html;
}

function changeVideoPage(page) {
  currentVideoPage = page;
  applyVideoFilters();
  
  const targetElement = document.getElementById('search-filter-section');
  if (targetElement) {
    window.scrollTo({ top: targetElement.offsetTop - 100, behavior: 'smooth' });
  }
}

function highlightText(text, query) {
  if (!query) return text;
  try {
    const escapedQuery = query.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&');
    const regex = new RegExp(`(${escapedQuery})`, 'gi');
    return text.replace(regex, '<mark class="search-highlight">$1</mark>');
  } catch (e) {
    console.error("Regex highlight error:", e);
    return text;
  }
}

function updateSearchInfoBar(totalResults) {
  const filterSection = document.getElementById('search-filter-section');
  if (!filterSection) return;

  let infoBar = document.getElementById('search-info-bar');
  const query = document.getElementById('search-box')?.value.toLowerCase().trim() || '';
  
  if (activeTab === 'blog') {
    if (!searchQuery && !activeTag) {
      if (infoBar) infoBar.remove();
      return;
    }
  } else {
    if (!query && activeVideoCategory === 'All') {
      if (infoBar) infoBar.remove();
      return;
    }
  }

  if (!infoBar) {
    infoBar = document.createElement('div');
    infoBar.id = 'search-info-bar';
    infoBar.className = 'search-info-bar';
    filterSection.insertAdjacentElement('afterend', infoBar);
  }

  let text = `Found <strong>${totalResults}</strong> result${totalResults === 1 ? '' : 's'}`;
  if (activeTab === 'blog') {
    if (searchQuery) {
      text += ` matching "<strong>${escapeHtml(searchQuery)}</strong>"`;
    }
    if (activeTag) {
      text += ` in tag "<strong>${escapeHtml(activeTag)}</strong>"`;
    }
  } else {
    if (query) {
      text += ` matching "<strong>${escapeHtml(query)}</strong>"`;
    }
    if (activeVideoCategory !== 'All') {
      text += ` in category "<strong>${escapeHtml(activeVideoCategory)}</strong>"`;
    }
  }

  infoBar.innerHTML = `
    <span>${text}</span>
    <button class="clear-search-btn-bar" onclick="resetFilters()">Reset Filters</button>
  `;
}

function escapeHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

function resetFilters() {
  const searchBox = document.getElementById('search-box');
  if (searchBox) searchBox.value = '';
  
  const clearIcon = document.getElementById('clear-search-icon');
  if (clearIcon) clearIcon.style.display = 'none';

  if (activeTab === 'blog') {
    searchQuery = '';
    activeTag = null;
    currentPage = 1;
    renderTags();
    applyFilters();
  } else {
    activeVideoCategory = 'All';
    currentVideoPage = 1;
    renderVideoCategories();
    applyVideoFilters();
  }
}

function renderPostsGrid() {
  const postsGrid = document.getElementById('posts-grid');
  if (!postsGrid) return;

  if (filteredPosts.length === 0) {
    postsGrid.innerHTML = '<p style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 40px 0;">No posts found matching your search.</p>';
    renderPagination(0);
    updateSearchInfoBar(0);
    return;
  }

  updateSearchInfoBar(filteredPosts.length);

  let postsHtml = '';
  const isInitialState = (currentPage === 1 && !activeTag && !searchQuery);

  if (isInitialState) {
    const featuredPost = filteredPosts[0];
    const coverImageHtml = featuredPost.coverImage 
      ? `<img class="featured-image" src="${featuredPost.coverImage}" alt="${featuredPost.title}" width="800" height="450" fetchpriority="high" loading="eager">`
      : `<div class="card-image-fallback">${featuredPost.title.slice(0, 2).toUpperCase()}</div>`;
    
    const tagsHtml = featuredPost.tags 
      ? featuredPost.tags.slice(0, 3).map(tag => `<span class="card-tag">${tag}</span>`).join('')
      : '';

    postsHtml += `
      <article class="featured-post-card">
        <div class="featured-image-wrapper">
          ${coverImageHtml}
          <div class="featured-badge">Latest Article</div>
        </div>
        <div class="featured-content">
          <div class="card-meta">
            <span>
              <svg fill="currentColor" viewBox="0 0 24 24"><path d="M19 4h-1V2h-2v2H8V2H6v2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 16H5V10h14v10zm0-12H5V6h14v2z"/></svg>
              ${featuredPost.formattedDate}
            </span>
            <span>
              <svg fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z"/></svg>
              ${featuredPost.readTime} min read
            </span>
            <span>
              <svg fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" style="width:14px; height:14px; vertical-align:middle; margin-right:4px;"><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path><path stroke-linecap="round" stroke-linejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path></svg>
              ${getPostViews(featuredPost).toLocaleString()} views
            </span>
          </div>
          <h2 class="featured-title"><a href=".${featuredPost.url}">${featuredPost.title}</a></h2>
          <p class="featured-excerpt">${featuredPost.excerpt}</p>
          <div class="card-tags">
            ${tagsHtml}
          </div>
        </div>
      </article>
    `;
  }

  let displayPosts = isInitialState ? filteredPosts.slice(1) : filteredPosts;

  const startIndex = (currentPage - 1) * postsPerPage;
  const endIndex = startIndex + postsPerPage;
  const pagePosts = displayPosts.slice(startIndex, endIndex);

  postsHtml += pagePosts.map((post, index) => {
    const displayTitle = searchQuery ? highlightText(post.title, searchQuery) : post.title;
    const displayExcerpt = searchQuery ? highlightText(post.excerpt, searchQuery) : post.excerpt;

    const isBelowFold = index > 1 || currentPage > 1;
    const lazyClass = isBelowFold ? 'post-card-lazy' : '';
    const loadingAttr = isBelowFold ? 'lazy' : 'eager';

    const coverImageHtml = post.coverImage 
      ? `<img class="card-image" src="${post.coverImage}" alt="${post.title}" width="400" height="250" loading="${loadingAttr}" decoding="async">`
      : `<div class="card-image-fallback">${post.title.slice(0, 2).toUpperCase()}</div>`;

    const tagsHtml = post.tags 
      ? post.tags.slice(0, 3).map(tag => `<span class="card-tag">${tag}</span>`).join('')
      : '';

    if (post.isVideo) {
      return `
        <article class="post-card video-card ${lazyClass}" onclick="playVideo('${post.id}')" style="cursor: pointer;">
          <div class="card-image-wrapper">
            <img class="card-image" src="${post.coverImage}" alt="${post.title}" width="400" height="250" loading="${loadingAttr}">
            <div class="play-overlay">
              <svg viewBox="0 0 24 24" fill="currentColor">
                <path d="M8 5v14l11-7z"/>
              </svg>
            </div>
          </div>
          <div class="card-content" style="display: flex; flex-direction: column; height: 100%;">
            <div class="card-meta">
              <span>
                <svg fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 14.5v-9l6 4.5-6 4.5z"/></svg>
                ${post.views || '0 views'}
              </span>
              <span>
                <svg fill="currentColor" viewBox="0 0 24 24"><path d="M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 2 22 6.48 22 12s-4.48-10-10-10zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z"/></svg>
                ${post.timeAgo || 'recent'}
              </span>
            </div>
            <h2 class="card-title" style="font-size: 1.15rem; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; margin-bottom: 8px;">${displayTitle}</h2>
            <div class="card-tags" style="margin-top: auto;">
              ${tagsHtml}
            </div>
          </div>
        </article>
      `;
    }

    return `
      <article class="post-card ${lazyClass}">
        <div class="card-image-wrapper">
          ${coverImageHtml}
        </div>
        <div class="card-content">
          <div class="card-meta">
            <span>
              <svg fill="currentColor" viewBox="0 0 24 24"><path d="M19 4h-1V2h-2v2H8V2H6v2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 16H5V10h14v10zm0-12H5V6h14v2z"/></svg>
              ${post.formattedDate}
            </span>
            <span>
              <svg fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z"/></svg>
              ${post.readTime} min read
            </span>
            <span>
              <svg fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" style="width:14px; height:14px; vertical-align:middle; margin-right:4px;"><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path><path stroke-linecap="round" stroke-linejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path></svg>
              ${getPostViews(post).toLocaleString()} views
            </span>
          </div>
          <h2 class="card-title"><a href=".${post.url}">${displayTitle}</a></h2>
          <p class="card-excerpt">${displayExcerpt}</p>
          <div class="card-tags">
            ${tagsHtml}
          </div>
        </div>
      </article>
    `;
  }).join('');

  postsGrid.innerHTML = postsHtml;
  renderPagination(filteredPosts.length);
}

function renderPagination(totalCount) {
  const paginationWrapper = document.getElementById('pagination');
  if (!paginationWrapper) return;

  const totalPages = Math.ceil(totalCount / postsPerPage);
  if (totalPages <= 1) {
    paginationWrapper.innerHTML = '';
    return;
  }

  let html = `
    <button class="page-btn" onclick="changePage(${currentPage - 1})" ${currentPage === 1 ? 'disabled' : ''}>&lt;</button>
  `;

  const startPage = Math.max(1, currentPage - 2);
  const endPage = Math.min(totalPages, currentPage + 2);

  if (startPage > 1) {
    html += `<button class="page-btn" onclick="changePage(1)">1</button>`;
    if (startPage > 2) html += `<span style="color: var(--text-muted)">...</span>`;
  }

  for (let i = startPage; i <= endPage; i++) {
    html += `
      <button class="page-btn ${i === currentPage ? 'active' : ''}" onclick="changePage(${i})">${i}</button>
    `;
  }

  if (endPage < totalPages) {
    if (endPage < totalPages - 1) html += `<span style="color: var(--text-muted)">...</span>`;
    html += `<button class="page-btn" onclick="changePage(${totalPages})">${totalPages}</button>`;
  }

  html += `
    <button class="page-btn" onclick="changePage(${currentPage + 1})" ${currentPage === totalPages ? 'disabled' : ''}>&gt;</button>
  `;

  paginationWrapper.innerHTML = html;
}

function changePage(page) {
  currentPage = page;
  renderPostsGrid();
  
  const targetElement = document.getElementById('search-filter-section');
  if (targetElement) {
    window.scrollTo({ top: targetElement.offsetTop - 100, behavior: 'smooth' });
  }
}

function sharePost(platform, title) {
  const fullUrl = encodeURIComponent(window.location.href);
  const encodedTitle = encodeURIComponent(title);
  let shareUrl = '';
  
  if (platform === 'twitter') {
    shareUrl = `https://twitter.com/intent/tweet?text=${encodedTitle}&url=${fullUrl}`;
  } else if (platform === 'facebook') {
    shareUrl = `https://www.facebook.com/sharer/sharer.php?u=${fullUrl}`;
  } else if (platform === 'linkedin') {
    shareUrl = `https://www.linkedin.com/sharing/share-offsite/?url=${fullUrl}`;
  } else if (platform === 'copy') {
    navigator.clipboard.writeText(window.location.href);
    alert('Link copied to clipboard!');
    return;
  }
  
  if (shareUrl) {
    window.open(shareUrl, '_blank', 'width=600,height=400');
  }
}

// Table of Contents Widget logic
function initTableOfContents() {
  const postContent = document.querySelector('.post-main-content');
  const tocWidget = document.getElementById('toc-widget');
  const tocLinks = document.getElementById('toc-links');
  
  if (!postContent || !tocWidget || !tocLinks) return;

  const headings = postContent.querySelectorAll('h2, h3');
  if (headings.length < 2) {
    tocWidget.style.display = 'none';
    
    const container = document.querySelector('.post-content-container');
    if (container && window.innerWidth >= 992) {
      container.style.gridTemplateColumns = '1fr';
    }
    return;
  }

  tocWidget.style.display = 'block';
  tocLinks.innerHTML = '';

  const headingElements = [];

  headings.forEach((heading, index) => {
    if (!heading.id) {
      heading.id = heading.textContent.toLowerCase()
        .replace(/[^a-z0-9\s-]/g, '')
        .replace(/\s+/g, '-');
      if (!heading.id) heading.id = 'heading-' + index;
    }

    const link = document.createElement('a');
    link.href = '#' + heading.id;
    link.textContent = heading.textContent;
    link.className = 'toc-link';
    
    if (heading.tagName.toLowerCase() === 'h3') {
      link.classList.add('toc-h3');
    }

    tocLinks.appendChild(link);
    headingElements.push({ id: heading.id, el: heading, linkEl: link });
  });

  const observerOptions = {
    root: null,
    rootMargin: '-80px 0px -60% 0px',
    threshold: 0
  };

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        const headingId = entry.target.id;
        headingElements.forEach((item) => {
          if (item.id === headingId) {
            headingElements.forEach(i => i.linkEl.classList.remove('active'));
            item.linkEl.classList.add('active');
            
            tocWidget.scrollTo({
              top: item.linkEl.offsetTop - 50,
              behavior: 'smooth'
            });
          }
        });
      }
    });
  }, observerOptions);

  headings.forEach(heading => observer.observe(heading));
}

// Lightbox Modal logic
function initImageLightbox() {
  const postContent = document.querySelector('.post-main-content');
  if (!postContent) return;

  const postImages = postContent.querySelectorAll('.post-image, img');
  if (postImages.length === 0) return;

  let lightbox = document.getElementById('lightbox-overlay');
  if (!lightbox) {
    lightbox = document.createElement('div');
    lightbox.id = 'lightbox-overlay';
    lightbox.className = 'lightbox-overlay';
    lightbox.style.display = 'none';
    lightbox.innerHTML = `
      <button class="lightbox-close" aria-label="Close lightbox">&times;</button>
      <img class="lightbox-img" src="" alt="Zoomed view">
    `;
    document.body.appendChild(lightbox);
  }

  const lightboxImg = lightbox.querySelector('.lightbox-img');
  const closeBtn = lightbox.querySelector('.lightbox-close');

  postImages.forEach(img => {
    img.style.cursor = 'zoom-in';
    img.addEventListener('click', (e) => {
      if (img.naturalWidth < 120 && img.naturalWidth !== 0) return;
      
      e.preventDefault();
      
      let mediaContainer = lightbox.querySelector('.lightbox-video-container');
      if (mediaContainer) {
        mediaContainer.remove();
      }
      
      let imgTag = lightbox.querySelector('.lightbox-img');
      if (!imgTag) {
        imgTag = document.createElement('img');
        imgTag.className = 'lightbox-img';
        lightbox.appendChild(imgTag);
      }
      
      imgTag.src = img.src;
      imgTag.alt = img.alt || 'Zoomed view';
      lightbox.style.display = 'flex';
      
      setTimeout(() => {
        lightbox.classList.add('active');
      }, 10);
      document.body.style.overflow = 'hidden';
    });
  });

  const closeLightbox = () => {
    lightbox.classList.remove('active');
    setTimeout(() => {
      lightbox.style.display = 'none';
    }, 300);
    document.body.style.overflow = '';
  };

  lightbox.addEventListener('click', (e) => {
    if (e.target === lightbox || e.target === closeBtn) {
      closeLightbox();
    }
  });

  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && lightbox.classList.contains('active')) {
      closeLightbox();
    }
  });
}

// Code Copy Buttons logic
function initCodeBlockCopyButtons() {
  const preBlocks = document.querySelectorAll('.post-main-content pre');
  preBlocks.forEach(pre => {
    if (pre.parentElement.classList.contains('code-block-wrapper')) return;

    const wrapper = document.createElement('div');
    wrapper.className = 'code-block-wrapper';
    pre.parentNode.insertBefore(wrapper, pre);
    wrapper.appendChild(pre);

    const btn = document.createElement('button');
    btn.className = 'copy-code-btn';
    btn.textContent = 'Copy';
    btn.type = 'button';
    wrapper.appendChild(btn);

    btn.addEventListener('click', () => {
      const code = pre.querySelector('code') || pre;
      const text = code.innerText || code.textContent;

      navigator.clipboard.writeText(text).then(() => {
        btn.textContent = 'Copied!';
        btn.classList.add('copied');
        setTimeout(() => {
          btn.textContent = 'Copy';
          btn.classList.remove('copied');
        }, 2000);
      }).catch(err => {
        console.error('Failed to copy code: ', err);
        btn.textContent = 'Error';
      });
    });
  });
}

// Videos Page Initialization (Standalone page loader)
function initVideosPage() {
  try {
    allVideos = window.videosData || [];
    filteredVideos = [...allVideos];
    
    const searchBox = document.getElementById('search-box');
    if (searchBox) {
      searchBox.value = '';
      searchBox.addEventListener('input', (e) => {
        currentVideoPage = 1;
        applyVideoFilters();
        
        const clearIcon = document.getElementById('clear-search-icon');
        if (clearIcon) {
          const query = e.target.value.toLowerCase().trim();
          clearIcon.style.display = query ? 'block' : 'none';
        }
      });
    }
    
    renderVideoCategories();
    applyVideoFilters();
  } catch (error) {
    console.error('Failed to load videos database:', error);
  }
}

function playVideo(videoId) {
  let lightbox = document.getElementById('lightbox-overlay');
  if (!lightbox) {
    lightbox = document.createElement('div');
    lightbox.id = 'lightbox-overlay';
    lightbox.className = 'lightbox-overlay';
    lightbox.style.display = 'none';
    document.body.appendChild(lightbox);
  }

  const videoObj = allVideos.find(v => v.id === videoId);
  const videoTitle = videoObj ? videoObj.title : 'Watch Video';

  // Modal with autoplay, fullscreen capabilities
  lightbox.innerHTML = `
    <button class="lightbox-close" aria-label="Close lightbox">&times;</button>
    <div class="lightbox-video-container">
      <iframe class="lightbox-video" src="https://www.youtube.com/embed/${videoId}?autoplay=1&fs=1" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen webkitallowfullscreen mozallowfullscreen allow="autoplay; fullscreen"></iframe>
    </div>
    <div class="lightbox-video-footer" style="margin-top: 15px; display: flex; justify-content: center; align-items: center; width: 85%; max-width: 800px; color: white;">
      <span id="lightbox-video-title" style="font-family:'Outfit', sans-serif; font-size:1.15rem; font-weight:600; text-overflow:ellipsis; overflow:hidden; white-space:nowrap; width:100%; text-align:center;">${videoTitle}</span>
    </div>
  `;

  const iframe = lightbox.querySelector('.lightbox-video');
  const closeBtn = lightbox.querySelector('.lightbox-close');
  lightbox.style.display = 'flex';
  
  setTimeout(() => {
    lightbox.classList.add('active');
  }, 10);
  document.body.style.overflow = 'hidden';

  const closeVideo = () => {
    lightbox.classList.remove('active');
    if (iframe) iframe.src = ''; // Halt video playback
    setTimeout(() => {
      lightbox.style.display = 'none';
      lightbox.innerHTML = '';
    }, 300);
    document.body.style.overflow = '';
  };

  lightbox.onclick = (e) => {
    if (e.target === lightbox || e.target === closeBtn) {
      closeVideo();
    }
  };

  const handleKey = (e) => {
    if (e.key === 'Escape' && lightbox.classList.contains('active')) {
      closeVideo();
      window.removeEventListener('keydown', handleKey);
    }
  };
  window.addEventListener('keydown', handleKey);
}

// Expose handlers globally
window.selectTag = selectTag;
window.changePage = changePage;
window.sharePost = sharePost;
window.resetFilters = resetFilters;
window.playVideo = playVideo;
window.switchTab = switchTab;
window.selectVideoCategory = selectVideoCategory;
window.changeVideoPage = changeVideoPage;
window.renderAppsGrid = renderAppsGrid;

// Floating AI Search Agent Chat Widget
function initAIAgentWidget() {
  const style = document.createElement('style');
  style.textContent = `
    @keyframes slideUpWidget {
      from { transform: translateY(20px); opacity: 0; }
      to { transform: translateY(0); opacity: 1; }
    }
    .widget-glowing-btn:hover {
      box-shadow: 0 0 20px rgba(139, 92, 246, 0.6) !important;
      transform: scale(1.05);
    }
  `;
  document.head.appendChild(style);

  const widget = document.createElement('div');
  widget.id = 'ai-agent-widget';
  widget.style.cssText = 'position: fixed; bottom: 24px; right: 24px; z-index: 10000; font-family: "Outfit", sans-serif;';
  
  widget.innerHTML = `
    <!-- Floating Circular Button -->
    <button id="ai-agent-btn" class="widget-glowing-btn" style="width: 56px; height: 56px; border-radius: 50%; background: var(--accent-gradient); border: none; color: white; display: flex; align-items: center; justify-content: center; cursor: pointer; box-shadow: 0 4px 16px rgba(139, 92, 246, 0.4); transition: all 0.2s;">
      <span class="material-icons" style="font-size: 28px;">smart_toy</span>
    </button>
    <!-- Chat Window -->
    <div id="ai-agent-panel" style="display: none; position: absolute; bottom: 70px; right: 0; width: 345px; height: 440px; background: var(--bg-secondary); border: 1px solid var(--border-color); border-radius: 16px; box-shadow: 0 8px 32px rgba(0,0,0,0.2); flex-direction: column; overflow: hidden; animation: slideUpWidget 0.25s cubic-bezier(0.4, 0, 0.2, 1); box-sizing: border-box;">
      <!-- Header -->
      <div style="background: var(--accent-gradient); color: white; padding: 16px; display: flex; align-items: center; gap: 10px; font-weight: bold; border-bottom: 1px solid var(--border-color);">
        <span class="material-icons" style="font-size: 20px;">smart_toy</span>
        <span>puruworld AI Agent</span>
        <button id="ai-agent-close" style="background: none; border: none; color: white; margin-left: auto; cursor: pointer; display: flex; align-items: center;">
          <span class="material-icons" style="font-size: 20px;">close</span>
        </button>
      </div>
      <!-- Chat Area -->
      <div id="ai-agent-messages" style="flex-grow: 1; padding: 16px; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; font-size: 0.88rem; line-height: 1.4; color: var(--text-primary); max-height: 310px;">
        <div style="background: rgba(139, 92, 246, 0.1); border: 1px solid rgba(139, 92, 246, 0.15); padding: 10px 12px; border-radius: 12px 12px 12px 0; align-self: flex-start; max-width: 85%;">
          Hello! I'm your AI Agent. Ask me to find articles, gaming tools, or search any topics on puruworld!
        </div>
      </div>
      <!-- Input Area -->
      <div style="padding: 12px; border-top: 1px solid var(--border-color); display: flex; gap: 8px; align-items: center; background: var(--bg-secondary);">
        <input type="text" id="ai-agent-input" placeholder="Search or ask me anything..." style="flex-grow: 1; padding: 8px 14px; border-radius: 20px; border: 1px solid var(--border-color); background: var(--bg-primary); color: var(--text-primary); outline: none; font-size: 0.88rem; box-shadow: inset 0 1px 2px rgba(0,0,0,0.05);">
        <button id="ai-agent-send" style="background: var(--accent-gradient); border: none; color: white; border-radius: 50%; width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: all 0.2s;">
          <span class="material-icons" style="font-size: 18px;">send</span>
        </button>
      </div>
    </div>
  `;
  document.body.appendChild(widget);

  const btn = widget.querySelector('#ai-agent-btn');
  const panel = widget.querySelector('#ai-agent-panel');
  const closeBtn = widget.querySelector('#ai-agent-close');
  const input = widget.querySelector('#ai-agent-input');
  const sendBtn = widget.querySelector('#ai-agent-send');
  const messagesContainer = widget.querySelector('#ai-agent-messages');

  btn.onclick = () => {
    const isHidden = panel.style.display === 'none';
    panel.style.display = isHidden ? 'flex' : 'none';
    if (isHidden) input.focus();
  };

  closeBtn.onclick = () => {
    panel.style.display = 'none';
  };

  const addMessage = (text, isUser = false) => {
    const msg = document.createElement('div');
    if (isUser) {
      msg.style.cssText = 'background: var(--accent-gradient); color: white; padding: 10px 12px; border-radius: 12px 12px 0 12px; align-self: flex-end; max-width: 85%; word-break: break-word;';
    } else {
      msg.style.cssText = 'background: rgba(139, 92, 246, 0.08); border: 1px solid var(--border-color); padding: 10px 12px; border-radius: 12px 12px 12px 0; align-self: flex-start; max-width: 85%; word-break: break-word;';
    }
    msg.innerHTML = text;
    messagesContainer.appendChild(msg);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  };

  const handleSearch = (query) => {
    addMessage(query, true);
    input.value = '';
    
    setTimeout(() => {
      const q = query.toLowerCase().trim();
      const queryWords = q.split(/\s+/).filter(w => w.length > 1);
      if (queryWords.length === 0 && q.length > 0) queryWords.push(q);

      let matchedPosts = [];
      if (window.postsData) {
        matchedPosts = window.postsData.map(post => {
          let score = 0;
          const titleLower = post.title.toLowerCase();
          const excerptLower = post.excerpt ? post.excerpt.toLowerCase() : '';
          
          if (titleLower.includes(q)) score += 10;
          queryWords.forEach(word => {
            if (titleLower.includes(word)) score += 5;
            if (excerptLower.includes(word)) score += 2;
          });
          return { post, score };
        }).filter(item => item.score > 0).sort((a,b) => b.score - a.score).slice(0, 3);
      }

      let matchedVideos = [];
      if (window.videosData) {
        matchedVideos = window.videosData.map(video => {
          let score = 0;
          const titleLower = video.title.toLowerCase();
          if (titleLower.includes(q)) score += 10;
          queryWords.forEach(word => {
            if (titleLower.includes(word)) score += 5;
          });
          return { video, score };
        }).filter(item => item.score > 0).sort((a,b) => b.score - a.score).slice(0, 3);
      }

      let replyHtml = "";
      if (matchedPosts.length === 0 && matchedVideos.length === 0) {
        replyHtml = "I searched puruworld but couldn't find matches for '" + query + "'. Try asking about 'python', 'salesforce', 'games', or 'tax'!";
      } else {
        replyHtml = "I found these relevant resources for you:<ul style='margin: 8px 0 0 16px; padding: 0;'>";
        matchedPosts.forEach(item => {
          const prefix = window.location.pathname.includes('/p/') ? '../' : './';
          replyHtml += "<li style='margin-bottom: 6px;'><a href='" + prefix + item.post.url.replace(/^\//, '') + "' style='color: #8b5cf6; text-decoration: none; font-weight: 600;'>[Article] " + item.post.title + "</a></li>";
        });
        matchedVideos.forEach(item => {
          const prefix = window.location.pathname.includes('/p/') ? '../' : './';
          replyHtml += "<li style='margin-bottom: 6px;'><a href='" + prefix + "p/videos.html?search=" + encodeURIComponent(item.video.title) + "' style='color: #6366f1; text-decoration: none; font-weight: 600;'>[Video] " + item.video.title + "</a></li>";
        });
        replyHtml += "</ul>";
      }
      addMessage(replyHtml);
    }, 400);
  };

  sendBtn.onclick = () => {
    const val = input.value.trim();
    if (val) handleSearch(val);
  };

  input.onkeydown = (e) => {
    if (e.key === 'Enter') {
      const val = input.value.trim();
      if (val) handleSearch(val);
    }
  };
}

// Ingest script initialization
document.addEventListener('DOMContentLoaded', () => {
  initAIAgentWidget();
});

// Analytics tracking script
(function() {
  const currentPath = window.location.pathname;
  const currentTitle = document.title;
  const referrer = document.referrer || 'Direct';
  
  let country = sessionStorage.getItem('puruworld_geo_country') || 'Unknown';
  
  const logVisit = (cntry) => {
    let logs = [];
    try {
      logs = JSON.parse(localStorage.getItem('puruworld_analytics') || '[]');
    } catch(e) {}
    
    // Classify referrer
    let source = 'Direct';
    const refLower = referrer.toLowerCase();
    if (refLower.includes('google.') || refLower.includes('bing.') || refLower.includes('yahoo.') || refLower.includes('duckduckgo.')) {
      source = 'Search Engine';
    } else if (refLower.includes('facebook.') || refLower.includes('t.co') || refLower.includes('twitter.') || refLower.includes('linkedin.') || refLower.includes('instagram.') || refLower.includes('reddit.')) {
      source = 'Social Media';
    } else if (referrer !== 'Direct' && !refLower.includes(window.location.hostname)) {
      source = 'Referral';
    }
    
    const visit = {
      path: currentPath,
      title: currentTitle,
      source: source,
      country: cntry,
      timestamp: Date.now(),
      timeSpent: 0,
      bounced: true
    };
    
    logs.push(visit);
    if (logs.length > 5000) logs.shift();
    localStorage.setItem('puruworld_analytics', JSON.stringify(logs));
    
    let startTime = Date.now();
    window.addEventListener('beforeunload', () => {
      let timeSpent = Math.round((Date.now() - startTime) / 1000);
      try {
        let currentLogs = JSON.parse(localStorage.getItem('puruworld_analytics') || '[]');
        if (currentLogs.length > 0) {
          let latest = currentLogs.find(l => l.path === currentPath && l.timestamp === visit.timestamp);
          if (latest) {
            latest.timeSpent = timeSpent;
            latest.bounced = timeSpent < 15;
            localStorage.setItem('puruworld_analytics', JSON.stringify(currentLogs));
          }
        }
      } catch(e) {}
    });
  };

  if (country === 'Unknown') {
    fetch('https://ipapi.co/json/')
      .then(r => r.json())
      .then(data => {
        country = data.country_name || 'United States';
        sessionStorage.setItem('puruworld_geo_country', country);
        logVisit(country);
      })
      .catch(() => {
        country = 'United States';
        sessionStorage.setItem('puruworld_geo_country', country);
        logVisit(country);
      });
  } else {
    logVisit(country);
  }
})();
"""

def load_template(name):
  path = os.path.join('templates', name)
  with open(path, 'r', encoding='utf-8') as f:
    return f.read()

def get_head(title, description, rel_path, filename=None, additional_scripts=""):
  head_tmpl = load_template('head.html')
  canonical_tag = ''
  if filename:
    clean_fn = filename.lstrip('/')
    canonical_tag = f'<link rel="canonical" href="https://purujeet.github.io/puruworld/{clean_fn}">'
  else:
    canonical_tag = '<link rel="canonical" href="https://purujeet.github.io/puruworld/">'
  
  return head_tmpl.replace('{{TITLE}}', title)\
                  .replace('{{DESCRIPTION}}', description)\
                  .replace('{{REL_PATH}}', rel_path)\
                  .replace('{{ADDITIONAL_SCRIPTS}}', canonical_tag + "\n" + additional_scripts)

def get_header(rel_path, has_progress=False, id_val="Index"):
  header_tmpl = load_template('header.html')
  progress_bar = '<div class="scroll-progress-container"><div class="scroll-progress-bar"></div></div>' if has_progress else ''
  return header_tmpl.replace('{{REL_PATH}}', rel_path)\
                    .replace('{{SCROLL_PROGRESS}}', progress_bar)\
                    .replace('{{ID}}', id_val)

def get_footer(rel_path):
  return load_template('footer.html').replace('{{REL_PATH}}', rel_path)

def make_post_html(post_title, post_date, post_tags, post_content, read_time, cover_image, rel_path, filename, related_posts_html):
  post_tmpl = load_template('post.html')
  
  head = get_head(f"{post_title} - puru world official", clean_excerpt(post_content, 150), rel_path, filename)
  header = get_header(rel_path, has_progress=True, id_val="Detail")
  footer = get_footer(rel_path)
  
  header_tags_html = "".join([f'<span class="filter-tag" style="cursor:default">{t}</span>' for t in post_tags])
  cover_image_html = f'<img class="post-hero-image" src="{cover_image}" alt="{post_title}" width="1200" height="630" fetchpriority="high" loading="eager" decoding="async">' if cover_image else ''
  
  title_escaped = post_title.replace("'", "\\'")
  
  post_html = post_tmpl.replace('{{HEAD}}', head)\
                       .replace('{{HEADER}}', header)\
                       .replace('{{FOOTER}}', footer)\
                       .replace('{{REL_PATH}}', rel_path)\
                       .replace('{{POST_TITLE}}', post_title)\
                       .replace('{{POST_TITLE_JS}}', title_escaped)\
                       .replace('{{POST_DATE}}', post_date)\
                       .replace('{{READ_TIME}}', str(read_time))\
                       .replace('{{HEADER_TAGS}}', header_tags_html)\
                       .replace('{{COVER_IMAGE}}', cover_image_html)\
                       .replace('{{POST_CONTENT}}', post_content)\
                       .replace('{{RELATED_POSTS}}', related_posts_html)
  return post_html

def generate_related_posts_section(post, all_posts_metadata, rel_path):
  tags_set = set(post['tags'])
  candidates = []
  
  for p in all_posts_metadata:
    if p['url'] == post['filename']:
      continue
    p_tags_set = set(p['tags'])
    overlap = len(tags_set.intersection(p_tags_set))
    if overlap > 0:
      candidates.append((p, overlap))
      
  candidates.sort(key=lambda x: (x[1], x[0]['date']), reverse=True)
  related = [c[0] for c in candidates[:3]]
  
  if len(related) < 3:
    used_urls = {p['url'] for p in related}
    used_urls.add(post['filename'])
    for p in all_posts_metadata:
      if p['url'] not in used_urls:
        related.append(p)
        used_urls.add(p['url'])
        if len(related) >= 3:
          break
          
  if not related:
    return ""
    
  cards_html = ""
  for r in related[:3]:
    cover_image_html = f'<img class="card-image" src="{r["coverImage"]}" alt="{r["title"]}" width="400" height="250" loading="lazy" decoding="async">' if r["coverImage"] else f'<div class="card-image-fallback">{r["title"][:2].upper()}</div>'
    tags_html = "".join([f'<span class="card-tag">{t}</span>' for t in r["tags"][:2]])
    cards_html += f"""
      <article class="post-card">
        <div class="card-image-wrapper">
          {cover_image_html}
        </div>
        <div class="card-content">
          <div class="card-meta">
            <span>
              <svg fill="currentColor" viewBox="0 0 24 24"><path d="M19 4h-1V2h-2v2H8V2H6v2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 16H5V10h14v10zm0-12H5V6h14v2z"/></svg>
              {r["formattedDate"]}
            </span>
          </div>
          <h3 class="card-title" style="font-size:1.1rem;"><a href="{rel_path}{r["url"].lstrip('/')}">{r["title"]}</a></h3>
          <p class="card-excerpt" style="font-size:0.85rem; margin-bottom:12px;">{r["excerpt"]}</p>
          <div class="card-tags">
            {tags_html}
          </div>
        </div>
      </article>
    """
    
  return f"""
    <section class="related-posts-section">
      <h2>You Might Also Like</h2>
      <div class="posts-grid">
        {cards_html}
      </div>
    </section>
  """

def main():
  print("Starting migration process...")
  
  try:
    atom_path = find_feed_file()
    print(f"Found Blogger feed at: {atom_path}")
  except FileNotFoundError as e:
    print(e)
    return
    
  tree = ET.parse(atom_path)
  root = tree.getroot()
  
  ns = {
    'atom': 'http://www.w3.org/2005/Atom',
    'blogger': 'http://schemas.google.com/blogger/2018'
  }
  
  entries = root.findall('atom:entry', ns)
  print(f"Parsed {len(entries)} elements from XML.")
  
  output_dir = '.'
  os.makedirs(output_dir, exist_ok=True)
  
  posts_metadata = []
  raw_posts = []
  raw_pages = []
  
  for entry in entries:
    etype = entry.find('blogger:type', ns)
    etype_text = etype.text if etype is not None else ''
    
    status = entry.find('blogger:status', ns)
    status_text = status.text if status is not None else ''
    
    if status_text != 'LIVE':
      continue
      
    title_el = entry.find('atom:title', ns)
    title = title_el.text if title_el is not None else '(No Title)'
    
    content_el = entry.find('atom:content', ns)
    content = content_el.text if content_el is not None else ''
    
    published_el = entry.find('atom:published', ns)
    published = published_el.text if published_el is not None else ''
    
    filename_el = entry.find('blogger:filename', ns)
    filename = filename_el.text if filename_el is not None else ''
    
    tags = []
    cats = entry.findall('atom:category', ns)
    for cat in cats:
      term = cat.get('term')
      if term and not term.startswith('http://') and not term.startswith('https://') and term != 'http://schemas.google.com/blogger/2008/kind#post' and term != 'http://schemas.google.com/blogger/2008/kind#page':
        term_clean = term.strip()
        if len(term_clean) <= 30 and len(term_clean.split()) <= 4 and term_clean.lower() != title.strip().lower():
          tags.append(term_clean)
        
    if etype_text == 'POST':
      if not filename:
        slug = re.sub(r'[^a-zA-Z0-9\s-]', '', title).strip().lower()
        slug = re.sub(r'[\s-]+', '-', slug)
        filename = f"/posts/{slug}.html"
        
      depth = filename.lstrip('/').count('/')
      rel_path = '../' * depth if depth > 0 else './'
      
      cover_img = find_cover_image(content)
      read_time = calculate_read_time(content)
      excerpt = clean_excerpt(content)
      formatted_date = format_date(published)
      
      raw_posts.append({
        'title': title,
        'date': published,
        'formattedDate': formatted_date,
        'filename': filename,
        'content': content,
        'tags': tags,
        'readTime': read_time,
        'coverImage': cover_img,
        'excerpt': excerpt,
        'depth': depth,
        'rel_path': rel_path
      })
      
      posts_metadata.append({
        'title': title,
        'date': published,
        'formattedDate': formatted_date,
        'url': filename,
        'readTime': read_time,
        'coverImage': cover_img,
        'excerpt': excerpt,
        'tags': tags
      })
      
    elif etype_text == 'PAGE':
      if not filename:
        slug = re.sub(r'[^a-zA-Z0-9\s-]', '', title).strip().lower()
        slug = re.sub(r'[\s-]+', '-', slug)
        filename = f"/p/{slug}.html"
        
      depth = filename.lstrip('/').count('/')
      rel_path = '../' * depth if depth > 0 else './'
      
      raw_pages.append({
        'title': title,
        'filename': filename,
        'content': content,
        'depth': depth,
        'rel_path': rel_path
      })

  raw_posts.sort(key=lambda x: x['date'], reverse=True)
  posts_metadata.sort(key=lambda x: x['date'], reverse=True)
  
  with open(os.path.join(output_dir, 'posts-metadata.js'), 'w', encoding='utf-8') as f:
    f.write("window.postsData = ")
    json.dump(posts_metadata, f, ensure_ascii=False, indent=2)
    f.write(";")
  print(f"Generated {len(posts_metadata)} posts in posts-metadata.js")
  
  deprecated_json = os.path.join(output_dir, 'posts.json')
  if os.path.exists(deprecated_json):
    os.remove(deprecated_json)
  
  with open(os.path.join(output_dir, 'style.css'), 'w', encoding='utf-8') as f:
    f.write(SHARED_CSS)
  with open(os.path.join(output_dir, 'main.js'), 'w', encoding='utf-8') as f:
    f.write(SHARED_JS)
  print("Generated style.css and main.js")
  
  # Load Index HTML modularly
  index_tmpl = load_template('index.html')
  head = get_head("puru world official", "puru world official - A blog on everyday need daily. Exploring technology, lifeskills, travel, and more.", "./", "index.html", '<script src="./posts-metadata.js"></script><script src="./videos-metadata.js"></script>')
  header = get_header("./", has_progress=False, id_val="Index")
  footer = get_footer("./")
  index_html = index_tmpl.replace('{{HEAD}}', head).replace('{{HEADER}}', header).replace('{{FOOTER}}', footer)
  
  with open(os.path.join(output_dir, 'index.html'), 'w', encoding='utf-8') as f:
    f.write(index_html)
  print("Generated index.html")
  
  # Fetch all YouTube videos programmatically
  print("Fetching YouTube videos...")
  videos = fetch_youtube_videos("UCFoVp5Va975oQQpevpQErQQ")
  with open(os.path.join(output_dir, 'videos-metadata.js'), 'w', encoding='utf-8') as f:
    f.write("window.videosData = ")
    json.dump(videos, f, ensure_ascii=False, indent=2)
    f.write(";")
  print(f"Generated {len(videos)} videos in videos-metadata.js")
  
  # Write p/videos.html page modularly
  videos_tmpl = load_template('videos.html')
  head = get_head("Videos - puru world official", "Watch my latest video updates, gaming livestreams, and tutorials from Puru World.", "../", "p/videos.html", '<script src="../videos-metadata.js"></script>')
  header = get_header("../", has_progress=False, id_val="Videos")
  footer = get_footer("../")
  videos_html = videos_tmpl.replace('{{HEAD}}', head).replace('{{HEADER}}', header).replace('{{FOOTER}}', footer)
  
  videos_page_dir = os.path.join(output_dir, 'p')
  os.makedirs(videos_page_dir, exist_ok=True)
  with open(os.path.join(videos_page_dir, 'videos.html'), 'w', encoding='utf-8') as f:
    f.write(videos_html)
  print("Generated p/videos.html")

  # Write p/tools-games.html page modularly
  tools_tmpl = load_template('tools-games.html')
  head_tools = get_head("Tools & Games - puru world official", "Play virtual casual games or launch interactive developer utility products.", "../", "p/tools-games.html")
  header_tools = get_header("../", has_progress=False, id_val="Tools")
  tools_html = tools_tmpl.replace('{{HEAD}}', head_tools).replace('{{HEADER}}', header_tools).replace('{{FOOTER}}', footer)
  with open(os.path.join(videos_page_dir, 'tools-games.html'), 'w', encoding='utf-8') as f:
    f.write(tools_html)
  print("Generated p/tools-games.html")
  
  # Generate standard ads.txt
  with open(os.path.join(output_dir, 'ads.txt'), 'w', encoding='utf-8') as f:
    f.write("google.com, pub-XXXXXXXXXXXXXXXX, DIRECT, f08c47fec0942fa0\n")
  print("Generated ads.txt")
  
  # Generate standard legal/info pages
  legal_pages = [
    ('privacy.html', 'Privacy Policy - puru world official', 'Privacy Policy page for puru world official.'),
    ('about.html', 'About Us - puru world official', 'Learn more about puru world official, our mission, and our content creators.'),
    ('contact.html', 'Contact Us - puru world official', 'Get in touch with puru world official for support, feedback, or business inquiries.'),
    ('terms.html', 'Terms of Service - puru world official', 'Read the Terms of Service for puru world official.'),
    ('disclaimer.html', 'Disclaimer - puru world official', 'Content disclaimer and liability guidelines for puru world official.')
  ]
  
  for filename, title, desc in legal_pages:
    tmpl = load_template(filename)
    head = get_head(title, desc, "../", f"p/{filename}")
    header = get_header("../", has_progress=False, id_val="Legal")
    footer = get_footer("../")
    html = tmpl.replace('{{HEAD}}', head).replace('{{HEADER}}', header).replace('{{FOOTER}}', footer)
    
    with open(os.path.join(videos_page_dir, filename), 'w', encoding='utf-8') as f:
      f.write(html)
    print(f"Generated p/{filename}")
  
  # Generate admin dashboard
  dashboard_dir = os.path.join(output_dir, 'dashboard')
  os.makedirs(dashboard_dir, exist_ok=True)
  
  dashboard_tmpl = load_template('dashboard.html')
  dashboard_head = get_head('Admin Dashboard - puru world official', 'Analytics dashboard for puru world official.', '../', 'dashboard/index.html', '<script src="../posts-metadata.js"></script>')
  dashboard_header = get_header('../', has_progress=False, id_val="Dashboard")
  dashboard_footer = get_footer('../')
  
  dashboard_html = dashboard_tmpl.replace('{{HEAD}}', dashboard_head)\
                                 .replace('{{HEADER}}', dashboard_header)\
                                 .replace('{{FOOTER}}', dashboard_footer)
                                 
  with open(os.path.join(dashboard_dir, 'index.html'), 'w', encoding='utf-8') as f:
    f.write(dashboard_html)
  print("Generated dashboard/index.html")
  
  print("Writing post HTML files...")
  for i, post in enumerate(raw_posts):
    content_rewritten = rewrite_internal_links(post['content'], post['depth'])
    content_linked = inject_contextual_links(content_rewritten, post['filename'], posts_metadata, post['rel_path'])
    content_sanitized = sanitize_blogger_html(content_linked, post['title'])
    related_html = generate_related_posts_section(post, posts_metadata, post['rel_path'])
    
    post_html = make_post_html(
      post_title=post['title'],
      post_date=post['formattedDate'],
      post_tags=post['tags'],
      post_content=content_sanitized,
      read_time=post['readTime'],
      cover_image=post['coverImage'],
      rel_path=post['rel_path'],
      filename=post['filename'],
      related_posts_html=related_html
    )
    
    dest_path = os.path.join(output_dir, post['filename'].lstrip('/'))
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    with open(dest_path, 'w', encoding='utf-8') as f:
      f.write(post_html)
      
    if (i + 1) % 200 == 0 or (i + 1) == len(raw_posts):
      print(f"  Processed {i + 1}/{len(raw_posts)} posts...")
      
  print("Writing page HTML files...")
  for i, page in enumerate(raw_pages):
    content_rewritten = rewrite_internal_links(page['content'], page['depth'])
    content_sanitized = sanitize_blogger_html(content_rewritten, page['title'])
    
    if 'flip-coin' in page['filename']:
      content_sanitized = content_sanitized.replace(
        'body {',
        'body-old {'
      ).replace(
        '.coin.flipping {\n            animation: flip 1s ease-in-out;\n        }',
        '/* removed flipping animation class */'
      ).replace(
        '.tails {\n            background: linear-gradient(45deg, #c0c0c0, #999999);\n            transform: rotateY(180deg);\n        }',
        '.tails {\n            background: linear-gradient(45deg, #c0c0c0, #999999);\n            transform: rotateX(180deg);\n        }'
      ).replace(
        '@keyframes flip {\n            0% { transform: rotateY(0deg); }\n            50% { transform: rotateY(720deg); }\n            100% { transform: rotateY(0deg); }\n        }',
        '@keyframes jump {\n            0% { transform: translateY(0) scale(1); }\n            50% { transform: translateY(-160px) scale(1.1); }\n            100% { transform: translateY(0) scale(1); }\n        }\n        .coin-container.flipping {\n            animation: jump 1.2s ease-in-out;\n        }'
      ).replace(
        'transition: transform 1s ease-in-out;',
        'transition: transform 1.2s cubic-bezier(0.175, 0.885, 0.32, 1.15);'
      ).replace(
        '''        <div class="coin" id="coin">
            <div class="heads">Heads</div>
            <div class="tails">Tails</div>
        </div>''',
        '''        <div class="coin" id="coin">
            <!-- Heads Face (Gold Custom P Brand) -->
            <div class="heads" style="position: absolute; width: 100%; height: 100%; backface-visibility: hidden; border-radius: 50%; display: flex; justify-content: center; align-items: center; background: radial-gradient(circle, #ffe066 0%, #f5b041 70%, #d35400 100%) !important; border: 5px double #f39c12 !important; box-shadow: inset 0 0 20px rgba(0,0,0,0.2), 0 8px 16px rgba(0,0,0,0.3) !important;">
              <svg viewBox="0 0 100 100" style="width: 80%; height: 80%;">
                <path d="M50 15 L59 38 L83 38 L64 53 L71 77 L50 62 L29 77 L36 53 L17 38 L41 38 Z" fill="#fff" opacity="0.25" />
                <text x="50%" y="62%" font-family="\'Outfit\', sans-serif" font-size="36" font-weight="900" fill="#fff" text-anchor="middle" style="text-shadow: 0 2px 4px rgba(0,0,0,0.3); font-style: italic;">P</text>
                <circle cx="50" cy="50" r="41" stroke="#f39c12" stroke-width="1.5" stroke-dasharray="3,3" fill="none" />
              </svg>
            </div>
            <!-- Tails Face (Silver Custom 1 Value) -->
            <div class="tails" style="position: absolute; width: 100%; height: 100%; backface-visibility: hidden; border-radius: 50%; display: flex; justify-content: center; align-items: center; background: radial-gradient(circle, #e5e8e8 0%, #bdc3c7 70%, #7f8c8d 100%) !important; border: 5px double #95a5a6 !important; box-shadow: inset 0 0 20px rgba(0,0,0,0.2), 0 8px 16px rgba(0,0,0,0.3) !important; transform: rotateX(180deg) !important;">
              <svg viewBox="0 0 100 100" style="width: 80%; height: 80%;">
                <path d="M25 50 Q25 75 50 75 Q75 75 75 50" fill="none" stroke="#7f8c8d" stroke-width="3" stroke-linecap="round" opacity="0.3" />
                <text x="50%" y="58%" font-family="\'Outfit\', sans-serif" font-size="38" font-weight="900" fill="#fff" text-anchor="middle" style="text-shadow: 0 2px 4px rgba(0,0,0,0.3);">1</text>
                <circle cx="50" cy="50" r="41" stroke="#7f8c8d" stroke-width="1.5" stroke-dasharray="3,3" fill="none" />
              </svg>
            </div>
        </div>'''
      ).replace(
        '.flip-button {\n            background: #6200ea;\n            color: white;\n            padding: 0.75rem 1.5rem;\n            border: none;\n            border-radius: 4px;\n            font-size: 1rem;\n            cursor: pointer;\n            display: flex;\n            align-items: center;\n            gap: 0.5rem;\n            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);\n            transition: background 0.3s, transform 0.2s;\n        }',
        '''.flip-button {
            background: var(--accent-gradient) !important;
            color: white !important;
            padding: 10px 24px !important;
            border: none !important;
            border-radius: 8px !important;
            font-size: 0.95rem !important;
            font-weight: 600 !important;
            cursor: pointer !important;
            display: inline-flex !important;
            align-items: center !important;
            gap: 8px !important;
            box-shadow: var(--shadow-sm) !important;
            transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
        }'''
      ).replace(
        '''        function flipCoin() {
            const coin = document.getElementById('coin');
            coin.classList.add('flipping');
            
            // Randomly decide heads or tails
            const isHeads = Math.random() > 0.5;
            const rotation = isHeads ? 0 : 180;
            coin.style.transform = `rotateY(${rotation}deg)`;
            
            // Remove flipping class after animation
            setTimeout(() => {
                coin.classList.remove('flipping');
            }, 1000);
        }''',
        '''        let currentRotation = 0;
        function flipCoin() {
            const coin = document.getElementById('coin');
            const container = document.querySelector('.coin-container');
            const btn = document.querySelector('.flip-button');
            btn.disabled = true;
            
            const isHeads = Math.random() > 0.5;
            const spins = Math.floor(Math.random() * 4 + 5) * 360;
            
            currentRotation += spins;
            if (Math.round(currentRotation / 180) % 2 !== (isHeads ? 0 : 1)) {
                currentRotation += 180;
            }
            
            coin.style.transform = `rotateX(${currentRotation}deg)`;
            container.classList.add('flipping');
            
            setTimeout(() => {
                container.classList.remove('flipping');
                btn.disabled = false;
            }, 1200);
        }'''
      )
    
    if 'tic-tac-toe' in page['filename']:
      content_sanitized = content_sanitized.replace(
        '#tictactoe-game * {',
        '#tictactoe-game-old-star {'
      ).replace(
        '#tictactoe-game {',
        '''#tictactoe-game {
            font-family: \'Outfit\', sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px 0;
        }
        #tictactoe-game .container {
            background: var(--bg-secondary) !important;
            border: 1px solid var(--border-color) !important;
            border-radius: 16px !important;
            box-shadow: var(--shadow-sm) !important;
            padding: 24px !important;
            max-width: 400px !important;
            width: 100% !important;
        }
        #tictactoe-game h1 {
            text-align: center !important;
            color: var(--text-primary) !important;
            margin-bottom: 24px !important;
            font-weight: 700 !important;
            font-size: 1.8rem !important;
        }
        #tictactoe-game .mode-selection {
            display: flex !important;
            justify-content: space-between !important;
            gap: 10px !important;
            margin-bottom: 24px !important;
        }
        #tictactoe-game .mode-btn {
            flex: 1 !important;
            background: rgba(0, 0, 0, 0.05) !important;
            border: 1px solid var(--border-color) !important;
            padding: 10px !important;
            border-radius: 8px !important;
            cursor: pointer !important;
            font-size: 0.9rem !important;
            font-weight: 600 !important;
            color: var(--text-secondary) !important;
            transition: all 0.2s !important;
        }
        [data-theme="dark"] #tictactoe-game .mode-btn {
            background: rgba(255, 255, 255, 0.05) !important;
        }
        #tictactoe-game .mode-btn:hover {
            border-color: var(--accent-color) !important;
            color: var(--accent-color) !important;
        }
        #tictactoe-game .mode-btn.active {
            background: var(--accent-gradient) !important;
            color: white !important;
            border-color: transparent !important;
        }
        #tictactoe-game .status {
            text-align: center !important;
            font-size: 1rem !important;
            font-weight: 600 !important;
            color: var(--text-primary) !important;
            margin-bottom: 20px !important;
            min-height: 24px !important;
            padding: 12px !important;
            border-radius: 8px !important;
            background: rgba(0, 0, 0, 0.02) !important;
            border: 1px solid var(--border-color) !important;
            transition: all 0.3s !important;
        }
        [data-theme="dark"] #tictactoe-game .status {
            background: rgba(255, 255, 255, 0.02) !important;
        }
        #tictactoe-game .board {
            display: grid !important;
            grid-template-columns: repeat(3, 1fr) !important;
            gap: 10px !important;
            margin-bottom: 24px !important;
        }
        #tictactoe-game .cell {
            aspect-ratio: 1 !important;
            background: rgba(0, 0, 0, 0.01) !important;
            border: 1px solid var(--border-color) !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            font-size: 2.5rem !important;
            font-weight: 800 !important;
            cursor: pointer !important;
            transition: all 0.2s !important;
            border-radius: 12px !important;
            user-select: none !important;
            color: var(--text-primary) !important;
        }
        [data-theme="dark"] #tictactoe-game .cell {
            background: rgba(255, 255, 255, 0.01) !important;
        }
        #tictactoe-game .cell:hover {
            background: rgba(0, 0, 0, 0.03) !important;
            border-color: var(--accent-color) !important;
        }
        [data-theme="dark"] #tictactoe-game .cell:hover {
            background: rgba(255, 255, 255, 0.03) !important;
        }
        #tictactoe-game .cell.x {
            color: #ef4444 !important;
            text-shadow: 0 0 12px rgba(239, 68, 68, 0.45) !important;
        }
        #tictactoe-game .cell.o {
            color: #06b6d4 !important;
            text-shadow: 0 0 12px rgba(6, 182, 212, 0.45) !important;
        }
        #tictactoe-game .cell.winning-cell {
            background: rgba(34, 197, 94, 0.15) !important;
            border-color: #22c55e !important;
            color: #22c55e !important;
            animation: pulse-win 1s infinite alternate !important;
        }
        @keyframes pulse-win {
            0% { transform: scale(1); }
            100% { transform: scale(1.03); }
        }
        #tictactoe-game .controls {
            display: flex !important;
            justify-content: center !important;
        }
        #tictactoe-game .reset-btn {
            background: var(--accent-gradient) !important;
            color: white !important;
            border: none !important;
            padding: 10px 24px !important;
            border-radius: 8px !important;
            cursor: pointer !important;
            font-size: 0.9rem !important;
            font-weight: 600 !important;
            transition: all 0.2s !important;
            width: 100% !important;
        }
        #tictactoe-game .reset-btn:hover {
            opacity: 0.9 !important;
            transform: translateY(-1px) !important;
        }
        #tictactoe-game .winner {
            color: #22c55e !important;
            background: rgba(34, 197, 94, 0.1) !important;
            border-color: rgba(34, 197, 94, 0.2) !important;
        }
        #tictactoe-game .draw {
            color: #eab308 !important;
            background: rgba(234, 179, 8, 0.1) !important;
            border-color: rgba(234, 179, 8, 0.2) !important;
        }
        #tictactoe-game-old {'''
      ).replace(
        'cell.classList.remove(\'x\', \'o\');',
        'cell.classList.remove(\'x\', \'o\', \'winning-cell\');'
      ).replace(
        '''                checkWinner() {
                    return this.getWinner() !== null;
                }''',
        '''                checkWinner() {
                    const winPatterns = [
                        [0, 1, 2], [3, 4, 5], [6, 7, 8],
                        [0, 3, 6], [1, 4, 7], [2, 5, 8],
                        [0, 4, 8], [2, 4, 6]
                    ];
                    for (let pattern of winPatterns) {
                        const [a, b, c] = pattern;
                        if (this.board[a] && this.board[a] === this.board[b] && this.board[a] === this.board[c]) {
                            [a, b, c].forEach(idx => {
                                const cell = gameContainer.querySelector(`[data-index="${idx}"]`);
                                if (cell) cell.classList.add(\'winning-cell\');
                            });
                            return true;
                        }
                    }
                    return false;
                }'''
      )

    if 'spin-bottle' in page['filename']:
      content_sanitized = content_sanitized.replace(
        'body {',
        'body-old {'
      ).replace(
        '.spin-button {',
        '''.spin-button {
            background: var(--accent-gradient) !important;
            color: white !important;
            padding: 10px 24px !important;
            border: none !important;
            border-radius: 8px !important;
            font-size: 0.95rem !important;
            font-weight: 600 !important;
            cursor: pointer !important;
            display: inline-flex !important;
            align-items: center !important;
            gap: 8px !important;
            box-shadow: var(--shadow-sm) !important;
            transition: all 0.2s !important;
        }
        .spin-button-old {'''
      ).replace(
        '''    <div class="bottle-container" onclick="spinBottle()">
        <div class="bottle" id="bottle">
            <div class="bottle-body">
                <div class="bottle-neck" id="bottleNeck"></div>
                <div class="bottle-main" id="bottleMain"></div>
            </div>
        </div>
    </div>
    <button class="spin-button" onclick="spinBottle()">
        <span class="material-icons">refresh</span> Spin Again
    </button>''',
        '''    <div class="bottle-selector" style="display: flex; gap: 8px; margin-bottom: 24px; justify-content: center; flex-wrap: wrap;">
        <button onclick="changeBottleTheme(\'green\')" class="theme-btn active" style="padding: 6px 12px; border: 1px solid var(--border-color); border-radius: 20px; background: rgba(0,0,0,0.03); color: var(--text-secondary); font-size: 0.82rem; font-weight: 600; cursor: pointer; transition: all 0.2s;">Green Glass</button>
        <button onclick="changeBottleTheme(\'gold\')" class="theme-btn" style="padding: 6px 12px; border: 1px solid var(--border-color); border-radius: 20px; background: rgba(0,0,0,0.03); color: var(--text-secondary); font-size: 0.82rem; font-weight: 600; cursor: pointer; transition: all 0.2s;">Champagne</button>
        <button onclick="changeBottleTheme(\'neon\')" class="theme-btn" style="padding: 6px 12px; border: 1px solid var(--border-color); border-radius: 20px; background: rgba(0,0,0,0.03); color: var(--text-secondary); font-size: 0.82rem; font-weight: 600; cursor: pointer; transition: all 0.2s;">Neon Cyber</button>
        <button onclick="changeBottleTheme(\'ruby\')" class="theme-btn" style="padding: 6px 12px; border: 1px solid var(--border-color); border-radius: 20px; background: rgba(0,0,0,0.03); color: var(--text-secondary); font-size: 0.82rem; font-weight: 600; cursor: pointer; transition: all 0.2s;">Ruby Decanter</button>
    </div>
    <div class="bottle-container" onclick="spinBottle()" style="display: inline-block; cursor: pointer; transition: transform 0.2s; margin-top: 10px;">
        <div class="bottle" id="bottle" style="transition: transform 2.5s cubic-bezier(0.25, 0.1, 0.25, 1);">
            <svg class="bottle-svg" viewBox="0 0 100 240" style="width: 100px; height: 240px; filter: drop-shadow(0 8px 16px rgba(0,0,0,0.3));">
                <defs>
                    <linearGradient id="glassGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stop-color="#1b5e20" />
                        <stop offset="25%" stop-color="#4caf50" />
                        <stop offset="50%" stop-color="#81c784" />
                        <stop offset="75%" stop-color="#2e7d32" />
                        <stop offset="100%" stop-color="#1b5e20" />
                    </linearGradient>
                    <linearGradient id="labelGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stop-color="#ffd700" />
                        <stop offset="50%" stop-color="#fff" />
                        <stop offset="100%" stop-color="#ffaa00" />
                    </linearGradient>
                    <linearGradient id="capGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stop-color="#d4af37" />
                        <stop offset="50%" stop-color="#fff" />
                        <stop offset="100%" stop-color="#aa7c11" />
                    </linearGradient>
                    <linearGradient id="goldGlass" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stop-color="#b7950b" />
                        <stop offset="25%" stop-color="#f1c40f" />
                        <stop offset="50%" stop-color="#f9e79f" />
                        <stop offset="75%" stop-color="#d4ac0d" />
                        <stop offset="100%" stop-color="#9a7d0a" />
                    </linearGradient>
                    <linearGradient id="goldCap" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stop-color="#fff" />
                        <stop offset="50%" stop-color="#e5e7eb" />
                        <stop offset="100%" stop-color="#9ca3af" />
                    </linearGradient>
                    <linearGradient id="neonGlass" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stop-color="#4a0e4e" />
                        <stop offset="25%" stop-color="#9c27b0" />
                        <stop offset="50%" stop-color="#e040fb" />
                        <stop offset="75%" stop-color="#7b1fa2" />
                        <stop offset="100%" stop-color="#4a0e4e" />
                    </linearGradient>
                    <linearGradient id="neonCap" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stop-color="#00ffff" />
                        <stop offset="50%" stop-color="#fff" />
                        <stop offset="100%" stop-color="#008080" />
                    </linearGradient>
                    <linearGradient id="rubyGlass" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stop-color="#78281f" />
                        <stop offset="25%" stop-color="#c0392b" />
                        <stop offset="50%" stop-color="#f1948a" />
                        <stop offset="75%" stop-color="#922b21" />
                        <stop offset="100%" stop-color="#641e16" />
                    </linearGradient>
                    <linearGradient id="rubyCap" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stop-color="#d4af37" />
                        <stop offset="50%" stop-color="#fff" />
                        <stop offset="100%" stop-color="#aa7c11" />
                    </linearGradient>
                </defs>
                <rect id="bottle-cap-rect" x="42" y="10" width="16" height="15" rx="3" fill="url(#capGrad)" />
                <path id="bottle-body-path" d="M44 25 L44 80 Q40 100 25 110 L25 210 Q25 230 40 230 L60 230 Q75 230 75 210 L75 110 Q60 100 56 80 L56 25 Z" fill="url(#glassGrad)" />
                <path d="M30 115 Q40 105 50 105" stroke="rgba(255, 255, 255, 0.4)" stroke-width="4" fill="none" stroke-linecap="round" />
                <path d="M30 125 L30 200" stroke="rgba(255, 255, 255, 0.3)" stroke-width="3" fill="none" stroke-linecap="round" />
                <rect x="29" y="130" width="42" height="50" rx="4" fill="url(#labelGrad)" />
                <text id="bottle-label-text" x="50" y="160" font-family="\'Outfit\', sans-serif" font-size="9" font-weight="bold" fill="#333" text-anchor="middle">puruworld</text>
            </svg>
        </div>
    </div>
    <div style="margin-top: 15px;">
        <button class="spin-button" onclick="spinBottle()">
            <span class="material-icons">refresh</span> Spin Bottle
        </button>
    </div>'''
      ).replace(
        '''        function spinBottle() {
            const bottle = document.getElementById('bottle');
            const bottleNeck = document.getElementById('bottleNeck');
            const bottleMain = document.getElementById('bottleMain');
            
            // Increment rotation angle (multiple full spins plus a random angle)
            const randomAngle = 1080 + Math.floor(Math.random() * 360);
            currentAngle += randomAngle;
            bottle.style.transform = `rotate(${currentAngle}deg)`;
            
            // Randomly select a color set
            const randomColorSet = colorSets[Math.floor(Math.random() * colorSets.length)];
            bottleNeck.style.background = randomColorSet.neck.gradient;
            bottleNeck.style.borderColor = randomColorSet.neck.border;
            bottleMain.style.background = randomColorSet.main.gradient;
            bottleMain.style.borderColor = randomColorSet.main.border;
        }''',
        '''        const bottleThemes = {
            green: { cap: 'url(#capGrad)', body: 'url(#glassGrad)', text: 'puruworld' },
            gold: { cap: 'url(#goldCap)', body: 'url(#goldGlass)', text: 'CELEBRATE' },
            neon: { cap: 'url(#neonCap)', body: 'url(#neonGlass)', text: 'CYBER' },
            ruby: { cap: 'url(#rubyCap)', body: 'url(#rubyGlass)', text: 'ROYAL' }
        };
        window.changeBottleTheme = function(theme) {
            const data = bottleThemes[theme];
            document.getElementById('bottle-cap-rect').setAttribute('fill', data.cap);
            document.getElementById('bottle-body-path').setAttribute('fill', data.body);
            document.getElementById('bottle-label-text').textContent = data.text;
            
            const container = document.querySelector('.bottle-selector');
            if (container) {
                container.querySelectorAll('.theme-btn').forEach(btn => {
                    btn.classList.remove('active');
                });
            }
            event.currentTarget.classList.add('active');
        };

        function spinBottle() {
            const bottle = document.getElementById('bottle');
            const randomAngle = 1440 + Math.floor(Math.random() * 360);
            currentAngle += randomAngle;
            bottle.style.transform = `rotate(${currentAngle}deg)`;
        }'''
      )

    if 'json-formatter' in page['filename']:
      content_sanitized = content_sanitized.replace(
        '.json-formatter-container {',
        '''.json-formatter-container {
            font-family: \'Inter\', sans-serif !important;
            display: flex !important;
            gap: 20px !important;
            height: 550px !important;
            margin: 0 auto !important;
            padding: 0 !important;
            box-sizing: border-box !important;
            background-color: transparent !important;
        }
        .json-formatter-container-old {'''
      ).replace(
        '.json-formatter-container .pane {',
        '''.json-formatter-container .pane {
            flex: 1 !important;
            display: flex !important;
            flex-direction: column !important;
            background-color: var(--bg-secondary) !important;
            border: 1px solid var(--border-color) !important;
            border-radius: 12px !important;
            padding: 20px !important;
            box-shadow: var(--shadow-sm) !important;
        }
        .json-formatter-container .pane-old {'''
      ).replace(
        '.json-formatter-container button {',
        '''.json-formatter-container button {
            padding: 8px 16px !important;
            border: none !important;
            border-radius: 6px !important;
            background: var(--accent-gradient) !important;
            color: #fff !important;
            cursor: pointer !important;
            font-size: 13px !important;
            font-weight: 600 !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            transition: all 0.2s !important;
        }
        .json-formatter-container button-old {'''
      ).replace(
        '.json-formatter-container textarea {',
        '''.json-formatter-container textarea {
            width: 100% !important;
            height: 80% !important;
            resize: none !important;
            font-family: \'Courier New\', monospace !important;
            font-size: 13px !important;
            border: 1px solid var(--border-color) !important;
            border-radius: 8px !important;
            padding: 12px !important;
            box-sizing: border-box !important;
            background: var(--bg-primary) !important;
            color: var(--text-primary) !important;
        }
        .json-formatter-container textarea-old {'''
      ).replace(
        '.json-formatter-container #output {',
        '''.json-formatter-container #output {
            height: 70% !important;
            overflow-y: auto !important;
            border: 1px solid var(--border-color) !important;
            border-radius: 8px !important;
            padding: 12px !important;
            font-family: \'Courier New\', monospace !important;
            font-size: 13px !important;
            background: var(--bg-primary) !important;
            color: var(--text-primary) !important;
            white-space: pre-wrap !important;
        }
        .json-formatter-container #output-old {'''
      )
    
    page_tmpl = load_template('page.html')
    head = get_head(f"{page['title']} - puru world official", clean_excerpt(page['content'], 150), page['rel_path'], page['filename'])
    header = get_header(page['rel_path'], has_progress=False, id_val="Page")
    footer = get_footer(page['rel_path'])
    
    is_game = any(k in page['filename'] for k in ['flip-coin', 'spin-bottle', 'tic-tac-toe', 'json-formatter'])
    layout_class = 'container page-layout game-page' if is_game else 'container page-layout'
    page_tmpl_patched = page_tmpl.replace('class="container page-layout"', f'class="{layout_class}"')
    
    page_html = page_tmpl_patched.replace('{{HEAD}}', head).replace('{{HEADER}}', header).replace('{{FOOTER}}', footer).replace('{{PAGE_TITLE}}', page['title']).replace('{{PAGE_CONTENT}}', content_sanitized)
    
    dest_path = os.path.join(output_dir, page['filename'].lstrip('/'))
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    with open(dest_path, 'w', encoding='utf-8') as f:
      f.write(page_html)
  
  print(f"Generated {len(raw_pages)} pages.")
  
  # Generate dynamic sitemap.xml
  print("Generating sitemap.xml...")
  sitemap_entries = [
    '  <url><loc>https://purujeet.github.io/puruworld/</loc><priority>1.0</priority><changefreq>daily</changefreq></url>',
    '  <url><loc>https://purujeet.github.io/puruworld/index.html</loc><priority>0.9</priority><changefreq>daily</changefreq></url>',
    '  <url><loc>https://purujeet.github.io/puruworld/p/videos.html</loc><priority>0.9</priority><changefreq>daily</changefreq></url>',
    '  <url><loc>https://purujeet.github.io/puruworld/p/tools-games.html</loc><priority>0.9</priority><changefreq>weekly</changefreq></url>',
    '  <url><loc>https://purujeet.github.io/puruworld/dashboard/index.html</loc><priority>0.7</priority><changefreq>weekly</changefreq></url>'
  ]
  
  # Add tools & games
  for page in raw_pages:
    clean_fn = page['filename'].lstrip('/')
    sitemap_entries.append(f'  <url><loc>https://purujeet.github.io/puruworld/{clean_fn}</loc><priority>0.8</priority><changefreq>weekly</changefreq></url>')
    
  # Add legal pages
  for filename, _, _ in legal_pages:
    sitemap_entries.append(f'  <url><loc>https://purujeet.github.io/puruworld/p/{filename}</loc><priority>0.5</priority><changefreq>monthly</changefreq></url>')
    
  # Add blog posts
  for post in raw_posts:
    clean_fn = post['filename'].lstrip('/')
    sitemap_entries.append(f'  <url><loc>https://purujeet.github.io/puruworld/{clean_fn}</loc><priority>0.7</priority><changefreq>monthly</changefreq></url>')
    
  sitemap_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(sitemap_entries)}
</urlset>
"""
  with open(os.path.join(output_dir, 'sitemap.xml'), 'w', encoding='utf-8') as f:
    f.write(sitemap_xml.strip())
  print("Generated sitemap.xml")
  
  print("Migration completed successfully!")

if __name__ == '__main__':
  main()
