// Global seeding utility functions
function hashCode(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash;
  }
  return hash;
}

function seededRandom(seed) {
  const x = Math.sin(seed++) * 10000;
  return x - Math.floor(x);
}

function getRealTrackedLogs() {
  try {
    return JSON.parse(localStorage.getItem('puruworld_analytics') || '[]');
  } catch(e) {
    return [];
  }
}

// Theme toggling and state synchronization
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
    window.activeAppCategory = 'all';
    renderAppsGrid();
    
    // Category filtering click handlers
    const filterButtons = document.querySelectorAll('.app-filter-btn');
    filterButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        filterButtons.forEach(b => {
          b.classList.remove('active');
          b.style.background = 'rgba(255,255,255,0.05)';
          b.style.borderColor = 'var(--border-color)';
          b.style.color = 'var(--text-primary)';
          b.style.fontWeight = '500';
        });
        btn.classList.add('active');
        btn.style.background = 'var(--accent-gradient)';
        btn.style.borderColor = 'transparent';
        btn.style.color = 'white';
        btn.style.fontWeight = '600';
        
        window.activeAppCategory = btn.getAttribute('data-category');
        renderAppsGrid();
      });
    });
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
    applyFilters(); // Trigger initial render of article list on entry
  } catch (error) {
    console.error('Failed to load database:', error);
  }
}

const allApps = [
  {
    title: "Coin Flipper",
    description: "Flip a virtual coin with realistic 3D jump physics. Perfect for quick decision-making and random draws.",
    url: "p/flip-coin.html",
    icon: "monetization_on",
    tag: "Casual Game",
    category: "game",
    isExternal: false
  },
  {
    title: "Tic Tac Toe",
    description: "Play the classic Tic Tac Toe game with a friend or challenge the AI bot.",
    url: "p/tic-tac-toe.html",
    icon: "grid_on",
    tag: "Classic Game",
    category: "game",
    isExternal: false
  },
  {
    title: "Spin the Bottle",
    description: "An interactive spin-the-bottle party game with smooth CSS rotation physics.",
    url: "p/spin-bottle.html",
    icon: "cached",
    tag: "Party Game",
    category: "game",
    isExternal: false
  },
  {
    title: "JSON Formatter",
    description: "A developer tool to format, validate, and beautify raw JSON strings easily.",
    url: "p/json-formatter.html",
    icon: "code",
    tag: "Utility Tool",
    category: "tool",
    isExternal: false
  },
  {
    title: "JSON to Apex Converter",
    description: "Convert raw JSON payloads directly into Salesforce Apex class structures.",
    url: "https://json2apex.com",
    icon: "cloud_queue",
    tag: "External Tool",
    category: "tool",
    isExternal: true
  },
  {
    title: "Python Visualizer",
    description: "Visualize python execution flows and trace memory stack frames in real-time.",
    url: "pythonVisualizer/index.html",
    icon: "visibility",
    tag: "Interactive Tool",
    category: "tool",
    isExternal: false
  },
  {
    title: "SFDX Data Dictionary",
    description: "Convert Salesforce SFDX metadata/object definitions directly into formatted Excel sheets.",
    url: "SFMetaToExcel/index.html",
    icon: "table_chart",
    tag: "Salesforce Tool",
    category: "tool",
    isExternal: false
  },
  {
    title: "Local Barter & Swap",
    description: "Post listings and swap goods or services locally without money on this decentralized barter platform.",
    url: "Barter-platform/index.html",
    icon: "swap_horiz",
    tag: "Web App",
    category: "tool",
    isExternal: false
  },
  {
    title: "Orbit Drop",
    description: "Challenge friends to a multiplayer space-themed physics arcade game powered by Phaser and PeerJS.",
    url: "orbit-drop/index.html",
    icon: "rocket_launch",
    tag: "Arcade Game",
    category: "game",
    isExternal: false
  },
  {
    title: "Image to PDF Converter",
    description: "Convert multiple image files (JPG, PNG) into a single optimized PDF document in your browser.",
    url: "Image2Pdf/index.html",
    icon: "picture_as_pdf",
    tag: "Utility Tool",
    category: "tool",
    isExternal: false
  },
  {
    title: "Universal Text Converter",
    description: "Convert text formats (XML, CSV, JSON, XLSX, YAML) seamlessly in your browser with automated structure parsing.",
    url: "universaltextconverter/index.html",
    icon: "transform",
    tag: "Developer Tool",
    category: "tool",
    isExternal: false
  }
];

function renderAppsGrid() {
  const grid = document.getElementById('apps-grid');
  if (!grid) return;
  
  const filteredApps = allApps.filter(app => {
    if (!window.activeAppCategory || window.activeAppCategory === 'all') return true;
    return app.category === window.activeAppCategory;
  });

  grid.innerHTML = filteredApps.map(app => {
    const targetAttr = app.isExternal ? 'target="_blank"' : '';
    
    // Resolve URL depending on relative path depth prefix
    let resolvedUrl = app.url;
    if (!app.isExternal && !app.url.startsWith('http')) {
      resolvedUrl = window.relPathDepth + app.url.replace(/^\.\//, '');
    }

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
          <h2 class="card-title" style="margin: 0 0 10px 0;"><a href="${resolvedUrl}" ${targetAttr} style="color: var(--text-primary); text-decoration: none; font-family: 'Outfit', sans-serif;">${app.title}</a></h2>
          <p class="card-excerpt" style="font-size: 0.9rem; color: var(--text-secondary); line-height: 1.5; margin-bottom: 20px; flex-grow: 1;">${app.description}</p>
          <div style="margin-top: auto; display: flex; justify-content: space-between; align-items: center;">
            <a href="${resolvedUrl}" ${targetAttr} class="back-btn" style="padding: 6px 12px; font-size: 0.85rem; border-color: var(--accent-color); color: var(--accent-color); font-weight: 600; text-decoration: none; display: inline-flex; align-items: center; gap: 4px; border-radius: 6px; border: 1px solid var(--accent-color); transition: all 0.2s;">
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
    const escapedQuery = query.replace(/[-\/\^$*+?.()|[\]{}]/g, '\$&');
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
          <div class="card-meta" style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap; font-size: 0.8rem; color: var(--text-muted);">
            <span>${featuredPost.formattedDate}</span>
            <span style="opacity: 0.5;">•</span>
            <span>${featuredPost.readTime} min read</span>
            <span style="opacity: 0.5;">•</span>
            <span style="color: var(--accent-color); font-weight: 600;">${getPostViews(featuredPost).toLocaleString()} views</span>
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
          <div class="card-meta" style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap; font-size: 0.8rem; color: var(--text-muted);">
            <span>${post.formattedDate}</span>
            <span style="opacity: 0.5;">•</span>
            <span>${post.readTime} min read</span>
            <span style="opacity: 0.5;">•</span>
            <span style="color: var(--accent-color); font-weight: 600;">${getPostViews(post).toLocaleString()} views</span>
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
