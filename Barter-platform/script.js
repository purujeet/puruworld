
const form = document.getElementById('listing-form');
const itemsContainer = document.getElementById('items-container');
let listings = JSON.parse(localStorage.getItem('barterListings')) || [];

function showToast(message) {
    let toast = document.getElementById('toast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'toast';
        document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 3000);
}

function saveListings() {
    localStorage.setItem('barterListings', JSON.stringify(listings));
}

function deleteListing(id) {
    listings = listings.filter(item => item.id !== id);
    saveListings();
    renderListings();
    showToast('Listing deleted');
}

function renderListings() {
    if (listings.length === 0) {
        itemsContainer.innerHTML = '<p>No listings found. Add a new one!</p>';
        return;
    }

    const now = new Date().getTime();
    // Filter out expired listings (older than 7 days)
    listings = listings.filter(item => now - item.createdAt < 7 * 24 * 3600 * 1000);
    saveListings();

    itemsContainer.innerHTML = listings.map(item => {
        return `
        <div class="card">
            <img src="${item.photo || 'https://via.placeholder.com/300?text=No+Image'}" alt="${item.title}" />
            <h3>${item.title}</h3>
            <p>${item.description}</p>
            <p class="info"><strong>Category:</strong> ${item.category} | <strong>Location:</strong> ${item.location}</p>
            <button onclick="deleteListing('${item.id}')">Delete</button>
        </div>
        `;
    }).join('');
}

function generateId() {
    return '_' + Math.random().toString(36).substr(2, 9);
}

form.addEventListener('submit', function(e) {
    e.preventDefault();

    const title = form['item-title'].value.trim();
    const description = form['item-description'].value.trim();
    const category = form['item-category'].value;
    const location = form['item-location'].value.trim();
    const photo = form['item-photo'].value.trim();

    if (!title || !description || !category || !location) {
        showToast('Please fill all required fields');
        return;
    }

    const newItem = {
        id: generateId(),
        title,
        description,
        category,
        location,
        photo: photo || null,
        createdAt: new Date().getTime()
    };

    listings.push(newItem);
    saveListings();
    renderListings();
    form.reset();
    showToast('Listing added successfully');
});

// Initial render
renderListings();
