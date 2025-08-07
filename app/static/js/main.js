// Main JavaScript for Best Wines Sweden

// Global variables
window.currentPage = 1;
window.currentFilters = {};
window.isLoading = false;

// Initialize page
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM Content Loaded');
    console.log('Wine grid element:', document.getElementById('wineGrid') ? 'found' : 'not found');
    console.log('Search input element:', document.getElementById('searchInput') ? 'found' : 'not found');
    console.log('Filter panel element:', document.getElementById('filterPanel') ? 'found' : 'not found');
    
    initializeFilters();
    setupEventListeners();
    
    // Load filter options if we're on a page with filters
    if (typeof loadFilterOptions === 'function') {
        loadFilterOptions();
    }
});

// Setup event listeners
function setupEventListeners() {
    // Filter input changes (only if filter panel exists)
    const filterPanel = document.getElementById('filterPanel');
    if (filterPanel) {
        document.querySelectorAll('#filterPanel input, #filterPanel select').forEach(input => {
            input.addEventListener('change', debounce(applyFilters, 300));
        });
    }
    
    // Search input with debounce
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('input', debounce(function() {
            const searchTerm = document.getElementById('searchTerm');
            if (searchTerm) {
                searchTerm.value = this.value;
            }
            applyFilters();
        }, 500));
    }
    
    const searchTerm = document.getElementById('searchTerm');
    if (searchTerm) {
        searchTerm.addEventListener('input', debounce(applyFilters, 500));
    }
}

// Debounce function to limit API calls
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Initialize filters
function initializeFilters() {
    window.currentFilters = {
        page: 1,
        page_size: 20,
        sort_by: 'rating',
        sort_order: 'desc'
    };
}

// Show/hide filter panel
function showFilters() {
    const panel = document.getElementById('filterPanel');
    if (panel) {
        panel.style.display = 'block';
        panel.scrollIntoView({ behavior: 'smooth' });
    }
}

function hideFilters() {
    const panel = document.getElementById('filterPanel');
    if (panel) {
        panel.style.display = 'none';
    }
}

// Show/hide toplists panel
function showToplists() {
    const panel = document.getElementById('toplistPanel');
    if (panel) {
        panel.style.display = 'block';
        loadToplists();
        panel.scrollIntoView({ behavior: 'smooth' });
    }
}

function hideToplists() {
    const panel = document.getElementById('toplistPanel');
    if (panel) {
        panel.style.display = 'none';
    }
}

// Load toplists
async function loadToplists() {
    try {
        const response = await fetch('/api/toplists');
        const toplists = await response.json();
        
        const grid = document.getElementById('toplistGrid');
        grid.innerHTML = '';
        
        toplists.forEach(toplist => {
            const card = createToplistCard(toplist);
            grid.appendChild(card);
        });
    } catch (error) {
        console.error('Error loading toplists:', error);
        showError('Failed to load toplists');
    }
}

// Create toplist card
function createToplistCard(toplist) {
    const div = document.createElement('div');
    div.className = 'col-md-6 col-lg-4 mb-3';
    
    const categoryClass = getCategoryClass(toplist.category);
    const avgRating = toplist.avg_rating ? toplist.avg_rating.toFixed(1) : 'N/A';
    
    div.innerHTML = `
        <div class="toplist-card card h-100" style="cursor: pointer;" onclick="window.location.href='/toplist/${toplist.id}'">
            <div class="card-body">
                <h6 class="card-title">${toplist.name}</h6>
                <span class="badge ${categoryClass} mb-2">${toplist.category}</span>
                <div class="toplist-stats">
                    <div class="d-flex text-center">
                        <div class="stat-mini flex-fill px-1">
                            <div class="small fw-bold text-primary">${toplist.wine_count}</div>
                            <small class="text-muted">Wines</small>
                        </div>
                        <div class="stat-mini flex-fill px-1">
                            <div class="small fw-bold text-success">${toplist.match_count}</div>
                            <small class="text-muted">Matches</small>
                        </div>
                        <div class="stat-mini flex-fill px-1">
                            <div class="small fw-bold text-warning">
                                <i class="bi bi-star-fill"></i> ${avgRating}
                            </div>
                            <small class="text-muted">Rating</small>
                        </div>
                    </div>
                </div>
                <div class="mt-2">
                    <small class="text-primary">
                        <i class="bi bi-arrow-right"></i> View Toplist
                    </small>
                </div>
            </div>
        </div>
    `;
    
    return div;
}

