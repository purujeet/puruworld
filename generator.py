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

def sanitize_blogger_html(content):
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

    content = re.sub(r'<img\s+[^>]+>', clean_standalone_img, content, flags=re.IGNORECASE)
    return content

def fetch_youtube_videos(channel_id):
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    print(f"Fetching YouTube feed from: {url}")
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        with urllib.request.urlopen(req, timeout=8) as response:
            xml_data = response.read()
        
        ns = {
            'atom': 'http://www.w3.org/2005/Atom',
            'yt': 'http://www.youtube.com/xml/schemas/2015',
            'media': 'http://search.yahoo.com/mrss/'
        }
        
        root = ET.fromstring(xml_data)
        entries = root.findall('atom:entry', ns)
        
        videos = []
        for entry in entries:
            video_id_el = entry.find('yt:videoId', ns)
            video_id = video_id_el.text if video_id_el is not None else ''
            
            title_el = entry.find('atom:title', ns)
            title = title_el.text if title_el is not None else ''
            
            published_el = entry.find('atom:published', ns)
            published = published_el.text if published_el is not None else ''
            formatted_date = format_date(published)
            
            media_group = entry.find('media:group', ns)
            desc_el = media_group.find('media:description', ns) if media_group is not None else None
            desc = desc_el.text if desc_el is not None else ''
            desc_clean = clean_excerpt(desc, 130)
            
            thumb_el = media_group.find('media:thumbnail', ns) if media_group is not None else None
            thumb = thumb_el.get('url') if thumb_el is not None else f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
            
            videos.append({
                'id': video_id,
                'title': title,
                'date': published,
                'formattedDate': formatted_date,
                'description': desc_clean,
                'thumbnail': thumb
            })
        return videos
    except Exception as e:
        print(f"Warning: Could not fetch YouTube videos: {e}")
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
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 24px;
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
  padding: 80px 0 60px;
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
  font-size: 3.5rem;
  margin-bottom: 16px;
  background: var(--accent-gradient);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  letter-spacing: -0.05em;
  line-height: 1.15;
}
.hero p {
  color: var(--text-secondary);
  font-size: 1.25rem;
  max-width: 600px;
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

/* Tag Filters */
.tags-wrapper {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
}
.filter-tag {
  background-color: var(--bg-secondary);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  padding: 7px 16px;
  border-radius: 20px;
  font-size: 0.85rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}
.filter-tag:hover {
  border-color: var(--accent-color);
  color: var(--accent-color);
}
.filter-tag.active {
  background: var(--accent-gradient);
  border-color: transparent;
  color: white;
  box-shadow: 0 4px 10px rgba(99, 102, 241, 0.25);
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
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 30px;
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

/* Pagination */
.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 10px;
  margin-bottom: 80px;
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
  max-height: 90%;
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

  // Videos Grid logic
  const videosGrid = document.getElementById('videos-grid');
  if (videosGrid) {
    initVideosPage();
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

function initHomePage() {
  try {
    allPosts = window.postsData || [];
    filteredPosts = [...allPosts];
    
    // Bind search and filter events
    const searchBox = document.getElementById('search-box');
    if (searchBox) {
      searchBox.value = ''; // Clear search box on reload
      searchBox.addEventListener('input', (e) => {
        searchQuery = e.target.value.toLowerCase().trim();
        currentPage = 1;

        const clearIcon = document.getElementById('clear-search-icon');
        if (clearIcon) {
          clearIcon.style.display = searchQuery ? 'block' : 'none';
        }

        applyFilters();
      });
    }

    renderTags();
    renderPostsGrid();
  } catch (error) {
    console.error('Failed to load posts database:', error);
    document.getElementById('posts-grid').innerHTML = '<p style="grid-column: 1/-1; text-align: center; color: var(--text-muted);">Failed to load posts.</p>';
  }
}

function renderTags() {
  const tagsWrapper = document.getElementById('tags-wrapper');
  if (!tagsWrapper) return;

  const tagCounts = {};
  allPosts.forEach(post => {
    if (post.tags) {
      post.tags.forEach(tag => {
        tagCounts[tag] = (tagCounts[tag] || 0) + 1;
      });
    }
  });

  // Sort tags by frequency
  const sortedTags = Object.keys(tagCounts).sort((a, b) => tagCounts[b] - tagCounts[a]).slice(0, 15);

  tagsWrapper.innerHTML = `
    <button class="filter-tag ${activeTag === null ? 'active' : ''}" onclick="selectTag(null)">All Posts</button>
  `;

  sortedTags.forEach(tag => {
    tagsWrapper.innerHTML += `
      <button class="filter-tag ${activeTag === tag ? 'active' : ''}" onclick="selectTag('${tag}')">${tag} (${tagCounts[tag]})</button>
    `;
  });
}

function selectTag(tag) {
  activeTag = tag;
  currentPage = 1;
  
  // Update UI active state
  const tagsWrapper = document.getElementById('tags-wrapper');
  const buttons = tagsWrapper.querySelectorAll('.filter-tag');
  buttons.forEach(btn => {
    const isAll = tag === null && btn.textContent.includes('All Posts');
    const isMatch = tag !== null && btn.textContent.startsWith(tag + ' ');
    if (isAll || isMatch) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });
  
  applyFilters();
}

function applyFilters() {
  filteredPosts = allPosts.filter(post => {
    const matchesTag = !activeTag || (post.tags && post.tags.includes(activeTag));
    const matchesSearch = !searchQuery || 
                          post.title.toLowerCase().includes(searchQuery) ||
                          post.excerpt.toLowerCase().includes(searchQuery) ||
                          (post.tags && post.tags.some(t => t.toLowerCase().includes(searchQuery)));
    return matchesTag && matchesSearch;
  });

  renderPostsGrid();
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
  
  if (!searchQuery && !activeTag) {
    if (infoBar) infoBar.remove();
    return;
  }

  if (!infoBar) {
    infoBar = document.createElement('div');
    infoBar.id = 'search-info-bar';
    infoBar.className = 'search-info-bar';
    filterSection.insertAdjacentElement('afterend', infoBar);
  }

  let text = `Found <strong>${totalResults}</strong> article${totalResults === 1 ? '' : 's'}`;
  if (searchQuery) {
    text += ` matching "<strong>${escapeHtml(searchQuery)}</strong>"`;
  }
  if (activeTag) {
    text += ` in tag "<strong>${escapeHtml(activeTag)}</strong>"`;
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
  searchQuery = '';
  activeTag = null;
  currentPage = 1;
  
  const tagsWrapper = document.getElementById('tags-wrapper');
  if (tagsWrapper) {
    const buttons = tagsWrapper.querySelectorAll('.filter-tag');
    buttons.forEach(btn => {
      if (btn.textContent.includes('All Posts')) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });
  }

  const clearIcon = document.getElementById('clear-search-icon');
  if (clearIcon) clearIcon.style.display = 'none';

  applyFilters();
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

  let displayPosts = [];
  if (isInitialState) {
    const featuredPost = filteredPosts[0];
    const coverImageHtml = featuredPost.coverImage 
      ? `<img class="featured-image" src="${featuredPost.coverImage}" alt="${featuredPost.title}" loading="eager">`
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
          </div>
          <h2 class="featured-title"><a href=".${featuredPost.url}">${featuredPost.title}</a></h2>
          <p class="featured-excerpt">${featuredPost.excerpt}</p>
          <div class="card-tags">
            ${tagsHtml}
          </div>
        </div>
      </article>
    `;

    displayPosts = filteredPosts.slice(1, postsPerPage);
  } else {
    const startIndex = (currentPage - 1) * postsPerPage;
    const endIndex = startIndex + postsPerPage;
    displayPosts = filteredPosts.slice(startIndex, endIndex);
  }

  postsHtml += displayPosts.map((post, idx) => {
    const displayTitle = searchQuery ? highlightText(post.title, searchQuery) : post.title;
    const displayExcerpt = searchQuery ? highlightText(post.excerpt, searchQuery) : post.excerpt;

    const isBelowFold = (currentPage > 1 || idx > 2);
    const lazyClass = isBelowFold ? 'post-card-lazy' : '';
    const loadingAttr = isBelowFold ? 'lazy' : 'eager';

    const coverImageHtml = post.coverImage 
      ? `<img class="card-image" src="${post.coverImage}" alt="${post.title}" loading="${loadingAttr}" decoding="async">`
      : `<div class="card-image-fallback">${post.title.slice(0, 2).toUpperCase()}</div>`;

    const tagsHtml = post.tags 
      ? post.tags.slice(0, 3).map(tag => `<span class="card-tag">${tag}</span>`).join('')
      : '';

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
      
      // Ensure we display an image element in the lightbox rather than an iframe
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

// Videos Page Initialization
function initVideosPage() {
  const videosGrid = document.getElementById('videos-grid');
  if (!videosGrid) return;
  
  const allVideos = window.videosData || [];
  if (allVideos.length === 0) {
    videosGrid.innerHTML = '<p style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 40px 0;">No videos found. Click back later!</p>';
    return;
  }
  
  videosGrid.innerHTML = allVideos.map(video => {
    return `
      <article class="post-card video-card" onclick="playVideo('${video.id}')" style="cursor: pointer;">
        <div class="card-image-wrapper">
          <img class="card-image" src="${video.thumbnail}" alt="${video.title}" loading="lazy">
          <div class="play-overlay">
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path d="M8 5v14l11-7z"/>
            </svg>
          </div>
        </div>
        <div class="card-content">
          <div class="card-meta">
            <span>
              <svg fill="currentColor" viewBox="0 0 24 24"><path d="M19 4h-1V2h-2v2H8V2H6v2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 16H5V10h14v10zm0-12H5V6h14v2z"/></svg>
              ${video.formattedDate}
            </span>
          </div>
          <h2 class="card-title" style="font-size: 1.15rem; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">${video.title}</h2>
          <p class="card-excerpt" style="font-size: 0.85rem; margin-bottom: 0;">${video.description}</p>
        </div>
      </article>
    `;
  }).join('');
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

  // Clear previous lightbox elements to display video
  lightbox.innerHTML = `
    <button class="lightbox-close" aria-label="Close lightbox">&times;</button>
    <div class="lightbox-video-container">
      <iframe class="lightbox-video" src="https://www.youtube.com/embed/${videoId}?autoplay=1" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen></iframe>
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
      lightbox.innerHTML = ''; // Clear elements
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
"""

INDEX_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="description" content="puru world official - A blog on everyday need daily. Exploring technology, lifeskills, travel, and more.">
  <title>puru world official</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="./style.css">
  <script src="./posts-metadata.js"></script>
  <script src="./main.js" defer></script>
</head>
<body>
  <header>
    <div class="container header-content">
      <div class="logo">
        <svg style="width: 28px; height: 28px; fill: url(#accentGradient);" viewBox="0 0 24 24">
          <defs>
            <linearGradient id="accentGradient" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#8b5cf6" />
              <stop offset="100%" stop-color="#6366f1" />
            </linearGradient>
          </defs>
          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 17h-2v-2h2v2zm2.07-7.75l-.9.92C13.45 12.9 13 13.5 13 15h-2v-.5c0-1.1.45-2.1 1.17-2.83l1.24-1.26c.37-.36.59-.86.59-1.41 0-1.1-.9-2-2-2s-2 .9-2 2H7c0-2.76 2.24-5 5-5s5 2.24 5 5c0 1.04-.42 1.99-1.07 2.75z"/>
        </svg>
        Puru's Blog
      </div>
      <nav class="nav-links">
        <a href="./index.html" class="nav-link">Home</a>
        <a href="./p/videos.html" class="nav-link">Videos</a>
        <a href="./p/subscribe-today.html" class="nav-link">Subscribe</a>
        <button class="theme-toggle-btn" aria-label="Toggle dark mode" id="theme-toggle">
          <svg class="moon-icon" fill="currentColor" viewBox="0 0 20 20"><path d="M17.293a8 8 0 01-10.586-10.586 8.001 8.001 0 1010.586 10.586z"></path></svg>
          <svg class="sun-icon" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z" clip-rule="evenodd"></path></svg>
        </button>
      </nav>
    </div>
  </header>

  <main class="container">
    <section class="hero">
      <div class="hero-bg-blobs">
        <div class="hero-blob hero-blob-1"></div>
        <div class="hero-blob hero-blob-2"></div>
      </div>
      <h1>puru world official</h1>
      <p>A beautiful destination for regular updates, lifestyle guides, technical tutorials, and emotional intelligence strategies.</p>
      <div class="blog-stats">
        <span>
          <svg fill="currentColor" viewBox="0 0 24 24"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z"/></svg>
          1,500+ Articles
        </span>
        <span>
          <svg fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 17h-2v-2h2v2zm2.07-7.75l-.9.92C13.45 12.9 13 13.5 13 15h-2v-.5c0-1.1.45-2.1 1.17-2.83l1.24-1.26c.37-.36.59-.86.59-1.41 0-1.1-.9-2-2-2s-2 .9-2 2H7c0-2.76 2.24-5 5-5s5 2.24 5 5c0 1.04-.42 1.99-1.07 2.75z"/></svg>
          5+ Categories
        </span>
      </div>
    </section>

    <section class="search-filter-section" id="search-filter-section">
      <div class="search-box-wrapper">
        <span class="search-icon">
          <svg fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
        </span>
        <input type="text" id="search-box" class="search-box" placeholder="Search across 1,500+ blog articles...">
        <span class="clear-icon" id="clear-search-icon" onclick="resetFilters()">&times;</span>
      </div>

      <div class="tags-wrapper" id="tags-wrapper">
        <!-- Tags will load dynamically -->
      </div>
    </section>

    <div class="posts-grid" id="posts-grid">
      <!-- Posts will render dynamically -->
    </div>

    <div class="pagination" id="pagination">
      <!-- Pagination will render dynamically -->
    </div>
  </main>

  <footer>
    <div class="container">
      <p>&copy; 2026 puru world official. All rights reserved.</p>
      <p>Migrated from Blogger to Static HTML Site.</p>
    </div>
  </footer>
</body>
</html>
"""

VIDEOS_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="description" content="Watch my latest video updates, gaming livestreams, and tutorials from Puru World.">
  <title>Videos - puru world official</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="../style.css">
  <script src="../videos-metadata.js"></script>
  <script src="../main.js" defer></script>
</head>
<body>
  <header>
    <div class="container header-content">
      <div class="logo">
        <a href="../index.html" style="background: var(--accent-gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent; display: flex; align-items: center; gap: 8px; font-weight: 800;">
          <svg style="width: 28px; height: 28px; fill: url(#accentGradientVideos);" viewBox="0 0 24 24">
            <defs>
              <linearGradient id="accentGradientVideos" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stop-color="#8b5cf6" />
                <stop offset="100%" stop-color="#6366f1" />
              </linearGradient>
            </defs>
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 17h-2v-2h2v2zm2.07-7.75l-.9.92C13.45 12.9 13 13.5 13 15h-2v-.5c0-1.1.45-2.1 1.17-2.83l1.24-1.26c.37-.36.59-.86.59-1.41 0-1.1-.9-2-2-2s-2 .9-2 2H7c0-2.76 2.24-5 5-5s5 2.24 5 5c0 1.04-.42 1.99-1.07 2.75z"/>
          </svg>
          Puru's Blog
        </a>
      </div>
      <nav class="nav-links">
        <a href="../index.html" class="nav-link">Home</a>
        <a href="../p/videos.html" class="nav-link">Videos</a>
        <a href="../p/subscribe-today.html" class="nav-link">Subscribe</a>
        <button class="theme-toggle-btn" aria-label="Toggle dark mode" id="theme-toggle">
          <svg class="moon-icon" fill="currentColor" viewBox="0 0 20 20"><path d="M17.293a8 8 0 01-10.586-10.586 8.001 8.001 0 1010.586 10.586z"></path></svg>
          <svg class="sun-icon" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z" clip-rule="evenodd"></path></svg>
        </button>
      </nav>
    </div>
  </header>

  <main class="container" style="padding-top: 40px; padding-bottom: 80px;">
    <section class="hero" style="padding: 40px 0;">
      <div class="hero-bg-blobs">
        <div class="hero-blob hero-blob-1"></div>
        <div class="hero-blob hero-blob-2"></div>
      </div>
      <h1>YouTube Video Library</h1>
      <p>Explore the latest gameplay uploads, livestreams, guides, and walkthroughs from Puru World.</p>
    </section>

    <div class="posts-grid" id="videos-grid">
      <!-- Videos will load dynamically -->
    </div>
  </main>

  <footer>
    <div class="container">
      <p>&copy; 2026 puru world official. All rights reserved.</p>
      <p>Migrated from Blogger to Static HTML Site.</p>
    </div>
  </footer>
</body>
</html>
"""

def make_post_html(post_title, post_date, post_tags, post_content, read_time, cover_image, rel_path, related_posts_html):
  tags_html = "".join([f'<span class="card-tag">{t}</span>' for t in post_tags])
  header_tags_html = "".join([f'<span class="filter-tag" style="cursor:default">{t}</span>' for t in post_tags])
  
  cover_image_html = ""
  if cover_image:
    cover_image_html = f'<img class="post-hero-image" src="{cover_image}" alt="{post_title}" loading="eager" decoding="async">'

  return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="description" content="{clean_excerpt(post_content, 150)}">
  <title>{post_title} - puru world official</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="{rel_path}style.css">
  <script src="{rel_path}main.js" defer></script>
</head>
<body>
  <header>
    <div class="container header-content">
      <div class="logo">
        <a href="{rel_path}index.html" style="background: var(--accent-gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent; display: flex; align-items: center; gap: 8px; font-weight: 800;">
          <svg style="width: 28px; height: 28px; fill: url(#accentGradientDetail);" viewBox="0 0 24 24">
            <defs>
              <linearGradient id="accentGradientDetail" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stop-color="#8b5cf6" />
                <stop offset="100%" stop-color="#6366f1" />
              </linearGradient>
            </defs>
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 17h-2v-2h2v2zm2.07-7.75l-.9.92C13.45 12.9 13 13.5 13 15h-2v-.5c0-1.1.45-2.1 1.17-2.83l1.24-1.26c.37-.36.59-.86.59-1.41 0-1.1-.9-2-2-2s-2 .9-2 2H7c0-2.76 2.24-5 5-5s5 2.24 5 5c0 1.04-.42 1.99-1.07 2.75z"/>
          </svg>
          Puru's Blog
        </a>
      </div>
      <nav class="nav-links">
        <a href="{rel_path}index.html" class="nav-link">Home</a>
        <a href="{rel_path}p/videos.html" class="nav-link">Videos</a>
        <a href="{rel_path}p/subscribe-today.html" class="nav-link">Subscribe</a>
        <button class="theme-toggle-btn" aria-label="Toggle dark mode" id="theme-toggle">
          <svg class="moon-icon" fill="currentColor" viewBox="0 0 20 20"><path d="M17.293a8 8 0 01-10.586-10.586 8.001 8.001 0 1010.586 10.586z"></path></svg>
          <svg class="sun-icon" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z" clip-rule="evenodd"></path></svg>
        </button>
      </nav>
      <div class="scroll-progress-container">
        <div class="scroll-progress-bar"></div>
      </div>
    </div>
  </header>

  <main class="container post-layout">
    <div class="back-btn-wrapper">
      <a href="{rel_path}index.html" class="back-btn">
        <svg fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18"></path></svg>
        Back to Home
      </a>
    </div>

    <article>
      <div class="post-header">
        <h1 class="post-header-title">{post_title}</h1>
        <div class="post-header-meta">
          <span>
            <svg fill="currentColor" viewBox="0 0 24 24"><path d="M19 4h-1V2h-2v2H8V2H6v2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 16H5V10h14v10zm0-12H5V6h14v2z"/></svg>
            {post_date}
          </span>
          <span>
            <svg fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z"/></svg>
            {read_time} min read
          </span>
        </div>
        <div class="post-header-tags">
          {header_tags_html}
        </div>
      </div>

      {cover_image_html}

      <div class="post-content-container">
        <div class="post-main-content">
          {post_content}
        </div>
        
        <aside class="post-sidebar">
          <div class="sidebar-widget" id="toc-widget" style="display: none;">
            <h3>Table of Contents</h3>
            <nav class="toc-links" id="toc-links">
              <!-- TOC links will load dynamically -->
            </nav>
          </div>
          
          <div class="sidebar-widget">
            <h3>Share this Article</h3>
            <div class="share-links">
              <button class="share-btn" onclick="sharePost('twitter', '{post_title}')">
                <svg fill="currentColor" viewBox="0 0 24 24"><path d="M22.46 6c-.77.35-1.6.58-2.46.69.88-.53 1.56-1.37 1.88-2.38-.83.5-1.75.85-2.72 1.05C18.37 4.5 17.26 4 16 4c-2.35 0-4.27 1.92-4.27 4.29 0 .34.04.67.11.98C8.28 9.09 5.11 7.38 3 4.79c-.37.63-.58 1.37-.58 2.15 0 1.49.75 2.81 1.91 3.56-.71 0-1.37-.2-1.95-.5v.03c0 2.08 1.48 3.82 3.44 4.21a4.2 4.2 0 0 1-1.93.07 4.28 4.28 0 0 0 4 2.98 8.52 8.52 0 0 1-5.3 1.83c-.35 0-.69-.02-1.02-.06C3.44 20.29 5.7 21 8.12 21 16 21 20.33 14.5 20.33 8.8c0-.19 0-.37-.01-.56.84-.6 1.56-1.36 2.14-2.24z"/></svg>
                Twitter / X
              </button>
              <button class="share-btn" onclick="sharePost('facebook', '{post_title}')">
                <svg fill="currentColor" viewBox="0 0 24 24"><path d="M22 12c0-5.52-4.48-10-10-10S2 6.48 2 12c0 4.84 3.44 8.87 8 9.8V15H8v-3h2V9.5C10 7.57 11.57 6 13.5 6H16v3h-2c-.55 0-1 .45-1 1v2h3v3h-3v6.95c4.56-.93 8-4.96 8-9.75z"/></svg>
                Facebook
              </button>
              <button class="share-btn" onclick="sharePost('linkedin', '{post_title}')">
                <svg fill="currentColor" viewBox="0 0 24 24"><path d="M19 3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h14m-.5 15.5v-5.3a3.26 3.26 0 0 0-3.26-3.26c-.85 0-1.84.52-2.32 1.3v-1.11h-2.79v8.37h2.79v-4.93c0-.77.62-1.4 1.39-1.4a1.4 1.4 0 0 1 1.4 1.4v4.93h2.79M6.88 8.56a1.68 1.68 0 0 0 1.68-1.68c0-.93-.75-1.69-1.68-1.69a1.69 1.69 0 0 0-1.69 1.69c0 .93.76 1.68 1.69 1.68m1.39 9.94v-8.37H5.5v8.37h2.77z"/></svg>
                LinkedIn
              </button>
              <button class="share-btn" onclick="sharePost('copy', '{post_title}')">
                <svg fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 002-2M8 5a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3"></path></svg>
                Copy Link
              </button>
            </div>
          </div>
        </aside>
      </div>
    </article>

    {related_posts_html}
  </main>

  <footer>
    <div class="container">
      <p>&copy; 2026 puru world official. All rights reserved.</p>
      <p>Migrated from Blogger to Static HTML Site.</p>
    </div>
  </footer>
</body>
</html>
"""

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
    cover_image_html = f'<img class="card-image" src="{r["coverImage"]}" alt="{r["title"]}" loading="lazy" decoding="async">' if r["coverImage"] else f'<div class="card-image-fallback">{r["title"][:2].upper()}</div>'
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
        tags.append(term)
        
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
  
  with open(os.path.join(output_dir, 'index.html'), 'w', encoding='utf-8') as f:
    f.write(INDEX_HTML_TEMPLATE)
  print("Generated index.html")
  
  # Fetch YouTube videos and write metadata
  print("Fetching YouTube videos...")
  videos = fetch_youtube_videos("UCFoVp5Va975oQQpevpQErQQ")
  with open(os.path.join(output_dir, 'videos-metadata.js'), 'w', encoding='utf-8') as f:
    f.write("window.videosData = ")
    json.dump(videos, f, ensure_ascii=False, indent=2)
    f.write(";")
  print(f"Generated {len(videos)} videos in videos-metadata.js")
  
  # Write p/videos.html page
  videos_page_dir = os.path.join(output_dir, 'p')
  os.makedirs(videos_page_dir, exist_ok=True)
  with open(os.path.join(videos_page_dir, 'videos.html'), 'w', encoding='utf-8') as f:
    f.write(VIDEOS_HTML_TEMPLATE)
  print("Generated p/videos.html")
  
  print("Writing post HTML files...")
  for i, post in enumerate(raw_posts):
    content_rewritten = rewrite_internal_links(post['content'], post['depth'])
    content_sanitized = sanitize_blogger_html(content_rewritten)
    related_html = generate_related_posts_section(post, posts_metadata, post['rel_path'])
    
    post_html = make_post_html(
      post_title=post['title'],
      post_date=post['formattedDate'],
      post_tags=post['tags'],
      post_content=content_sanitized,
      read_time=post['readTime'],
      cover_image=post['coverImage'],
      rel_path=post['rel_path'],
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
    content_sanitized = sanitize_blogger_html(content_rewritten)
    
    page_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="description" content="{clean_excerpt(page['content'], 150)}">
  <title>{page['title']} - puru world official</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="{page['rel_path']}style.css">
  <script src="{page['rel_path']}main.js" defer></script>
</head>
<body>
  <header>
    <div class="container header-content">
      <div class="logo">
        <a href="{page['rel_path']}index.html" style="background: var(--accent-gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent; display: flex; align-items: center; gap: 8px; font-weight: 800;">
          <svg style="width: 28px; height: 28px; fill: url(#accentGradientPage);" viewBox="0 0 24 24">
            <defs>
              <linearGradient id="accentGradientPage" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stop-color="#8b5cf6" />
                <stop offset="100%" stop-color="#6366f1" />
              </linearGradient>
            </defs>
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 17h-2v-2h2v2zm2.07-7.75l-.9.92C13.45 12.9 13 13.5 13 15h-2v-.5c0-1.1.45-2.1 1.17-2.83l1.24-1.26c.37-.36.59-.86.59-1.41 0-1.1-.9-2-2-2s-2 .9-2 2H7c0-2.76 2.24-5 5-5s5 2.24 5 5c0 1.04-.42 1.99-1.07 2.75z"/>
          </svg>
          Puru's Blog
        </a>
      </div>
      <nav class="nav-links">
        <a href="{page['rel_path']}index.html" class="nav-link">Home</a>
        <a href="{page['rel_path']}p/videos.html" class="nav-link">Videos</a>
        <a href="{page['rel_path']}p/subscribe-today.html" class="nav-link">Subscribe</a>
        <button class="theme-toggle-btn" aria-label="Toggle dark mode" id="theme-toggle">
          <svg class="moon-icon" fill="currentColor" viewBox="0 0 20 20"><path d="M17.293a8 8 0 01-10.586-10.586 8.001 8.001 0 1010.586 10.586z"></path></svg>
          <svg class="sun-icon" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z" clip-rule="evenodd"></path></svg>
        </button>
      </nav>
    </div>
  </header>

  <main class="container post-layout">
    <div class="back-btn-wrapper">
      <a href="{page['rel_path']}index.html" class="back-btn">
        <svg fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18"></path></svg>
        Back to Home
      </a>
    </div>

    <article>
      <div class="post-header">
        <h1 class="post-header-title">{page['title']}</h1>
      </div>

      <div class="post-main-content" style="max-width: 800px; margin: 0 auto;">
        {content_sanitized}
      </div>
    </article>
  </main>

  <footer>
    <div class="container">
      <p>&copy; 2026 puru world official. All rights reserved.</p>
      <p>Migrated from Blogger to Static HTML Site.</p>
    </div>
  </footer>
</body>
</html>
"""
    dest_path = os.path.join(output_dir, page['filename'].lstrip('/'))
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    with open(dest_path, 'w', encoding='utf-8') as f:
      f.write(page_html)
  
  print(f"Generated {len(raw_pages)} pages.")
  print("Migration completed successfully!")

if __name__ == '__main__':
  main()
