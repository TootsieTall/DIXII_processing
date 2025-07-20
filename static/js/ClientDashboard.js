/**
 * ClientDashboard.js - Client Dashboard Management Module
 * Handles client profiles, document timelines, communication tracking, and client analytics
 */

class ClientDashboard {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.currentClient = null;
        this.clients = [];
        this.communications = [];
        this.viewMode = 'grid'; // 'grid' or 'list'

        this.init();
    }

    init() {
        this.createDashboardInterface();
        this.bindEvents();
        this.loadClients();
    }

    createDashboardInterface() {
        const dashboardHTML = `
            <div class="client-dashboard-container">
                <div class="dashboard-header">
                    <h2>Client Management Dashboard</h2>
                    <div class="dashboard-actions">
                        <button class="btn btn-primary" id="addClientBtn">
                            <i class="fas fa-plus"></i> Add New Client
                        </button>
                        <button class="btn btn-outline" id="exportClientsBtn">
                            <i class="fas fa-download"></i> Export Data
                        </button>
                        <button class="btn btn-outline" id="importClientsBtn">
                            <i class="fas fa-upload"></i> Import Clients
                        </button>
                    </div>
                </div>

                <div class="dashboard-filters">
                    <div class="filter-group">
                        <input type="text" id="clientSearch" placeholder="Search clients..." class="search-input">
                    </div>

                    <div class="filter-group">
                        <select id="businessTypeFilter">
                            <option value="">All Business Types</option>
                            <option value="individual">Individual</option>
                            <option value="partnership">Partnership</option>
                            <option value="corporation">Corporation</option>
                            <option value="llc">LLC</option>
                            <option value="nonprofit">Nonprofit</option>
                        </select>
                    </div>

                    <div class="filter-group">
                        <select id="complianceFilter">
                            <option value="">All Compliance Status</option>
                            <option value="current">Current</option>
                            <option value="pending">Pending</option>
                            <option value="overdue">Overdue</option>
                        </select>
                    </div>

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
                </div>

                <div class="dashboard-stats" id="dashboardStats">
                    <!-- Stats will be populated here -->
                </div>

                <div class="clients-container" id="clientsContainer">
                    <div class="loading-spinner" id="clientsLoading">
                        <div class="spinner"></div>
                        <p>Loading clients...</p>
                    </div>
                </div>
            </div>

            <!-- Client Detail Modal -->
            <div id="clientDetailModal" class="modal" style="display: none;">
                <div class="modal-content large">
                    <div class="modal-header">
                        <h3 id="clientModalTitle">Client Details</h3>
                        <div class="modal-actions">
                            <button class="btn btn-outline" id="editClientBtn">
                                <i class="fas fa-edit"></i> Edit
                            </button>
                            <button class="btn btn-outline" id="addCommunicationBtn">
                                <i class="fas fa-comment"></i> Add Note
                            </button>
                            <button class="modal-close" id="closeClientModal">
                                <i class="fas fa-times"></i>
                            </button>
                        </div>
                    </div>

                    <div class="modal-body">
                        <div class="client-detail-container">
                            <div class="client-sidebar">
                                <div class="client-profile" id="clientProfile">
                                    <!-- Client profile will be populated here -->
                                </div>

                                <div class="client-stats" id="clientStats">
                                    <!-- Client statistics will be populated here -->
                                </div>

                                <div class="client-actions">
                                    <button class="btn btn-primary btn-block" onclick="clientDashboard.viewClientDocuments()">
                                        <i class="fas fa-file-alt"></i> View All Documents
                                    </button>
                                    <button class="btn btn-outline btn-block" onclick="clientDashboard.generateClientReport()">
                                        <i class="fas fa-chart-bar"></i> Generate Report
                                    </button>
                                    <button class="btn btn-outline btn-block" onclick="clientDashboard.scheduleFollowUp()">
                                        <i class="fas fa-calendar"></i> Schedule Follow-up
                                    </button>
                                </div>
                            </div>

                            <div class="client-main-content">
                                <div class="client-tabs">
                                    <button class="tab-btn active" data-tab="documents">
                                        <i class="fas fa-file-alt"></i> Documents
                                    </button>
                                    <button class="tab-btn" data-tab="timeline">
                                        <i class="fas fa-clock"></i> Timeline
                                    </button>
                                    <button class="tab-btn" data-tab="communications">
                                        <i class="fas fa-comments"></i> Communications
                                    </button>
                                    <button class="tab-btn" data-tab="compliance">
                                        <i class="fas fa-check-circle"></i> Compliance
                                    </button>
                                </div>

                                <div class="tab-content">
                                    <!-- Documents Tab -->
                                    <div class="tab-panel active" id="documentsTab">
                                        <div class="documents-summary" id="documentsSummary">
                                            <!-- Documents summary will be populated here -->
                                        </div>

                                        <div class="recent-documents" id="recentDocuments">
                                            <!-- Recent documents will be listed here -->
                                        </div>
                                    </div>

                                    <!-- Timeline Tab -->
                                    <div class="tab-panel" id="timelineTab">
                                        <div class="timeline-container" id="clientTimeline">
                                            <!-- Timeline will be populated here -->
                                        </div>
                                    </div>

                                    <!-- Communications Tab -->
                                    <div class="tab-panel" id="communicationsTab">
                                        <div class="communications-list" id="communicationsList">
                                            <!-- Communications will be listed here -->
                                        </div>
                                    </div>

                                    <!-- Compliance Tab -->
                                    <div class="tab-panel" id="complianceTab">
                                        <div class="compliance-overview" id="complianceOverview">
                                            <!-- Compliance status will be shown here -->
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Add/Edit Client Modal -->
            <div id="clientFormModal" class="modal" style="display: none;">
                <div class="modal-content medium">
                    <div class="modal-header">
                        <h3 id="clientFormTitle">Add New Client</h3>
                        <button class="modal-close" id="closeClientFormModal">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                    <div class="modal-body">
                        <form id="clientForm">
                            <div class="form-row">
                                <div class="form-group">
                                    <label for="clientFirstName">First Name *</label>
                                    <input type="text" id="clientFirstName" name="first_name" required>
                                </div>
                                <div class="form-group">
                                    <label for="clientLastName">Last Name *</label>
                                    <input type="text" id="clientLastName" name="last_name" required>
                                </div>
                            </div>

                            <div class="form-row">
                                <div class="form-group">
                                    <label for="clientEmail">Email</label>
                                    <input type="email" id="clientEmail" name="email">
                                </div>
                                <div class="form-group">
                                    <label for="clientPhone">Phone</label>
                                    <input type="tel" id="clientPhone" name="phone">
                                </div>
                            </div>

                            <div class="form-row">
                                <div class="form-group">
                                    <label for="businessType">Business Type</label>
                                    <select id="businessType" name="business_type">
                                        <option value="individual">Individual</option>
                                        <option value="partnership">Partnership</option>
                                        <option value="corporation">Corporation</option>
                                        <option value="llc">LLC</option>
                                        <option value="nonprofit">Nonprofit</option>
                                    </select>
                                </div>
                                <div class="form-group">
                                    <label for="taxId">Tax ID / EIN</label>
                                    <input type="text" id="taxId" name="tax_id">
                                </div>
                            </div>

                            <div class="form-row">
                                <div class="form-group">
                                    <label for="preferredContact">Preferred Contact</label>
                                    <select id="preferredContact" name="preferred_contact">
                                        <option value="email">Email</option>
                                        <option value="phone">Phone</option>
                                        <option value="mail">Mail</option>
                                    </select>
                                </div>
                                <div class="form-group">
                                    <label for="filingFrequency">Filing Frequency</label>
                                    <select id="filingFrequency" name="filing_frequency">
                                        <option value="annual">Annual</option>
                                        <option value="quarterly">Quarterly</option>
                                        <option value="monthly">Monthly</option>
                                    </select>
                                </div>
                            </div>

                            <div class="form-group">
                                <label for="clientNotes">Notes</label>
                                <textarea id="clientNotes" name="notes" rows="3"
                                         placeholder="Additional notes about the client..."></textarea>
                            </div>

                            <div class="form-group">
                                <label class="checkbox-label">
                                    <input type="checkbox" id="portalAccess" name="portal_access">
                                    Enable Portal Access
                                </label>
                            </div>

                            <div class="form-actions">
                                <button type="button" class="btn btn-secondary" id="cancelClientForm">Cancel</button>
                                <button type="submit" class="btn btn-primary">Save Client</button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>

            <!-- Communication Modal -->
            <div id="communicationModal" class="modal" style="display: none;">
                <div class="modal-content medium">
                    <div class="modal-header">
                        <h3>Add Communication</h3>
                        <button class="modal-close" id="closeCommunicationModal">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                    <div class="modal-body">
                        <form id="communicationForm">
                            <div class="form-row">
                                <div class="form-group">
                                    <label for="communicationType">Type *</label>
                                    <select id="communicationType" name="communication_type" required>
                                        <option value="call">Phone Call</option>
                                        <option value="email">Email</option>
                                        <option value="meeting">Meeting</option>
                                        <option value="note">Note</option>
                                    </select>
                                </div>
                                <div class="form-group">
                                    <label for="communicationDate">Date *</label>
                                    <input type="datetime-local" id="communicationDate"
                                           name="communication_date" required>
                                </div>
                            </div>

                            <div class="form-group">
                                <label for="communicationSubject">Subject *</label>
                                <input type="text" id="communicationSubject" name="subject"
                                       placeholder="Brief description of the communication" required>
                            </div>

                            <div class="form-group">
                                <label for="communicationContent">Details</label>
                                <textarea id="communicationContent" name="content" rows="4"
                                         placeholder="Detailed notes about the communication..."></textarea>
                            </div>

                            <div class="form-actions">
                                <button type="button" class="btn btn-secondary" id="cancelCommunication">Cancel</button>
                                <button type="submit" class="btn btn-primary">Save Communication</button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        `;

        this.container.innerHTML = dashboardHTML;
    }

    bindEvents() {
        // Search and filters
        document.getElementById('clientSearch').addEventListener('input', (e) => {
            this.filterClients();
        });

        document.getElementById('businessTypeFilter').addEventListener('change', () => {
            this.filterClients();
        });

        document.getElementById('complianceFilter').addEventListener('change', () => {
            this.filterClients();
        });

        // View mode toggle
        document.querySelectorAll('.view-toggle').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.toggleViewMode(e.target.dataset.view);
            });
        });

        // Dashboard actions
        document.getElementById('addClientBtn').addEventListener('click', () => {
            this.showClientForm();
        });

        document.getElementById('exportClientsBtn').addEventListener('click', () => {
            this.exportClients();
        });

        // Modal events
        document.getElementById('closeClientModal').addEventListener('click', () => {
            this.closeClientModal();
        });

        document.getElementById('closeClientFormModal').addEventListener('click', () => {
            this.closeClientFormModal();
        });

        document.getElementById('closeCommunicationModal').addEventListener('click', () => {
            this.closeCommunicationModal();
        });

        // Form submissions
        document.getElementById('clientForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.saveClient();
        });

        document.getElementById('communicationForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.saveCommunication();
        });

        // Tab switching in client detail modal
        document.addEventListener('click', (e) => {
            if (e.target.matches('.tab-btn')) {
                this.switchClientTab(e.target.dataset.tab);
            }
        });

        // Cancel buttons
        document.getElementById('cancelClientForm').addEventListener('click', () => {
            this.closeClientFormModal();
        });

        document.getElementById('cancelCommunication').addEventListener('click', () => {
            this.closeCommunicationModal();
        });
    }

    async loadClients() {
        this.showLoading();

        try {
            const response = await fetch('/api/clients/dashboard');
            const result = await response.json();

            if (result.success) {
                this.clients = result.data;
                this.displayClients();
                this.updateDashboardStats();
            } else {
                this.showError('Failed to load clients');
            }
        } catch (error) {
            console.error('Error loading clients:', error);
            this.showError('An error occurred while loading clients');
        }
    }

    displayClients() {
        const container = document.getElementById('clientsContainer');

        if (this.clients.length === 0) {
            container.innerHTML = `
                <div class="no-clients">
                    <i class="fas fa-users fa-3x"></i>
                    <h3>No clients found</h3>
                    <p>Start by adding your first client.</p>
                    <button class="btn btn-primary" onclick="clientDashboard.showClientForm()">
                        <i class="fas fa-plus"></i> Add First Client
                    </button>
                </div>
            `;
            return;
        }

        if (this.viewMode === 'grid') {
            this.displayClientsGrid();
        } else {
            this.displayClientsList();
        }

        this.hideLoading();
    }

    displayClientsGrid() {
        const container = document.getElementById('clientsContainer');
        container.className = 'clients-container grid-view';

        const clientsHTML = this.clients.map(client => `
            <div class="client-card" onclick="clientDashboard.showClientDetail(${client.id})">
                <div class="client-header">
                    <div class="client-avatar">
                        ${this.getClientInitials(client.first_name, client.last_name)}
                    </div>
                    <div class="client-status ${client.compliance_status}">
                        ${this.getComplianceIcon(client.compliance_status)}
                    </div>
                </div>

                <div class="client-info">
                    <h4 class="client-name">${client.name}</h4>

                    <div class="client-meta">
                        ${client.business_type ? `<span class="business-type">${client.business_type}</span>` : ''}
                        ${client.email ? `<span class="email"><i class="fas fa-envelope"></i> ${client.email}</span>` : ''}
                        ${client.phone ? `<span class="phone"><i class="fas fa-phone"></i> ${client.phone}</span>` : ''}
                    </div>

                    <div class="client-stats">
                        <div class="stat-item">
                            <span class="stat-value">${client.total_documents || 0}</span>
                            <span class="stat-label">Documents</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-value">${client.unique_tax_years || 0}</span>
                            <span class="stat-label">Tax Years</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-value">${client.communication_count || 0}</span>
                            <span class="stat-label">Notes</span>
                        </div>
                    </div>

                    ${client.last_document_date ? `
                        <div class="last-activity">
                            Last activity: ${new Date(client.last_document_date).toLocaleDateString()}
                        </div>
                    ` : ''}
                </div>

                <div class="client-actions" onclick="event.stopPropagation()">
                    <button class="btn btn-sm btn-outline" onclick="clientDashboard.editClient(${client.id})" title="Edit">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="btn btn-sm btn-outline" onclick="clientDashboard.addCommunication(${client.id})" title="Add Note">
                        <i class="fas fa-comment"></i>
                    </button>
                    <button class="btn btn-sm btn-outline" onclick="clientDashboard.viewClientDocuments(${client.id})" title="Documents">
                        <i class="fas fa-file-alt"></i>
                    </button>
                </div>
            </div>
        `).join('');

        container.innerHTML = clientsHTML;
    }

    displayClientsList() {
        const container = document.getElementById('clientsContainer');
        container.className = 'clients-container list-view';

        const clientsHTML = `
            <div class="clients-table">
                <div class="table-header">
                    <div class="table-cell name-cell">Name</div>
                    <div class="table-cell business-cell">Business Type</div>
                    <div class="table-cell contact-cell">Contact</div>
                    <div class="table-cell documents-cell">Documents</div>
                    <div class="table-cell status-cell">Status</div>
                    <div class="table-cell activity-cell">Last Activity</div>
                    <div class="table-cell actions-cell">Actions</div>
                </div>

                ${this.clients.map(client => `
                    <div class="table-row" onclick="clientDashboard.showClientDetail(${client.id})">
                        <div class="table-cell name-cell">
                            <div class="client-name-info">
                                <div class="client-avatar-small">
                                    ${this.getClientInitials(client.first_name, client.last_name)}
                                </div>
                                <div>
                                    <div class="client-name">${client.name}</div>
                                    ${client.tax_id ? `<div class="tax-id">${client.tax_id}</div>` : ''}
                                </div>
                            </div>
                        </div>

                        <div class="table-cell business-cell">
                            ${client.business_type || 'N/A'}
                        </div>

                        <div class="table-cell contact-cell">
                            <div class="contact-info">
                                ${client.email ? `<div><i class="fas fa-envelope"></i> ${client.email}</div>` : ''}
                                ${client.phone ? `<div><i class="fas fa-phone"></i> ${client.phone}</div>` : ''}
                            </div>
                        </div>

                        <div class="table-cell documents-cell">
                            <span class="document-count">${client.total_documents || 0}</span>
                            ${client.error_documents > 0 ? `<span class="error-count">(${client.error_documents} errors)</span>` : ''}
                        </div>

                        <div class="table-cell status-cell">
                            <span class="status-badge ${client.compliance_status}">
                                ${this.getComplianceIcon(client.compliance_status)} ${client.compliance_status}
                            </span>
                        </div>

                        <div class="table-cell activity-cell">
                            ${client.last_document_date ?
                                new Date(client.last_document_date).toLocaleDateString() :
                                'No activity'
                            }
                        </div>

                        <div class="table-cell actions-cell" onclick="event.stopPropagation()">
                            <button class="btn btn-sm btn-outline" onclick="clientDashboard.editClient(${client.id})">
                                <i class="fas fa-edit"></i>
                            </button>
                            <button class="btn btn-sm btn-outline" onclick="clientDashboard.addCommunication(${client.id})">
                                <i class="fas fa-comment"></i>
                            </button>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;

        container.innerHTML = clientsHTML;
    }

    updateDashboardStats() {
        const statsContainer = document.getElementById('dashboardStats');

        const totalClients = this.clients.length;
        const activeClients = this.clients.filter(c => c.total_documents > 0).length;
        const overdueClients = this.clients.filter(c => c.compliance_status === 'overdue').length;
        const totalDocuments = this.clients.reduce((sum, c) => sum + (c.total_documents || 0), 0);

        statsContainer.innerHTML = `
            <div class="stat-card">
                <div class="stat-icon">
                    <i class="fas fa-users"></i>
                </div>
                <div class="stat-info">
                    <div class="stat-value">${totalClients}</div>
                    <div class="stat-label">Total Clients</div>
                </div>
            </div>

            <div class="stat-card">
                <div class="stat-icon">
                    <i class="fas fa-user-check"></i>
                </div>
                <div class="stat-info">
                    <div class="stat-value">${activeClients}</div>
                    <div class="stat-label">Active Clients</div>
                </div>
            </div>

            <div class="stat-card ${overdueClients > 0 ? 'warning' : ''}">
                <div class="stat-icon">
                    <i class="fas fa-exclamation-triangle"></i>
                </div>
                <div class="stat-info">
                    <div class="stat-value">${overdueClients}</div>
                    <div class="stat-label">Overdue</div>
                </div>
            </div>

            <div class="stat-card">
                <div class="stat-icon">
                    <i class="fas fa-file-alt"></i>
                </div>
                <div class="stat-info">
                    <div class="stat-value">${totalDocuments}</div>
                    <div class="stat-label">Total Documents</div>
                </div>
            </div>
        `;
    }

    // Client Detail Modal Methods
    async showClientDetail(clientId) {
        this.currentClient = this.clients.find(c => c.id === clientId);
        if (!this.currentClient) return;

        this.showClientModal();
        this.loadClientDetails();
    }

    async loadClientDetails() {
        try {
            // Load full client data including communications and recent activity
            const [clientResponse, communicationsResponse] = await Promise.all([
                fetch(`/api/clients/${this.currentClient.id}/full`),
                fetch(`/api/clients/${this.currentClient.id}/communications`)
            ]);

            const clientResult = await clientResponse.json();
            const communicationsResult = await communicationsResponse.json();

            if (clientResult.success) {
                this.currentClient = { ...this.currentClient, ...clientResult.data };
                this.displayClientProfile();
                this.displayClientDocuments();
                this.displayClientTimeline();
            }

            if (communicationsResult.success) {
                this.communications = communicationsResult.data;
                this.displayClientCommunications();
            }
        } catch (error) {
            console.error('Error loading client details:', error);
        }
    }

    displayClientProfile() {
        const profileContainer = document.getElementById('clientProfile');
        const client = this.currentClient;

        document.getElementById('clientModalTitle').textContent = client.name;

        profileContainer.innerHTML = `
            <div class="profile-header">
                <div class="client-avatar-large">
                    ${this.getClientInitials(client.first_name, client.last_name)}
                </div>
                <div class="profile-info">
                    <h3>${client.name}</h3>
                    <p class="business-type">${client.business_type || 'Individual'}</p>
                    <p class="compliance-status ${client.compliance_status}">
                        ${this.getComplianceIcon(client.compliance_status)} ${client.compliance_status}
                    </p>
                </div>
            </div>

            <div class="profile-details">
                ${client.email ? `
                    <div class="detail-item">
                        <i class="fas fa-envelope"></i>
                        <span>${client.email}</span>
                    </div>
                ` : ''}

                ${client.phone ? `
                    <div class="detail-item">
                        <i class="fas fa-phone"></i>
                        <span>${client.phone}</span>
                    </div>
                ` : ''}

                ${client.tax_id ? `
                    <div class="detail-item">
                        <i class="fas fa-id-card"></i>
                        <span>${client.tax_id}</span>
                    </div>
                ` : ''}

                <div class="detail-item">
                    <i class="fas fa-calendar"></i>
                    <span>Filing: ${client.filing_frequency || 'Annual'}</span>
                </div>

                <div class="detail-item">
                    <i class="fas fa-comment"></i>
                    <span>Contact: ${client.preferred_contact || 'Email'}</span>
                </div>

                ${client.portal_access ? `
                    <div class="detail-item">
                        <i class="fas fa-globe"></i>
                        <span>Portal Access Enabled</span>
                    </div>
                ` : ''}
            </div>

            ${client.profile_notes ? `
                <div class="profile-notes">
                    <h4>Notes</h4>
                    <p>${client.profile_notes}</p>
                </div>
            ` : ''}
        `;

        // Update client stats
        const statsContainer = document.getElementById('clientStats');
        statsContainer.innerHTML = `
            <div class="client-stat">
                <div class="stat-value">${client.total_documents || 0}</div>
                <div class="stat-label">Total Documents</div>
            </div>
            <div class="client-stat">
                <div class="stat-value">${client.completed_documents || 0}</div>
                <div class="stat-label">Completed</div>
            </div>
            <div class="client-stat">
                <div class="stat-value">${client.error_documents || 0}</div>
                <div class="stat-label">Errors</div>
            </div>
            <div class="client-stat">
                <div class="stat-value">${client.unique_tax_years || 0}</div>
                <div class="stat-label">Tax Years</div>
            </div>
        `;
    }

    // Utility Methods
    getClientInitials(firstName, lastName) {
        const first = firstName ? firstName.charAt(0).toUpperCase() : '';
        const last = lastName ? lastName.charAt(0).toUpperCase() : '';
        return first + last;
    }

    getComplianceIcon(status) {
        const icons = {
            'current': '<i class="fas fa-check-circle"></i>',
            'pending': '<i class="fas fa-clock"></i>',
            'overdue': '<i class="fas fa-exclamation-triangle"></i>'
        };
        return icons[status] || '<i class="fas fa-question-circle"></i>';
    }

    toggleViewMode(mode) {
        this.viewMode = mode;

        // Update button states
        document.querySelectorAll('.view-toggle').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.view === mode);
        });

        this.displayClients();
    }

    filterClients() {
        const search = document.getElementById('clientSearch').value.toLowerCase();
        const businessType = document.getElementById('businessTypeFilter').value;
        const compliance = document.getElementById('complianceFilter').value;

        // This would filter the clients array and re-display
        // Implementation would depend on your filtering requirements
        this.displayClients();
    }

    showLoading() {
        document.getElementById('clientsLoading').style.display = 'flex';
    }

    hideLoading() {
        document.getElementById('clientsLoading').style.display = 'none';
    }

    showError(message) {
        console.error(message);
        // Implement error display
    }

    // Modal management
    showClientModal() {
        document.getElementById('clientDetailModal').style.display = 'block';
        document.body.style.overflow = 'hidden';
    }

    closeClientModal() {
        document.getElementById('clientDetailModal').style.display = 'none';
        document.body.style.overflow = 'auto';
        this.currentClient = null;
    }

    showClientForm(clientId = null) {
        const modal = document.getElementById('clientFormModal');
        const title = document.getElementById('clientFormTitle');

        if (clientId) {
            title.textContent = 'Edit Client';
            // Load client data into form
            const client = this.clients.find(c => c.id === clientId);
            if (client) {
                this.populateClientForm(client);
            }
        } else {
            title.textContent = 'Add New Client';
            document.getElementById('clientForm').reset();
        }

        modal.style.display = 'block';
        document.body.style.overflow = 'hidden';
    }

    closeClientFormModal() {
        document.getElementById('clientFormModal').style.display = 'none';
        document.body.style.overflow = 'auto';
    }

    showCommunicationModal() {
        const modal = document.getElementById('communicationModal');
        // Set default date to now
        document.getElementById('communicationDate').value = new Date().toISOString().slice(0, 16);
        modal.style.display = 'block';
        document.body.style.overflow = 'hidden';
    }

    closeCommunicationModal() {
        document.getElementById('communicationModal').style.display = 'none';
        document.body.style.overflow = 'auto';
        document.getElementById('communicationForm').reset();
    }

    switchClientTab(tabName) {
        // Update tab buttons
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === tabName);
        });

        // Update tab panels
        document.querySelectorAll('.tab-panel').forEach(panel => {
            panel.classList.toggle('active', panel.id === `${tabName}Tab`);
        });
    }

    // API Methods
    async saveClient() {
        const formData = new FormData(document.getElementById('clientForm'));
        const clientData = Object.fromEntries(formData);

        try {
            const url = this.currentClient ?
                `/api/clients/${this.currentClient.id}` :
                '/api/clients';

            const method = this.currentClient ? 'PUT' : 'POST';

            const response = await fetch(url, {
                method: method,
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(clientData)
            });

            if (response.ok) {
                this.closeClientFormModal();
                this.loadClients(); // Reload clients list
            }
        } catch (error) {
            console.error('Error saving client:', error);
        }
    }

    async saveCommunication() {
        if (!this.currentClient) return;

        const formData = new FormData(document.getElementById('communicationForm'));
        const communicationData = Object.fromEntries(formData);

        try {
            const response = await fetch(`/api/clients/${this.currentClient.id}/communications`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(communicationData)
            });

            if (response.ok) {
                this.closeCommunicationModal();
                this.loadClientDetails(); // Reload client details
            }
        } catch (error) {
            console.error('Error saving communication:', error);
        }
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('clientDashboardContainer')) {
        window.clientDashboard = new ClientDashboard('clientDashboardContainer');
    }
});