// Get category class for styling
function getCategoryClass(category) {
    const classes = {
        'budget': 'bg-success',
        'mid-range': 'bg-warning text-dark',
        'premium': 'bg-danger',
        'value': 'bg-info text-dark',
        'pairing': 'bg-secondary',
        'style': 'bg-primary',
        'regional': 'bg-dark',
        'discovery': 'bg-purple'
    };
    return classes[category] || 'bg-secondary';
}

// Filter by toplist
function filterByToplist(toplistId) {
    const filterPanel = document.getElementById('filterPanel');
    if (filterPanel) {
        filterPanel.style.display = 'block';
    }
    
    // Clear other filters and set toplist
    clearFilters();
    window.currentFilters.toplist_id = toplistId;
    
    applyFilters();
    hideToplists();
}

// Apply filters
async function applyFilters() {
    if (window.isLoading) return;
    
    // Helper function to safely get element value
    function getElementValue(id, fallback = undefined) {
        const element = document.getElementById(id);
        return element ? (element.value || fallback) : fallback;
    }
    
    window.currentFilters = {
        ...window.currentFilters,
        page: 1, // Reset to first page
        min_price: parseFloat(getElementValue('minPrice')) || undefined,
        max_price: parseFloat(getElementValue('maxPrice')) || undefined,
        min_rating: parseFloat(getElementValue('minRating')) || undefined,
        max_rating: parseFloat(getElementValue('maxRating')) || undefined,
        wine_style: getElementValue('wineStyle'),
        country: getElementValue('country'),
        search_term: getElementValue('searchTerm'),
        sort_by: getElementValue('sortBy', 'rating'),
        sort_order: getElementValue('sortOrder', 'desc')
    };
    
    console.log('Applying filters:', window.currentFilters);
    await loadWines(true);
}

// Clear filters
function clearFilters() {
    // Helper function to safely clear element value
    function clearElementValue(id, defaultValue = '') {
        const element = document.getElementById(id);
        if (element) {
            element.value = defaultValue;
        }
    }
    
    clearElementValue('minPrice');
    clearElementValue('maxPrice');
    clearElementValue('minRating');
    clearElementValue('maxRating');
    clearElementValue('wineStyle');
    clearElementValue('country');
    clearElementValue('searchTerm');
    clearElementValue('searchInput');
    clearElementValue('sortBy', 'rating');
    clearElementValue('sortOrder', 'desc');
    
    window.currentFilters = {
        page: 1,
        page_size: 20,
        sort_by: 'rating',
        sort_order: 'desc'
    };
    
    loadWines(true);
}

