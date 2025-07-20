/**
 * DocumentGrid.js - Document Grid Display Module
 * Handles grid view with thumbnails, bulk selection, and batch operations
 */

class DocumentGrid {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.documents = [];
        this.selectedDocuments = new Set();
        this.viewMode = 'grid'; // 'grid' or 'list'
        this.currentPage = 1;
        this.totalPages = 1;

        this.init();
    }

    init() {
        this.createGridInterface();
        this.bindEvents();
        this.loadDocuments();
    }

    createGridInterface() {
        const gridHTML = `
            <div class="document-grid-container">
                <div class="grid-header">
                    <div class="grid-controls">
                        <div class="view-controls">
                            <button class="btn btn-outline view-toggle ${this.viewMode === 'grid' ? 'active' : ''}"
                                    data-view="grid" title="Grid View">
                                <i class="fas fa-th"></i>
                            </button>
                            <button class="btn btn-outline view-toggle ${this.viewMode === 'list' ? 'active' : ''}"
                                    data-view="list" title="List View">
                                <i class="fas fa-list"></i>
                            </button>
                        </div>

                        <div class="selection-controls" style="display: none;">
                            <span class="selection-count">0 selected</span>
                            <button class="btn btn-outline" id="selectAll">Select All</button>
                            <button class="btn btn-outline" id="clearSelection">Clear</button>
                        </div>

                        <div class="bulk-actions" style="display: none;">
                            <button class="btn btn-primary" id="downloadSelected">
                                <i class="fas fa-download"></i> Download
                            </button>
                            <button class="btn btn-secondary" id="addAnnotationBulk">
                                <i class="fas fa-comment"></i> Add Note
                            </button>
                            <button class="btn btn-warning" id="moveDocuments">
                                <i class="fas fa-folder"></i> Move
                            </button>
                            <button class="btn btn-danger" id="deleteSelected">
                                <i class="fas fa-trash"></i> Delete
                            </button>
                        </div>
                    </div>

                    <div class="results-info">
                        <span id="resultsCount">0 documents</span>
                    </div>
                </div>

                <div class="grid-loading" id="gridLoading" style="display: none;">
                    <div class="loading-spinner"></div>
                    <p>Loading documents...</p>
                </div>

                <div class="grid-error" id="gridError" style="display: none;">
                    <p class="error-message"></p>
                </div>

                <div class="document-grid" id="documentGrid">
                    <!-- Documents will be rendered here -->
                </div>

                <div class="pagination" id="paginationContainer">
                    <!-- Pagination will be rendered here -->
                </div>
            </div>
        `;

        this.container.innerHTML = gridHTML;
    }

    bindEvents() {
        // View mode toggle
        this.container.querySelectorAll('.view-toggle').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.toggleViewMode(e.target.dataset.view);
            });
        });

        // Selection controls
        document.getElementById('selectAll').addEventListener('click', () => {
            this.selectAll();
        });

        document.getElementById('clearSelection').addEventListener('click', () => {
            this.clearSelection();
        });

        // Bulk actions
        document.getElementById('downloadSelected').addEventListener('click', () => {
            this.downloadSelected();
        });

        document.getElementById('addAnnotationBulk').addEventListener('click', () => {
            this.showBulkAnnotationDialog();
        });

        document.getElementById('moveDocuments').addEventListener('click', () => {
            this.showMoveDialog();
        });

        document.getElementById('deleteSelected').addEventListener('click', () => {
            this.deleteSelected();
        });

        // Listen for search results
        document.addEventListener('searchResults', (e) => {
            this.displayDocuments(e.detail.results);
        });

        document.addEventListener('updatePagination', (e) => {
            this.renderPagination(e.detail.pagination);
        });

        document.addEventListener('searchLoading', () => {
            this.showLoading();
        });

        document.addEventListener('searchComplete', () => {
            this.hideLoading();
        });

        document.addEventListener('searchError', (e) => {
            this.showError(e.detail.message);
        });
    }

    async loadDocuments() {
        this.showLoading();

        try {
            const response = await fetch('/api/documents');
            const result = await response.json();

            if (result.success) {
                this.displayDocuments(result.data);
                this.renderPagination(result.pagination || {});
            } else {
                this.showError(result.error);
            }
        } catch (error) {
            console.error('Error loading documents:', error);
            this.showError('Failed to load documents');
        }
    }

    displayDocuments(documents) {
        this.documents = documents;
        this.selectedDocuments.clear();
        this.updateSelectionControls();

        const gridContainer = document.getElementById('documentGrid');
        const resultsCount = document.getElementById('resultsCount');

        resultsCount.textContent = `${documents.length} document${documents.length !== 1 ? 's' : ''}`;

        if (documents.length === 0) {
            gridContainer.innerHTML = `
                <div class="no-documents">
                    <i class="fas fa-file-alt fa-3x"></i>
                    <h3>No documents found</h3>
                    <p>Try adjusting your search criteria or upload some documents.</p>
                </div>
            `;
            return;
        }

        if (this.viewMode === 'grid') {
            this.renderGridView(documents);
        } else {
            this.renderListView(documents);
        }

        this.hideLoading();
    }

    renderGridView(documents) {
        const gridContainer = document.getElementById('documentGrid');
        gridContainer.className = 'document-grid grid-view';

        const documentsHTML = documents.map(doc => `
            <div class="document-card" data-doc-id="${doc.id}">
                <div class="card-header">
                    <input type="checkbox" class="document-checkbox" value="${doc.id}">
                    <div class="document-status ${doc.status}">
                        ${this.getStatusIcon(doc.status)}
                    </div>
                </div>

                <div class="document-thumbnail" onclick="documentGrid.previewDocument(${doc.id})">
                    ${this.getThumbnail(doc)}
                </div>

                <div class="document-info">
                    <h4 class="document-title" title="${doc.original_filename}">
                        ${this.truncateText(doc.original_filename, 30)}
                    </h4>

                    <div class="document-meta">
                        <span class="client-name">
                            <i class="fas fa-user"></i> ${doc.client_name || 'Unknown'}
                        </span>

                        <span class="document-type">
                            <i class="fas fa-file"></i> ${doc.document_type || 'Unknown'}
                        </span>

                        ${doc.tax_year ? `<span class="tax-year"><i class="fas fa-calendar"></i> ${doc.tax_year}</span>` : ''}

                        <span class="file-size">
                            <i class="fas fa-hdd"></i> ${this.formatFileSize(doc.file_size_bytes)}
                        </span>

                        ${doc.confidence ? `<span class="confidence ${this.getConfidenceClass(doc.confidence)}">
                            <i class="fas fa-chart-bar"></i> ${Math.round(doc.confidence * 100)}%
                        </span>` : ''}

                        ${doc.annotation_count > 0 ? `<span class="annotations">
                            <i class="fas fa-comment"></i> ${doc.annotation_count}
                        </span>` : ''}
                    </div>

                    <div class="document-date">
                        ${new Date(doc.created_at).toLocaleDateString()}
                    </div>
                </div>

                <div class="card-actions">
                    <button class="btn btn-sm btn-outline" onclick="documentGrid.previewDocument(${doc.id})" title="Preview">
                        <i class="fas fa-eye"></i>
                    </button>
                    <button class="btn btn-sm btn-outline" onclick="documentGrid.downloadDocument(${doc.id})" title="Download">
                        <i class="fas fa-download"></i>
                    </button>
                    <button class="btn btn-sm btn-outline" onclick="documentGrid.showAnnotations(${doc.id})" title="Annotations">
                        <i class="fas fa-comment"></i>
                    </button>
                    <div class="dropdown">
                        <button class="btn btn-sm btn-outline dropdown-toggle" title="More">
                            <i class="fas fa-ellipsis-v"></i>
                        </button>
                        <div class="dropdown-menu">
                            <a href="#" onclick="documentGrid.editDocument(${doc.id})">Edit</a>
                            <a href="#" onclick="documentGrid.showRelated(${doc.id})">Related</a>
                            <a href="#" onclick="documentGrid.showVersions(${doc.id})">Versions</a>
                            <a href="#" onclick="documentGrid.deleteDocument(${doc.id})" class="text-danger">Delete</a>
                        </div>
                    </div>
                </div>
            </div>
        `).join('');

        gridContainer.innerHTML = documentsHTML;
        this.bindDocumentEvents();
    }

    renderListView(documents) {
        const gridContainer = document.getElementById('documentGrid');
        gridContainer.className = 'document-grid list-view';

        const documentsHTML = `
            <div class="list-header">
                <div class="list-cell checkbox-cell">
                    <input type="checkbox" id="selectAllCheckbox">
                </div>
                <div class="list-cell filename-cell">Filename</div>
                <div class="list-cell client-cell">Client</div>
                <div class="list-cell type-cell">Type</div>
                <div class="list-cell year-cell">Year</div>
                <div class="list-cell status-cell">Status</div>
                <div class="list-cell size-cell">Size</div>
                <div class="list-cell confidence-cell">Confidence</div>
                <div class="list-cell date-cell">Date</div>
                <div class="list-cell actions-cell">Actions</div>
            </div>

            ${documents.map(doc => `
                <div class="document-row" data-doc-id="${doc.id}">
                    <div class="list-cell checkbox-cell">
                        <input type="checkbox" class="document-checkbox" value="${doc.id}">
                    </div>

                    <div class="list-cell filename-cell" onclick="documentGrid.previewDocument(${doc.id})">
                        <div class="filename-info">
                            <span class="filename" title="${doc.original_filename}">
                                ${this.truncateText(doc.original_filename, 40)}
                            </span>
                            ${doc.annotation_count > 0 ? `<span class="annotation-indicator"><i class="fas fa-comment"></i></span>` : ''}
                        </div>
                    </div>

                    <div class="list-cell client-cell">
                        ${doc.client_name || 'Unknown'}
                    </div>

                    <div class="list-cell type-cell">
                        ${doc.document_type || 'Unknown'}
                    </div>

                    <div class="list-cell year-cell">
                        ${doc.tax_year || '-'}
                    </div>

                    <div class="list-cell status-cell">
                        <span class="status-badge ${doc.status}">
                            ${this.getStatusIcon(doc.status)} ${doc.status}
                        </span>
                    </div>

                    <div class="list-cell size-cell">
                        ${this.formatFileSize(doc.file_size_bytes)}
                    </div>

                    <div class="list-cell confidence-cell">
                        ${doc.confidence ? `<span class="confidence ${this.getConfidenceClass(doc.confidence)}">
                            ${Math.round(doc.confidence * 100)}%
                        </span>` : '-'}
                    </div>

                    <div class="list-cell date-cell">
                        ${new Date(doc.created_at).toLocaleDateString()}
                    </div>

                    <div class="list-cell actions-cell">
                        <button class="btn btn-sm btn-outline" onclick="documentGrid.previewDocument(${doc.id})" title="Preview">
                            <i class="fas fa-eye"></i>
                        </button>
                        <button class="btn btn-sm btn-outline" onclick="documentGrid.downloadDocument(${doc.id})" title="Download">
                            <i class="fas fa-download"></i>
                        </button>
                        <div class="dropdown">
                            <button class="btn btn-sm btn-outline dropdown-toggle">
                                <i class="fas fa-ellipsis-v"></i>
                            </button>
                            <div class="dropdown-menu">
                                <a href="#" onclick="documentGrid.editDocument(${doc.id})">Edit</a>
                                <a href="#" onclick="documentGrid.deleteDocument(${doc.id})" class="text-danger">Delete</a>
                            </div>
                        </div>
                    </div>
                </div>
            `).join('')}
        `;

        gridContainer.innerHTML = documentsHTML;
        this.bindDocumentEvents();
    }

    bindDocumentEvents() {
        // Checkbox handling
        this.container.querySelectorAll('.document-checkbox').forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                const docId = parseInt(e.target.value);
                if (e.target.checked) {
                    this.selectedDocuments.add(docId);
                } else {
                    this.selectedDocuments.delete(docId);
                }
                this.updateSelectionControls();
            });
        });

        // Select all checkbox in list view
        const selectAllCheckbox = document.getElementById('selectAllCheckbox');
        if (selectAllCheckbox) {
            selectAllCheckbox.addEventListener('change', (e) => {
                if (e.target.checked) {
                    this.selectAll();
                } else {
                    this.clearSelection();
                }
            });
        }
    }

    toggleViewMode(mode) {
        this.viewMode = mode;

        // Update button states
        this.container.querySelectorAll('.view-toggle').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.view === mode);
        });

        // Re-render with current documents
        this.displayDocuments(this.documents);
    }

    selectAll() {
        this.selectedDocuments.clear();
        this.documents.forEach(doc => {
            this.selectedDocuments.add(doc.id);
        });

        // Check all checkboxes
        this.container.querySelectorAll('.document-checkbox').forEach(checkbox => {
            checkbox.checked = true;
        });

        this.updateSelectionControls();
    }

    clearSelection() {
        this.selectedDocuments.clear();

        // Uncheck all checkboxes
        this.container.querySelectorAll('.document-checkbox').forEach(checkbox => {
            checkbox.checked = false;
        });

        const selectAllCheckbox = document.getElementById('selectAllCheckbox');
        if (selectAllCheckbox) {
            selectAllCheckbox.checked = false;
        }

        this.updateSelectionControls();
    }

    updateSelectionControls() {
        const count = this.selectedDocuments.size;
        const selectionControls = this.container.querySelector('.selection-controls');
        const bulkActions = this.container.querySelector('.bulk-actions');
        const selectionCount = this.container.querySelector('.selection-count');

        if (count > 0) {
            selectionControls.style.display = 'flex';
            bulkActions.style.display = 'flex';
            selectionCount.textContent = `${count} selected`;
        } else {
            selectionControls.style.display = 'none';
            bulkActions.style.display = 'none';
        }
    }

    // Document action methods
    async previewDocument(docId) {
        // This will be handled by the AnnotationTool module
        if (window.annotationTool) {
            window.annotationTool.openDocument(docId);
        }
    }

    async downloadDocument(docId) {
        try {
            const response = await fetch(`/api/documents/${docId}/download`);
            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `document_${docId}`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
            }
        } catch (error) {
            console.error('Download error:', error);
        }
    }

    async downloadSelected() {
        const selectedIds = Array.from(this.selectedDocuments);

        try {
            const response = await fetch('/api/documents/download-multiple', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ documentIds: selectedIds })
            });

            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `documents_${new Date().toISOString().split('T')[0]}.zip`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
            }
        } catch (error) {
            console.error('Bulk download error:', error);
        }
    }

    async deleteSelected() {
        if (!confirm(`Are you sure you want to delete ${this.selectedDocuments.size} document(s)?`)) {
            return;
        }

        const selectedIds = Array.from(this.selectedDocuments);

        try {
            const response = await fetch('/api/documents/delete-multiple', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ documentIds: selectedIds })
            });

            if (response.ok) {
                // Reload documents
                this.loadDocuments();
                this.clearSelection();
            }
        } catch (error) {
            console.error('Bulk delete error:', error);
        }
    }

    // Utility methods
    getThumbnail(doc) {
        const extension = doc.original_filename.split('.').pop().toLowerCase();

        if (['jpg', 'jpeg', 'png', 'gif'].includes(extension)) {
            return `<img src="/api/documents/${doc.id}/thumbnail" alt="Document thumbnail" onerror="this.src='/static/images/file-icon.png'">`;
        } else {
            return `<div class="file-icon">
                <i class="fas fa-file-${this.getFileIcon(extension)}"></i>
                <span class="extension">${extension}</span>
            </div>`;
        }
    }

    getFileIcon(extension) {
        const iconMap = {
            'pdf': 'pdf',
            'doc': 'word',
            'docx': 'word',
            'xls': 'excel',
            'xlsx': 'excel',
            'txt': 'alt',
            'csv': 'csv'
        };

        return iconMap[extension] || 'alt';
    }

    getStatusIcon(status) {
        const iconMap = {
            'completed': '<i class="fas fa-check-circle"></i>',
            'processing': '<i class="fas fa-spinner fa-spin"></i>',
            'error': '<i class="fas fa-exclamation-circle"></i>',
            'waiting': '<i class="fas fa-clock"></i>'
        };

        return iconMap[status] || '<i class="fas fa-question-circle"></i>';
    }

    getConfidenceClass(confidence) {
        if (confidence >= 0.8) return 'high';
        if (confidence >= 0.6) return 'medium';
        return 'low';
    }

    formatFileSize(bytes) {
        if (!bytes) return '0 B';

        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));

        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    truncateText(text, maxLength) {
        if (text.length <= maxLength) return text;
        return text.substring(0, maxLength) + '...';
    }

    showLoading() {
        document.getElementById('gridLoading').style.display = 'block';
        document.getElementById('documentGrid').style.display = 'none';
        document.getElementById('gridError').style.display = 'none';
    }

    hideLoading() {
        document.getElementById('gridLoading').style.display = 'none';
        document.getElementById('documentGrid').style.display = 'block';
    }

    showError(message) {
        document.getElementById('gridError').style.display = 'block';
        document.getElementById('gridError').querySelector('.error-message').textContent = message;
        document.getElementById('documentGrid').style.display = 'none';
        document.getElementById('gridLoading').style.display = 'none';
    }

    renderPagination(pagination) {
        const container = document.getElementById('paginationContainer');

        if (!pagination || pagination.totalPages <= 1) {
            container.innerHTML = '';
            return;
        }

        const { currentPage, totalPages, totalItems } = pagination;

        let paginationHTML = `
            <div class="pagination-info">
                Showing page ${currentPage} of ${totalPages} (${totalItems} total documents)
            </div>
            <div class="pagination-buttons">
        `;

        // Previous button
        if (currentPage > 1) {
            paginationHTML += `<button class="btn btn-outline pagination-btn" data-page="${currentPage - 1}">Previous</button>`;
        }

        // Page numbers
        for (let i = Math.max(1, currentPage - 2); i <= Math.min(totalPages, currentPage + 2); i++) {
            paginationHTML += `<button class="btn ${i === currentPage ? 'btn-primary' : 'btn-outline'} pagination-btn" data-page="${i}">${i}</button>`;
        }

        // Next button
        if (currentPage < totalPages) {
            paginationHTML += `<button class="btn btn-outline pagination-btn" data-page="${currentPage + 1}">Next</button>`;
        }

        paginationHTML += '</div>';

        container.innerHTML = paginationHTML;

        // Bind pagination events
        container.querySelectorAll('.pagination-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const page = parseInt(e.target.dataset.page);
                if (window.documentSearch) {
                    window.documentSearch.performSearch(page);
                }
            });
        });
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('documentGridContainer')) {
        window.documentGrid = new DocumentGrid('documentGridContainer');
    }
});