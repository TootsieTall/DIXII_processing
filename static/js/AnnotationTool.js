/**
 * AnnotationTool.js - Document Annotation and Preview Module
 * Handles document preview modal with annotation tools, metadata, and related documents
 */

class AnnotationTool {
    constructor() {
        this.currentDocument = null;
        this.annotations = [];
        this.isAnnotationMode = false;
        this.currentAnnotationType = 'note';
        this.modal = null;

        this.init();
    }

    init() {
        this.createModal();
        this.bindEvents();
    }

    createModal() {
        const modalHTML = `
            <div id="documentPreviewModal" class="modal" style="display: none;">
                <div class="modal-content large">
                    <div class="modal-header">
                        <h3 id="modalTitle">Document Preview</h3>
                        <div class="modal-actions">
                            <button class="btn btn-outline" id="downloadBtn">
                                <i class="fas fa-download"></i> Download
                            </button>
                            <button class="btn btn-outline" id="shareBtn">
                                <i class="fas fa-share"></i> Share
                            </button>
                            <button class="btn btn-outline" id="printBtn">
                                <i class="fas fa-print"></i> Print
                            </button>
                            <button class="modal-close" id="closeModal">
                                <i class="fas fa-times"></i>
                            </button>
                        </div>
                    </div>

                    <div class="modal-body">
                        <div class="document-viewer-container">
                            <div class="viewer-sidebar">
                                <div class="sidebar-tabs">
                                    <button class="tab-btn active" data-tab="metadata">
                                        <i class="fas fa-info-circle"></i> Metadata
                                    </button>
                                    <button class="tab-btn" data-tab="annotations">
                                        <i class="fas fa-comment"></i> Notes
                                        <span class="annotation-count" id="annotationCount">0</span>
                                    </button>
                                    <button class="tab-btn" data-tab="related">
                                        <i class="fas fa-link"></i> Related
                                    </button>
                                    <button class="tab-btn" data-tab="versions">
                                        <i class="fas fa-history"></i> Versions
                                    </button>
                                </div>

                                <div class="tab-content">
                                    <!-- Metadata Tab -->
                                    <div class="tab-panel active" id="metadataPanel">
                                        <div class="metadata-section">
                                            <h4>Document Information</h4>
                                            <div class="metadata-grid" id="documentMetadata">
                                                <!-- Metadata will be populated here -->
                                            </div>
                                        </div>

                                        <div class="metadata-section">
                                            <h4>Processing Details</h4>
                                            <div class="processing-info" id="processingInfo">
                                                <!-- Processing info will be populated here -->
                                            </div>
                                        </div>

                                        <div class="metadata-section">
                                            <h4>Client Information</h4>
                                            <div class="client-info" id="clientInfo">
                                                <!-- Client info will be populated here -->
                                            </div>
                                        </div>
                                    </div>

                                    <!-- Annotations Tab -->
                                    <div class="tab-panel" id="annotationsPanel">
                                        <div class="annotation-tools">
                                            <div class="tool-group">
                                                <label>Annotation Type:</label>
                                                <select id="annotationType">
                                                    <option value="note">Note</option>
                                                    <option value="highlight">Highlight</option>
                                                    <option value="approval">Approval</option>
                                                    <option value="flag">Flag Issue</option>
                                                </select>
                                            </div>

                                            <button class="btn btn-primary" id="addAnnotationBtn">
                                                <i class="fas fa-plus"></i> Add Note
                                            </button>
                                        </div>

                                        <div class="annotations-list" id="annotationsList">
                                            <!-- Annotations will be listed here -->
                                        </div>
                                    </div>

                                    <!-- Related Documents Tab -->
                                    <div class="tab-panel" id="relatedPanel">
                                        <div class="related-filters">
                                            <button class="btn btn-outline filter-btn active" data-filter="all">All</button>
                                            <button class="btn btn-outline filter-btn" data-filter="client">Same Client</button>
                                            <button class="btn btn-outline filter-btn" data-filter="year">Same Year</button>
                                            <button class="btn btn-outline filter-btn" data-filter="type">Same Type</button>
                                        </div>

                                        <div class="related-documents" id="relatedDocuments">
                                            <!-- Related documents will be listed here -->
                                        </div>
                                    </div>

                                    <!-- Versions Tab -->
                                    <div class="tab-panel" id="versionsPanel">
                                        <div class="version-actions">
                                            <button class="btn btn-outline" id="uploadNewVersion">
                                                <i class="fas fa-upload"></i> Upload New Version
                                            </button>
                                        </div>

                                        <div class="versions-list" id="versionsList">
                                            <!-- Version history will be listed here -->
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div class="document-preview">
                                <div class="preview-toolbar">
                                    <div class="zoom-controls">
                                        <button class="btn btn-sm btn-outline" id="zoomOut">
                                            <i class="fas fa-search-minus"></i>
                                        </button>
                                        <span class="zoom-level">100%</span>
                                        <button class="btn btn-sm btn-outline" id="zoomIn">
                                            <i class="fas fa-search-plus"></i>
                                        </button>
                                        <button class="btn btn-sm btn-outline" id="fitToWidth">
                                            <i class="fas fa-arrows-alt-h"></i> Fit Width
                                        </button>
                                    </div>

                                    <div class="page-controls" id="pageControls" style="display: none;">
                                        <button class="btn btn-sm btn-outline" id="prevPage">
                                            <i class="fas fa-chevron-left"></i>
                                        </button>
                                        <span id="pageInfo">Page 1 of 1</span>
                                        <button class="btn btn-sm btn-outline" id="nextPage">
                                            <i class="fas fa-chevron-right"></i>
                                        </button>
                                    </div>

                                    <div class="annotation-mode-toggle">
                                        <button class="btn btn-sm btn-outline" id="toggleAnnotationMode">
                                            <i class="fas fa-edit"></i> Annotation Mode
                                        </button>
                                    </div>
                                </div>

                                <div class="preview-container" id="previewContainer">
                                    <div class="preview-loading">
                                        <div class="loading-spinner"></div>
                                        <p>Loading document...</p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Annotation Dialog -->
            <div id="annotationDialog" class="modal" style="display: none;">
                <div class="modal-content small">
                    <div class="modal-header">
                        <h3>Add Annotation</h3>
                        <button class="modal-close" id="closeAnnotationDialog">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                    <div class="modal-body">
                        <form id="annotationForm">
                            <div class="form-group">
                                <label for="annotationTypeSelect">Type:</label>
                                <select id="annotationTypeSelect" required>
                                    <option value="note">Note</option>
                                    <option value="highlight">Highlight</option>
                                    <option value="approval">Approval</option>
                                    <option value="flag">Flag Issue</option>
                                </select>
                            </div>

                            <div class="form-group">
                                <label for="annotationContent">Content:</label>
                                <textarea id="annotationContent" required rows="4"
                                         placeholder="Enter your annotation..."></textarea>
                            </div>

                            <div class="form-actions">
                                <button type="button" class="btn btn-secondary" id="cancelAnnotation">Cancel</button>
                                <button type="submit" class="btn btn-primary">Save Annotation</button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHTML);
        this.modal = document.getElementById('documentPreviewModal');
    }

    bindEvents() {
        // Modal close events
        document.getElementById('closeModal').addEventListener('click', () => {
            this.closeModal();
        });

        document.getElementById('closeAnnotationDialog').addEventListener('click', () => {
            this.closeAnnotationDialog();
        });

        // Tab switching
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.switchTab(e.target.dataset.tab);
            });
        });

        // Document actions
        document.getElementById('downloadBtn').addEventListener('click', () => {
            this.downloadDocument();
        });

        document.getElementById('shareBtn').addEventListener('click', () => {
            this.shareDocument();
        });

        document.getElementById('printBtn').addEventListener('click', () => {
            this.printDocument();
        });

        // Annotation actions
        document.getElementById('addAnnotationBtn').addEventListener('click', () => {
            this.showAnnotationDialog();
        });

        document.getElementById('toggleAnnotationMode').addEventListener('click', () => {
            this.toggleAnnotationMode();
        });

        document.getElementById('annotationForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.saveAnnotation();
        });

        document.getElementById('cancelAnnotation').addEventListener('click', () => {
            this.closeAnnotationDialog();
        });

        // Zoom controls
        document.getElementById('zoomIn').addEventListener('click', () => {
            this.zoom(1.2);
        });

        document.getElementById('zoomOut').addEventListener('click', () => {
            this.zoom(0.8);
        });

        document.getElementById('fitToWidth').addEventListener('click', () => {
            this.fitToWidth();
        });

        // Related document filters
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.filterRelatedDocuments(e.target.dataset.filter);
            });
        });

        // Upload new version
        document.getElementById('uploadNewVersion').addEventListener('click', () => {
            this.uploadNewVersion();
        });

        // Click outside modal to close
        window.addEventListener('click', (e) => {
            if (e.target === this.modal) {
                this.closeModal();
            }
        });
    }

    async openDocument(documentId) {
        try {
            this.showModal();
            this.showLoading();

            // Load document data
            const response = await fetch(`/api/documents/${documentId}/full`);
            const result = await response.json();

            if (result.success) {
                this.currentDocument = result.data;
                this.displayDocument();
                this.loadAnnotations();
                this.loadRelatedDocuments();
                this.loadVersionHistory();
            } else {
                this.showError('Failed to load document');
            }
        } catch (error) {
            console.error('Error opening document:', error);
            this.showError('An error occurred while loading the document');
        }
    }

    displayDocument() {
        const doc = this.currentDocument;

        // Update modal title
        document.getElementById('modalTitle').textContent = doc.original_filename;

        // Display metadata
        this.displayMetadata();

        // Load preview
        this.loadPreview();

        this.hideLoading();
    }

    displayMetadata() {
        const doc = this.currentDocument;
        const metadataContainer = document.getElementById('documentMetadata');

        const metadata = [
            { label: 'Filename', value: doc.original_filename },
            { label: 'Client', value: doc.client_name || 'Unknown' },
            { label: 'Document Type', value: doc.document_type || 'Unknown' },
            { label: 'Tax Year', value: doc.tax_year || 'N/A' },
            { label: 'Status', value: doc.status },
            { label: 'File Size', value: this.formatFileSize(doc.file_size_bytes) },
            { label: 'Upload Date', value: new Date(doc.created_at).toLocaleString() },
            { label: 'Processing Time', value: doc.processing_time_seconds ? `${doc.processing_time_seconds}s` : 'N/A' }
        ];

        metadataContainer.innerHTML = metadata.map(item => `
            <div class="metadata-item">
                <span class="metadata-label">${item.label}:</span>
                <span class="metadata-value">${item.value}</span>
            </div>
        `).join('');

        // Display processing info
        const processingContainer = document.getElementById('processingInfo');
        processingContainer.innerHTML = `
            <div class="processing-item">
                <span class="processing-label">Confidence:</span>
                <span class="processing-value">
                    ${doc.confidence ? `${Math.round(doc.confidence * 100)}%` : 'N/A'}
                    ${doc.confidence ? `<div class="confidence-bar">
                        <div class="confidence-fill" style="width: ${doc.confidence * 100}%"></div>
                    </div>` : ''}
                </span>
            </div>
            ${doc.error_message ? `
                <div class="processing-item error">
                    <span class="processing-label">Error:</span>
                    <span class="processing-value">${doc.error_message}</span>
                </div>
            ` : ''}
        `;

        // Display client info if available
        if (doc.client_info) {
            const clientContainer = document.getElementById('clientInfo');
            clientContainer.innerHTML = `
                <div class="client-item">
                    <span class="client-label">Name:</span>
                    <span class="client-value">${doc.client_info.name}</span>
                </div>
                ${doc.client_info.email ? `
                    <div class="client-item">
                        <span class="client-label">Email:</span>
                        <span class="client-value">${doc.client_info.email}</span>
                    </div>
                ` : ''}
                ${doc.client_info.phone ? `
                    <div class="client-item">
                        <span class="client-label">Phone:</span>
                        <span class="client-value">${doc.client_info.phone}</span>
                    </div>
                ` : ''}
            `;
        }
    }

    async loadPreview() {
        const previewContainer = document.getElementById('previewContainer');
        const doc = this.currentDocument;

        // Check if we can show a preview
        const extension = doc.original_filename.split('.').pop().toLowerCase();

        if (['jpg', 'jpeg', 'png', 'gif'].includes(extension)) {
            // Image preview
            previewContainer.innerHTML = `
                <img src="/api/documents/${doc.id}/preview" alt="Document preview"
                     class="document-preview-image" id="previewImage">
            `;
        } else if (extension === 'pdf') {
            // PDF preview using iframe or PDF.js
            previewContainer.innerHTML = `
                <iframe src="/api/documents/${doc.id}/preview"
                        class="document-preview-pdf" id="previewPdf">
                </iframe>
            `;
        } else {
            // Text or other file types
            try {
                const response = await fetch(`/api/documents/${doc.id}/content`);
                const content = await response.text();

                previewContainer.innerHTML = `
                    <div class="document-preview-text">
                        <pre>${this.escapeHtml(content)}</pre>
                    </div>
                `;
            } catch (error) {
                previewContainer.innerHTML = `
                    <div class="preview-unavailable">
                        <i class="fas fa-file-alt fa-3x"></i>
                        <h3>Preview not available</h3>
                        <p>This file type cannot be previewed.</p>
                        <button class="btn btn-primary" onclick="annotationTool.downloadDocument()">
                            <i class="fas fa-download"></i> Download to view
                        </button>
                    </div>
                `;
            }
        }
    }

    async loadAnnotations() {
        try {
            const response = await fetch(`/api/documents/${this.currentDocument.id}/annotations`);
            const result = await response.json();

            if (result.success) {
                this.annotations = result.data;
                this.displayAnnotations();
                this.updateAnnotationCount();
            }
        } catch (error) {
            console.error('Error loading annotations:', error);
        }
    }

    displayAnnotations() {
        const container = document.getElementById('annotationsList');

        if (this.annotations.length === 0) {
            container.innerHTML = `
                <div class="no-annotations">
                    <i class="fas fa-comment fa-2x"></i>
                    <p>No annotations yet</p>
                    <button class="btn btn-primary" onclick="annotationTool.showAnnotationDialog()">
                        Add First Note
                    </button>
                </div>
            `;
            return;
        }

        const annotationsHTML = this.annotations.map(annotation => `
            <div class="annotation-item" data-annotation-id="${annotation.id}">
                <div class="annotation-header">
                    <span class="annotation-type ${annotation.annotation_type}">
                        ${this.getAnnotationIcon(annotation.annotation_type)} ${annotation.annotation_type}
                    </span>
                    <span class="annotation-date">
                        ${new Date(annotation.created_at).toLocaleDateString()}
                    </span>
                    <button class="btn btn-sm btn-outline annotation-delete"
                            onclick="annotationTool.deleteAnnotation(${annotation.id})">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
                <div class="annotation-content">
                    ${annotation.content}
                </div>
                ${annotation.created_by ? `
                    <div class="annotation-author">
                        by ${annotation.created_by}
                    </div>
                ` : ''}
            </div>
        `).join('');

        container.innerHTML = annotationsHTML;
    }

    async loadRelatedDocuments(filter = 'all') {
        try {
            const response = await fetch(`/api/documents/${this.currentDocument.id}/related?filter=${filter}`);
            const result = await response.json();

            if (result.success) {
                this.displayRelatedDocuments(result.data);
            }
        } catch (error) {
            console.error('Error loading related documents:', error);
        }
    }

    displayRelatedDocuments(documents) {
        const container = document.getElementById('relatedDocuments');

        if (documents.length === 0) {
            container.innerHTML = `
                <div class="no-related">
                    <i class="fas fa-link fa-2x"></i>
                    <p>No related documents found</p>
                </div>
            `;
            return;
        }

        const documentsHTML = documents.map(doc => `
            <div class="related-document-item" onclick="annotationTool.openDocument(${doc.id})">
                <div class="related-doc-info">
                    <h5>${doc.original_filename}</h5>
                    <div class="related-doc-meta">
                        <span class="client">${doc.client_name}</span>
                        <span class="type">${doc.document_type}</span>
                        ${doc.tax_year ? `<span class="year">${doc.tax_year}</span>` : ''}
                    </div>
                    <div class="related-doc-date">
                        ${new Date(doc.created_at).toLocaleDateString()}
                    </div>
                </div>
                <div class="related-doc-actions">
                    <button class="btn btn-sm btn-outline" onclick="event.stopPropagation(); annotationTool.downloadDocument(${doc.id})">
                        <i class="fas fa-download"></i>
                    </button>
                </div>
            </div>
        `).join('');

        container.innerHTML = documentsHTML;
    }

    async loadVersionHistory() {
        try {
            const response = await fetch(`/api/documents/${this.currentDocument.id}/versions`);
            const result = await response.json();

            if (result.success) {
                this.displayVersionHistory(result.data);
            }
        } catch (error) {
            console.error('Error loading version history:', error);
        }
    }

    displayVersionHistory(versions) {
        const container = document.getElementById('versionsList');

        if (versions.length === 0) {
            container.innerHTML = `
                <div class="no-versions">
                    <i class="fas fa-history fa-2x"></i>
                    <p>No version history available</p>
                </div>
            `;
            return;
        }

        const versionsHTML = versions.map((version, index) => `
            <div class="version-item ${index === 0 ? 'current' : ''}">
                <div class="version-info">
                    <div class="version-number">
                        Version ${version.version_number}
                        ${index === 0 ? '<span class="current-badge">Current</span>' : ''}
                    </div>
                    <div class="version-details">
                        <div class="version-size">${this.formatFileSize(version.file_size_bytes)}</div>
                        <div class="version-date">${new Date(version.created_at).toLocaleDateString()}</div>
                        ${version.upload_reason ? `<div class="version-reason">${version.upload_reason}</div>` : ''}
                        ${version.created_by ? `<div class="version-author">by ${version.created_by}</div>` : ''}
                    </div>
                </div>
                <div class="version-actions">
                    ${index !== 0 ? `
                        <button class="btn btn-sm btn-outline" onclick="annotationTool.downloadVersion(${version.id})">
                            <i class="fas fa-download"></i> Download
                        </button>
                        <button class="btn btn-sm btn-outline" onclick="annotationTool.revertToVersion(${version.id})">
                            <i class="fas fa-undo"></i> Revert
                        </button>
                    ` : ''}
                </div>
            </div>
        `).join('');

        container.innerHTML = versionsHTML;
    }

    // UI Helper Methods
    switchTab(tabName) {
        // Update tab buttons
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === tabName);
        });

        // Update tab panels
        document.querySelectorAll('.tab-panel').forEach(panel => {
            panel.classList.toggle('active', panel.id === `${tabName}Panel`);
        });
    }

    showModal() {
        this.modal.style.display = 'block';
        document.body.style.overflow = 'hidden';
    }

    closeModal() {
        this.modal.style.display = 'none';
        document.body.style.overflow = 'auto';
        this.currentDocument = null;
        this.annotations = [];
    }

    showAnnotationDialog() {
        document.getElementById('annotationDialog').style.display = 'block';
    }

    closeAnnotationDialog() {
        document.getElementById('annotationDialog').style.display = 'none';
        document.getElementById('annotationForm').reset();
    }

    showLoading() {
        document.querySelector('#previewContainer .preview-loading').style.display = 'block';
    }

    hideLoading() {
        document.querySelector('#previewContainer .preview-loading').style.display = 'none';
    }

    showError(message) {
        alert(message); // Replace with better error display
    }

    // Utility Methods
    getAnnotationIcon(type) {
        const icons = {
            'note': '<i class="fas fa-sticky-note"></i>',
            'highlight': '<i class="fas fa-highlighter"></i>',
            'approval': '<i class="fas fa-check"></i>',
            'flag': '<i class="fas fa-flag"></i>'
        };
        return icons[type] || '<i class="fas fa-comment"></i>';
    }

    formatFileSize(bytes) {
        if (!bytes) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    updateAnnotationCount() {
        const countElement = document.getElementById('annotationCount');
        countElement.textContent = this.annotations.length;
        countElement.style.display = this.annotations.length > 0 ? 'inline' : 'none';
    }

    // Document Actions
    async downloadDocument() {
        if (!this.currentDocument) return;

        try {
            const response = await fetch(`/api/documents/${this.currentDocument.id}/download`);
            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = this.currentDocument.original_filename;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
            }
        } catch (error) {
            console.error('Download error:', error);
        }
    }

    async saveAnnotation() {
        const type = document.getElementById('annotationTypeSelect').value;
        const content = document.getElementById('annotationContent').value;

        if (!content.trim()) return;

        try {
            const response = await fetch(`/api/documents/${this.currentDocument.id}/annotations`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    annotation_type: type,
                    content: content.trim()
                })
            });

            if (response.ok) {
                this.closeAnnotationDialog();
                this.loadAnnotations(); // Reload annotations
            }
        } catch (error) {
            console.error('Error saving annotation:', error);
        }
    }

    async deleteAnnotation(annotationId) {
        if (!confirm('Are you sure you want to delete this annotation?')) return;

        try {
            const response = await fetch(`/api/documents/${this.currentDocument.id}/annotations/${annotationId}`, {
                method: 'DELETE'
            });

            if (response.ok) {
                this.loadAnnotations(); // Reload annotations
            }
        } catch (error) {
            console.error('Error deleting annotation:', error);
        }
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    window.annotationTool = new AnnotationTool();
});