// Load wines with filters
async function loadWines(replace = false) {
    if (window.isLoading) return;
    
    window.isLoading = true;
    showLoading();
    
    try {
        const params = new URLSearchParams();
        
        Object.entries(window.currentFilters).forEach(([key, value]) => {
            if (value !== undefined && value !== null && value !== '') {
                params.append(key, value);
            }
        });
        
        const response = await fetch(`/api/wines?${params}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const wines = await response.json();
        console.log(`Loaded ${wines.length} wines from API`);
        displayWines(wines, replace);
        
        // Update results count
        updateResultsCount(wines.length, replace);
        
    } catch (error) {
        console.error('Error loading wines:', error);
        showError('Failed to load wines. Please try again.');
    } finally {
        window.isLoading = false;
        hideLoading();
    }
}

// Display wines in grid
function displayWines(wines, replace = false) {
    const grid = document.getElementById('wineGrid');
    
    // Check if grid exists
    if (!grid) {
        console.error('Wine grid element not found');
        return;
    }
    
    const noResults = document.getElementById('noResults');
    const loadMoreBtn = document.getElementById('loadMoreBtn');
    
    if (replace && grid) {
        grid.innerHTML = '';
    }
    
    if (wines.length === 0 && replace) {
        if (noResults) {
            noResults.style.display = 'block';
        }
        if (loadMoreBtn) {
            loadMoreBtn.style.display = 'none';
        }
        return;
    }
    
    if (noResults) {
        noResults.style.display = 'none';
    }
    
    wines.forEach(wine => {
        const wineCard = createWineCard(wine);
        grid.appendChild(wineCard);
    });
    
    // Show/hide load more button
    if (loadMoreBtn) {
        loadMoreBtn.style.display = wines.length === window.currentFilters.page_size ? 'block' : 'none';
    }
    
    console.log(`Displayed ${wines.length} wines in grid`);
}

// Create wine card element
function createWineCard(wine) {
    const div = document.createElement('div');
    div.className = 'col-lg-6 col-xl-4 mb-4';
    
    const verifiedBadge = wine.verified ? 
        '<span class="badge bg-success ms-1"><i class="bi bi-check-circle"></i> Verified</span>' : '';
    
    const price = wine.price ? `${Math.round(wine.price)} SEK` : 'Price N/A';
    
    // Enhanced wine information
    const vivinoWineStyle = wine.vivino_wine_style ? `<span class="badge bg-primary me-1">${wine.vivino_wine_style}</span>` : '';
    const systembolagetStyle = wine.wine_style ? `<span class="badge bg-secondary me-1">${wine.wine_style}</span>` : '';
    const vivinoCountry = wine.vivino_country ? `<span class="badge bg-outline-info me-1"><i class="bi bi-geo-alt"></i> ${wine.vivino_country}</span>` : '';
    const country = wine.country ? `<span class="badge bg-outline-secondary me-1">${wine.country}</span>` : '';
    const year = wine.year ? `<span class="badge bg-outline-secondary">${wine.year}</span>` : '';
    const producer = wine.producer ? `<p class="text-muted small mt-2 mb-1"><i class="bi bi-building"></i> ${wine.producer}</p>` : '';
    const winery = wine.vivino_winery ? `<p class="text-muted small mt-2 mb-1"><i class="bi bi-house"></i> ${wine.vivino_winery}</p>` : '';
    const region = wine.vivino_region ? `<p class="text-muted small mb-1"><i class="bi bi-map"></i> ${wine.vivino_region}</p>` : '';
    
    // Alcohol content (prefer vivino data)
    const alcoholContent = wine.vivino_alcohol_content || wine.alcohol_percentage;
    const alcohol = alcoholContent ? `<p class="text-muted small mb-2"><i class="bi bi-percent"></i> ${alcoholContent}% vol</p>` : '';
    
    // Wine characteristics
    const characteristics = [];
    if (wine.body) {
        const bodyText = wine.body <= 2 ? 'Light' : wine.body <= 3 ? 'Medium' : 'Full';
        characteristics.push(`<span class="badge bg-info me-1"><i class="bi bi-droplet"></i> ${bodyText} Body</span>`);
    }
    if (wine.acidity) {
        const acidityText = wine.acidity <= 2 ? 'Low' : wine.acidity <= 3 ? 'Medium' : 'High';
        characteristics.push(`<span class="badge bg-warning text-dark me-1"><i class="bi bi-lightning"></i> ${acidityText} Acidity</span>`);
    }
    const characteristicsHtml = characteristics.length > 0 ? `<div class="mb-2">${characteristics.join('')}</div>` : '';
    
    const matchScore = wine.match_score ? `<div class="mt-2"><small class="text-muted">Match Score: ${wine.match_score.toFixed(1)}%</small></div>` : '';
    
    // Wine image with fallback
    const wineImage = wine.image_url ? 
        `<div class="wine-image-container text-center py-3">
            <img src="${wine.image_url}" 
                 alt="${wine.vivino_name}" 
                 class="wine-bottle-image img-fluid"
                 style="max-height: 200px; max-width: 120px; object-fit: contain;"
                 onerror="this.style.display='none'; this.nextElementSibling.style.display='block';">
            <div class="wine-placeholder d-none text-muted">
                <i class="bi bi-cup" style="font-size: 3rem;"></i>
                <br><small>No image available</small>
            </div>
         </div>` : 
        `<div class="wine-image-container text-center py-3">
            <div class="wine-placeholder text-muted">
                <i class="bi bi-cup" style="font-size: 3rem;"></i>
                <br><small>No image available</small>
            </div>
         </div>`;
    
    div.innerHTML = `
        <div class="wine-card card h-100">
            <div class="card-header d-flex justify-content-between align-items-start">
                <div class="wine-rating">
                    <span class="badge bg-warning text-dark">
                        <i class="bi bi-star-fill"></i> ${wine.vivino_rating}
                    </span>
                    ${verifiedBadge}
                </div>
                <div class="wine-price text-end">
                    <strong class="text-primary">${price}</strong>
                </div>
            </div>
            
            ${wineImage}
            
            <div class="card-body">
                <h5 class="card-title wine-name">${wine.vivino_name}</h5>
                <h6 class="card-subtitle text-muted mb-2">${wine.systembolaget_name}</h6>
                
                <div class="wine-details mb-2">
                    ${vivinoWineStyle}
                    ${systembolagetStyle}
                    ${vivinoCountry}
                    ${year}
                </div>
                
                ${characteristicsHtml}
                
                ${winery}
                ${region}
                ${producer}
                ${alcohol}
            </div>
            
            <div class="card-footer bg-transparent">
                <div class="d-flex justify-content-between align-items-center">
                    <a href="/wine/${wine.match_id}" class="btn btn-primary btn-sm">
                        <i class="bi bi-eye"></i> View Details
                    </a>
                    <a href="https://systembolaget.se/sortiment/vin/?q=${wine.product_number}" 
                       target="_blank" class="btn btn-outline-primary btn-sm">
                        <i class="bi bi-shop"></i> Buy
                    </a>
                </div>
                ${matchScore}
            </div>
        </div>
    `;
    
    return div;
}

// Load more wines
async function loadMoreWines() {
    window.currentFilters.page += 1;
    await loadWines(false);
}

// Update results count
function updateResultsCount(count, isNewSearch) {
    const resultsCount = document.getElementById('resultsCount');
    const currentCount = isNewSearch ? count : 
        document.querySelectorAll('#wineGrid .wine-card').length;
    
    resultsCount.textContent = `Showing ${currentCount} wines`;
}

// Search functionality
function handleSearch(event) {
    if (event.key === 'Enter') {
        searchWines();
    }
}

function searchWines() {
    console.log('Search wines function called');
    const searchInput = document.getElementById('searchInput');
    const searchTerm = document.getElementById('searchTerm');
    
    console.log('Search input value:', searchInput ? searchInput.value : 'not found');
    console.log('Search term element:', searchTerm ? 'found' : 'not found');
    
    // If we have both search elements, copy the value
    if (searchInput && searchTerm) {
        searchTerm.value = searchInput.value;
        console.log('Copied search value to search term field');
    }
    
    // Show filters panel if it exists, otherwise just apply filters
    const filterPanel = document.getElementById('filterPanel');
    if (filterPanel) {
        console.log('Showing filter panel');
        showFilters();
    } else {
        console.log('Filter panel not found, applying filters directly');
    }
    
    applyFilters();
}

// Loading states
function showLoading() {
    const indicator = document.getElementById('loadingIndicator');
    if (indicator) {
        indicator.style.display = 'block';
    }
}

function hideLoading() {
    const indicator = document.getElementById('loadingIndicator');
    if (indicator) {
        indicator.style.display = 'none';
    }
}

// Error handling
function showError(message) {
    // Create or update error alert
    let alert = document.getElementById('errorAlert');
    if (!alert) {
        alert = document.createElement('div');
        alert.id = 'errorAlert';
        alert.className = 'alert alert-danger alert-dismissible fade show';
        alert.innerHTML = `
            <i class="bi bi-exclamation-triangle"></i> <span></span>
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        document.querySelector('.container').insertBefore(alert, document.querySelector('.container').firstChild);
    }
    
    alert.querySelector('span').textContent = message;
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
        if (alert && alert.parentNode) {
            alert.remove();
        }
    }, 5000);
}

