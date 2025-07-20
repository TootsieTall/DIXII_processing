/**
 * DocumentSearch.js - Advanced Document Search Module
 * Handles multi-field search, filtering, sorting, and saved searches
 */

class DocumentSearch {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.searchForm = null;
        this.savedSearches = [];
        this.currentSearchCriteria = {};
        this.currentSort = { field: 'created_at', order: 'desc' };
        this.currentPage = 1;
        this.pageSize = 20;

        this.init();
    }

    init() {
        this.createSearchInterface();
        this.loadSavedSearches();
        this.bindEvents();
    }

    createSearchInterface() {
        const searchHTML = `
            <div class="advanced-search-container">
                <div class="search-header">
                    <h3>Advanced Document Search</h3>
                    <div class="search-actions">
                        <button type="button" class="btn btn-secondary" id="clearSearch">Clear All</button>
                        <button type="button" class="btn btn-outline" id="saveSearch">Save Search</button>
                    </div>
                </div>

                <form id="advancedSearchForm" class="advanced-search-form">
                    <div class="search-row">
                        <div class="search-group">
                            <label for="searchQuery">Search Text</label>
                            <input type="text" id="searchQuery" name="searchQuery"
                                   placeholder="Search filenames, client names, or document types...">
                        </div>

                        <div class="search-group">
                            <label for="clientSelect">Client</label>
                            <select id="clientSelect" name="clientId">
                                <option value="">All Clients</option>
                            </select>
                        </div>

                        <div class="search-group">
                            <label for="documentType">Document Type</label>
                            <select id="documentType" name="documentType">
                                <option value="">All Types</option>
                            </select>
                        </div>
                    </div>

                    <div class="search-row">
                        <div class="search-group">
                            <label for="taxYear">Tax Year</label>
                            <select id="taxYear" name="taxYear">
                                <option value="">All Years</option>
                            </select>
                        </div>

                        <div class="search-group">
                            <label for="status">Status</label>
                            <select id="status" name="status">
                                <option value="">All Statuses</option>
                                <option value="completed">Completed</option>
                                <option value="processing">Processing</option>
                                <option value="error">Error</option>
                                <option value="waiting">Waiting</option>
                            </select>
                        </div>

                        <div class="search-group">
                            <label for="hasAnnotations">Annotations</label>
                            <select id="hasAnnotations" name="hasAnnotations">
                                <option value="">Any</option>
                                <option value="true">With Annotations</option>
                                <option value="false">Without Annotations</option>
                            </select>
                        </div>
                    </div>

                    <div class="search-row">
                        <div class="search-group">
                            <label for="dateFrom">Date From</label>
                            <input type="date" id="dateFrom" name="dateFrom">
                        </div>

                        <div class="search-group">
                            <label for="dateTo">Date To</label>
                            <input type="date" id="dateTo" name="dateTo">
                        </div>

                        <div class="search-group">
                            <label for="confidenceMin">Min Confidence</label>
                            <input type="number" id="confidenceMin" name="confidenceMin"
                                   min="0" max="1" step="0.01" placeholder="0.00">
                        </div>
                    </div>

                    <div class="search-actions-row">
                        <button type="submit" class="btn btn-primary">
                            <i class="fas fa-search"></i> Search Documents
                        </button>

                        <div class="sort-controls">
                            <label for="sortBy">Sort by:</label>
                            <select id="sortBy" name="sortBy">
                                <option value="created_at">Date Created</option>
                                <option value="filename">Filename</option>
                                <option value="client">Client Name</option>
                                <option value="type">Document Type</option>
                                <option value="size">File Size</option>
                                <option value="confidence">Confidence</option>
                            </select>

                            <button type="button" class="btn btn-outline sort-order" id="sortOrder" data-order="desc">
                                <i class="fas fa-sort-down"></i>
                            </button>
                        </div>
                    </div>
                </form>

                <div class="saved-searches-section">
                    <h4>Saved Searches</h4>
                    <div id="savedSearchesList" class="saved-searches-list">
                        <!-- Saved searches will be loaded here -->
                    </div>
                </div>
            </div>
        `;

        this.container.innerHTML = searchHTML;
        this.searchForm = document.getElementById('advancedSearchForm');
    }

    async loadFormData() {
        try {
            // Load clients for dropdown
            const clientsResponse = await fetch('/api/clients');
            const clients = await clientsResponse.json();
            const clientSelect = document.getElementById('clientSelect');
            clients.forEach(client => {
                const option = document.createElement('option');
                option.value = client.id;
                option.textContent = client.name;
                clientSelect.appendChild(option);
            });

            // Load document types
            const typesResponse = await fetch('/api/documents/types');
            const types = await typesResponse.json();
            const typeSelect = document.getElementById('documentType');
            types.forEach(type => {
                const option = document.createElement('option');
                option.value = type;
                option.textContent = type;
                typeSelect.appendChild(option);
            });

            // Load tax years
            const yearsResponse = await fetch('/api/documents/years');
            const years = await yearsResponse.json();
            const yearSelect = document.getElementById('taxYear');
            years.forEach(year => {
                const option = document.createElement('option');
                option.value = year;
                option.textContent = year;
                yearSelect.appendChild(option);
            });
        } catch (error) {
            console.error('Error loading form data:', error);
        }
    }

    bindEvents() {
        // Form submission
        this.searchForm.addEventListener('submit', (e) => {
            e.preventDefault();
            this.performSearch();
        });

        // Clear search
        document.getElementById('clearSearch').addEventListener('click', () => {
            this.clearSearch();
        });

        // Save search
        document.getElementById('saveSearch').addEventListener('click', () => {
            this.showSaveSearchDialog();
        });

        // Sort order toggle
        document.getElementById('sortOrder').addEventListener('click', (e) => {
            this.toggleSortOrder(e.target);
        });

        // Real-time search on input change (debounced)
        let searchTimeout;
        document.getElementById('searchQuery').addEventListener('input', () => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                this.performSearch();
            }, 500);
        });

        // Trigger search when filter values change
        const filterElements = this.searchForm.querySelectorAll('select, input[type="date"], input[type="number"]');
        filterElements.forEach(element => {
            element.addEventListener('change', () => {
                this.performSearch();
            });
        });
    }

    async performSearch(page = 1) {
        this.currentPage = page;
        this.showSearchLoading();

        try {
            const formData = new FormData(this.searchForm);
            const searchCriteria = Object.fromEntries(formData);

            // Add pagination and sorting
            searchCriteria.page = page;
            searchCriteria.pageSize = this.pageSize;
            searchCriteria.sortBy = this.currentSort.field;
            searchCriteria.sortOrder = this.currentSort.order;

            this.currentSearchCriteria = searchCriteria;

            const response = await fetch('/api/documents/advanced-search', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(searchCriteria)
            });

            const result = await response.json();

            if (result.success) {
                this.displaySearchResults(result.data);
                this.updatePagination(result.pagination);
            } else {
                this.showSearchError(result.error);
            }
        } catch (error) {
            console.error('Search error:', error);
            this.showSearchError('An error occurred while searching');
        }
    }

    displaySearchResults(results) {
        // This will trigger the DocumentGrid to update
        const event = new CustomEvent('searchResults', {
            detail: { results: results }
        });
        document.dispatchEvent(event);

        this.hideSearchLoading();
    }

    updatePagination(pagination) {
        const event = new CustomEvent('updatePagination', {
            detail: { pagination: pagination }
        });
        document.dispatchEvent(event);
    }

    showSearchLoading() {
        const event = new CustomEvent('searchLoading');
        document.dispatchEvent(event);
    }

    hideSearchLoading() {
        const event = new CustomEvent('searchComplete');
        document.dispatchEvent(event);
    }

    showSearchError(message) {
        const event = new CustomEvent('searchError', {
            detail: { message: message }
        });
        document.dispatchEvent(event);
    }

    clearSearch() {
        this.searchForm.reset();
        this.currentSearchCriteria = {};
        this.currentPage = 1;
        this.performSearch();
    }

    toggleSortOrder(button) {
        const currentOrder = button.dataset.order;
        const newOrder = currentOrder === 'desc' ? 'asc' : 'desc';

        button.dataset.order = newOrder;
        button.innerHTML = newOrder === 'desc'
            ? '<i class="fas fa-sort-down"></i>'
            : '<i class="fas fa-sort-up"></i>';

        this.currentSort.order = newOrder;
        this.performSearch();
    }

    async loadSavedSearches() {
        try {
            const response = await fetch('/api/saved-searches');
            const savedSearches = await response.json();
            this.savedSearches = savedSearches;
            this.renderSavedSearches();
        } catch (error) {
            console.error('Error loading saved searches:', error);
        }
    }

    renderSavedSearches() {
        const container = document.getElementById('savedSearchesList');

        if (this.savedSearches.length === 0) {
            container.innerHTML = '<p class="no-saved-searches">No saved searches yet</p>';
            return;
        }

        const searchesHTML = this.savedSearches.map(search => `
            <div class="saved-search-item" data-search-id="${search.id}">
                <div class="search-info">
                    <h5>${search.search_name}</h5>
                    <small>Saved on ${new Date(search.created_at).toLocaleDateString()}</small>
                </div>
                <div class="search-actions">
                    <button class="btn btn-sm btn-outline load-search" data-search-id="${search.id}">
                        Load
                    </button>
                    <button class="btn btn-sm btn-danger delete-search" data-search-id="${search.id}">
                        Delete
                    </button>
                </div>
            </div>
        `).join('');

        container.innerHTML = searchesHTML;

        // Bind events for saved searches
        container.querySelectorAll('.load-search').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const searchId = e.target.dataset.searchId;
                this.loadSavedSearch(searchId);
            });
        });

        container.querySelectorAll('.delete-search').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const searchId = e.target.dataset.searchId;
                this.deleteSavedSearch(searchId);
            });
        });
    }

    async loadSavedSearch(searchId) {
        const savedSearch = this.savedSearches.find(s => s.id == searchId);
        if (!savedSearch) return;

        const criteria = savedSearch.search_criteria;

        // Populate form with saved criteria
        Object.keys(criteria).forEach(key => {
            const element = this.searchForm.querySelector(`[name="${key}"]`);
            if (element) {
                element.value = criteria[key] || '';
            }
        });

        // Trigger search
        this.performSearch();
    }

    async deleteSavedSearch(searchId) {
        if (!confirm('Are you sure you want to delete this saved search?')) return;

        try {
            const response = await fetch(`/api/saved-searches/${searchId}`, {
                method: 'DELETE'
            });

            if (response.ok) {
                this.loadSavedSearches(); // Reload the list
            }
        } catch (error) {
            console.error('Error deleting saved search:', error);
        }
    }

    showSaveSearchDialog() {
        const searchName = prompt('Enter a name for this search:');
        if (!searchName) return;

        this.saveCurrentSearch(searchName);
    }

    async saveCurrentSearch(searchName) {
        try {
            const response = await fetch('/api/saved-searches', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    search_name: searchName,
                    search_criteria: this.currentSearchCriteria
                })
            });

            if (response.ok) {
                this.loadSavedSearches(); // Reload the list
            }
        } catch (error) {
            console.error('Error saving search:', error);
        }
    }

    // Export search results
    async exportResults(format = 'csv') {
        try {
            const response = await fetch('/api/documents/export', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    searchCriteria: this.currentSearchCriteria,
                    format: format
                })
            });

            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `documents_export_${new Date().toISOString().split('T')[0]}.${format}`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
            }
        } catch (error) {
            console.error('Error exporting results:', error);
        }
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('documentSearchContainer')) {
        window.documentSearch = new DocumentSearch('documentSearchContainer');
        window.documentSearch.loadFormData();
    }
});