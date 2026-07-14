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
  const isStandaloneVideosPage = videosGrid && !document.getElementById('posts-grid');
  if (isStandaloneVideosPage) {
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

let allVideos = [];
let filteredVideos = [];
let currentVideoPage = 1;
const videosPerPage = 12;
let activeVideoCategory = 'All';
let activeTab = 'blog';

function initHomePage() {
  try {
    allPosts = window.postsData || [];
    filteredPosts = [...allPosts];
    
    allVideos = window.videosData || [];
    filteredVideos = [...allVideos];
    
    // Bind search and filter events
    const searchBox = document.getElementById('search-box');
    if (searchBox) {
      searchBox.value = ''; // Clear search box on reload
      searchBox.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase().trim();
        
        if (activeTab === 'blog') {
          searchQuery = query;
          currentPage = 1;
          applyFilters();
        } else {
          currentVideoPage = 1;
          applyVideoFilters();
        }

        const clearIcon = document.getElementById('clear-search-icon');
        if (clearIcon) {
          clearIcon.style.display = query ? 'block' : 'none';
        }
      });
    }

    renderTags();
    renderVideoCategories();
    
    // Check URL parameters for active tab
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('tab') === 'videos') {
      switchTab('videos');
    } else {
      switchTab('blog');
    }
  } catch (error) {
    console.error('Failed to load databases:', error);
  }
}

function switchTab(tab) {
  activeTab = tab;
  
  const tabBlog = document.getElementById('tab-blog');
  const tabVideos = document.getElementById('tab-videos');
  const blogPageLayout = document.getElementById('blog-page-layout');
  const videosPageLayout = document.getElementById('videos-page-layout');
  const pagination = document.getElementById('pagination');
  const videosPagination = document.getElementById('videos-pagination');
  const searchBox = document.getElementById('search-box');
  
  if (!tabBlog || !tabVideos) return;
  
  if (tab === 'blog') {
    tabBlog.classList.add('active');
    tabVideos.classList.remove('active');
    if (blogPageLayout) blogPageLayout.style.display = 'grid';
    if (videosPageLayout) videosPageLayout.style.display = 'none';
    if (pagination) pagination.style.display = 'flex';
    if (videosPagination) videosPagination.style.display = 'none';
    if (searchBox) {
      searchBox.placeholder = 'Search across 1,500+ blog articles...';
      searchBox.value = searchQuery;
    }
    applyFilters();
  } else {
    tabBlog.classList.remove('active');
    tabVideos.classList.add('active');
    if (blogPageLayout) blogPageLayout.style.display = 'none';
    if (videosPageLayout) videosPageLayout.style.display = 'grid';
    if (pagination) pagination.style.display = 'none';
    if (videosPagination) videosPagination.style.display = 'flex';
    if (searchBox) {
      searchBox.placeholder = 'Search YouTube video library...';
      searchBox.value = '';
    }
    applyVideoFilters();
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
        All Articles
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

function applyVideoFilters() {
  const videosGrid = document.getElementById('videos-grid');
  const videosPagination = document.getElementById('videos-pagination');
  if (!videosGrid) return;

  const query = document.getElementById('search-box')?.value.toLowerCase().trim() || '';

  filteredVideos = allVideos.filter(video => {
    const matchesCategory = activeVideoCategory === 'All' || video.category === activeVideoCategory;
    const matchesSearch = !query || 
                          video.title.toLowerCase().includes(query) ||
                          (video.views && video.views.toLowerCase().includes(query)) ||
                          (video.timeAgo && video.timeAgo.toLowerCase().includes(query));
    return matchesCategory && matchesSearch;
  });

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
              <svg fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 14.5v-9l6 4.5-6 4.5z"/></svg>
              ${video.views || '0 views'}
            </span>
            <span>
              <svg fill="currentColor" viewBox="0 0 24 24"><path d="M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 2 22 6.48 22 12s-4.48-10-10-10zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z"/></svg>
              ${video.timeAgo || 'recent'}
            </span>
          </div>
          <h2 class="card-title" style="font-size: 1.15rem; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; margin-bottom: 0;">${displayTitle}</h2>
          
          <a href="https://www.youtube.com/@PuruWorld?sub_confirmation=1" target="_blank" onclick="event.stopPropagation();" class="video-subscribe-btn">
            <svg viewBox="0 0 24 24" style="width:14px; height:14px; fill:currentColor; margin-right:4px;"><path d="M23.498 6.163a3.003 3.003 0 0 0-2.11-2.11C19.517 3.545 12 3.545 12 3.545s-7.517 0-9.388.508a3.003 3.003 0 0 0-2.11 2.11C0 8.033 0 12 0 12s0 3.967.502 5.837a3.003 3.003 0 0 0 2.11 2.11c1.871.508 9.388.508 9.388.508s7.517 0 9.388-.508a3.003 3.003 0 0 0 2.11-2.11C24 15.967 24 12 24 12s0-3.967-.502-5.837zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/></svg>
            Subscribe
          </a>
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

  // Modal with autoplay, fullscreen capabilities, and Subscribe shortcut inside lightbox footer
  lightbox.innerHTML = `
    <button class="lightbox-close" aria-label="Close lightbox">&times;</button>
    <div class="lightbox-video-container">
      <iframe class="lightbox-video" src="https://www.youtube.com/embed/${videoId}?autoplay=1" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen webkitallowfullscreen mozallowfullscreen allow="autoplay; fullscreen"></iframe>
    </div>
    <div class="lightbox-video-footer" style="margin-top: 15px; display: flex; justify-content: space-between; align-items: center; width: 85%; max-width: 800px; color: white;">
      <span id="lightbox-video-title" style="font-family:'Outfit', sans-serif; font-size:1.15rem; font-weight:600; text-overflow:ellipsis; overflow:hidden; white-space:nowrap; max-width:70%; text-align:left;">${videoTitle}</span>
      <a href="https://www.youtube.com/@PuruWorld?sub_confirmation=1" target="_blank" class="modal-subscribe-btn" style="background-color:#ef4444; color:white; padding:8px 16px; border-radius:8px; font-weight:700; font-size:0.9rem; display:flex; align-items:center; gap:6px; text-decoration:none; transition:background-color 0.2s; font-family:'Outfit', sans-serif; box-shadow:0 2px 8px rgba(239,68,68,0.3);">
        <svg viewBox="0 0 24 24" style="width:16px; height:16px; fill:currentColor;"><path d="M23.498 6.163a3.003 3.003 0 0 0-2.11-2.11C19.517 3.545 12 3.545 12 3.545s-7.517 0-9.388.508a3.003 3.003 0 0 0-2.11 2.11C0 8.033 0 12 0 12s0 3.967.502 5.837a3.003 3.003 0 0 0 2.11 2.11c1.871.508 9.388.508 9.388.508s7.517 0 9.388-.508a3.003 3.003 0 0 0 2.11-2.11C24 15.967 24 12 24 12s0-3.967-.502-5.837zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/></svg>
        Subscribe
      </a>
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