// Utility functions
function formatPrice(price) {
    return price ? `${Math.round(price)} SEK` : 'Price N/A';
}

function formatRating(rating) {
    return rating ? rating.toFixed(1) : 'N/A';
}

function getWineStyleEmoji(style) {
    if (!style) return '';
    
    const lowerStyle = style.toLowerCase();
    if (lowerStyle.includes('rött') || lowerStyle.includes('red')) return '🍇';
    if (lowerStyle.includes('vitt') || lowerStyle.includes('white')) return '🥂';
    if (lowerStyle.includes('mousserande') || lowerStyle.includes('sparkling')) return '🍾';
    if (lowerStyle.includes('rosé') || lowerStyle.includes('rose')) return '🌹';
    return '🍷';
}

function getCountryFlag(country) {
    const flags = {
        'Frankrike': '🇫🇷',
        'Italien': '🇮🇹', 
        'Spanien': '🇪🇸',
        'Tyskland': '🇩🇪',
        'Argentina': '🇦🇷',
        'Chile': '🇨🇱',
        'Australien': '🇦🇺',
        'USA': '🇺🇸',
        'Sydafrika': '🇿🇦',
        'Nya Zeeland': '🇳🇿',
        'Portugal': '🇵🇹',
        'Grekland': '🇬🇷'
    };
    return flags[country] || '🌍';
}

// Test function for debugging
window.testSearch = function() {
    console.log('Testing search functionality...');
    
    // Test if we can access the wine grid
    const grid = document.getElementById('wineGrid');
    console.log('Wine grid:', grid);
    
    // Test if we can make API call
    fetch('/api/wines?page_size=5')
        .then(response => response.json())
        .then(wines => {
            console.log('Got wines from API:', wines.length);
            if (grid) {
                grid.innerHTML = '<div class="col-12"><p class="text-success">✅ Test successful! Got ' + wines.length + ' wines</p></div>';
            }
        })
        .catch(error => {
            console.error('Test failed:', error);
            if (grid) {
                grid.innerHTML = '<div class="col-12"><p class="text-danger">❌ Test failed: ' + error.message + '</p></div>';
            }
        });
};