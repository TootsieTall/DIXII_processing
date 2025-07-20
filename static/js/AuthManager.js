/**
 * Authentication Manager
 * Handles user authentication state and session management
 */

class AuthManager {
    constructor() {
        this.currentUser = null;
        this.session = null;
        this.authCallbacks = [];
        this.init();
    }

    async init() {
        try {
            // Check for existing session in storage
            const savedSession = this.getSavedSession();
            if (savedSession && savedSession.access_token) {
                // Verify session with backend
                const isValid = await this.verifySession(savedSession.access_token);
                if (isValid) {
                    this.session = savedSession;
                    this.currentUser = savedSession.user;
                    this.notifyAuthChange('SIGNED_IN');
                } else {
                    this.clearSession();
                }
            }

            // Set up automatic token refresh
            this.setupTokenRefresh();
        } catch (error) {
            console.error('Auth initialization error:', error);
            this.clearSession();
        }
    }

    // Session management
    getSavedSession() {
        // Try localStorage first (remember me), then sessionStorage
        const stored = localStorage.getItem('auth_session') || sessionStorage.getItem('auth_session');
        return stored ? JSON.parse(stored) : null;
    }

    saveSession(session, remember = false) {
        const sessionData = {
            access_token: session.access_token,
            refresh_token: session.refresh_token,
            expires_at: session.expires_at,
            user: session.user
        };

        if (remember) {
            localStorage.setItem('auth_session', JSON.stringify(sessionData));
        } else {
            sessionStorage.setItem('auth_session', JSON.stringify(sessionData));
        }

        this.session = sessionData;
        this.currentUser = session.user;
    }

    clearSession() {
        localStorage.removeItem('auth_session');
        sessionStorage.removeItem('auth_session');
        this.session = null;
        this.currentUser = null;
        this.notifyAuthChange('SIGNED_OUT');
    }

    // Authentication methods
    async signIn(email, password, remember = false) {
        try {
            const response = await this.apiCall('/api/auth/signin', {
                method: 'POST',
                body: JSON.stringify({
                    email: email,
                    password: password
                })
            });

            if (response.success) {
                this.saveSession(response.session, remember);
                this.notifyAuthChange('SIGNED_IN');
                return response;
            } else {
                throw new Error(response.error || 'Sign in failed');
            }
        } catch (error) {
            console.error('Sign in error:', error);
            throw error;
        }
    }

    async signUp(email, password, userData = {}) {
        try {
            const response = await this.apiCall('/api/auth/signup', {
                method: 'POST',
                body: JSON.stringify({
                    email: email,
                    password: password,
                    first_name: userData.firstName,
                    last_name: userData.lastName
                })
            });

            if (response.success) {
                if (response.session) {
                    this.saveSession(response.session, false);
                    this.notifyAuthChange('SIGNED_IN');
                }
                return response;
            } else {
                throw new Error(response.error || 'Sign up failed');
            }
        } catch (error) {
            console.error('Sign up error:', error);
            throw error;
        }
    }

    async signOut() {
        try {
            if (this.session?.access_token) {
                await this.apiCall('/api/auth/signout', {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${this.session.access_token}`
                    }
                });
            }
        } catch (error) {
            console.error('Sign out error:', error);
        } finally {
            this.clearSession();
            // Redirect to auth page
            window.location.href = '/auth';
        }
    }

    async verifySession(token) {
        try {
            const response = await this.apiCall('/api/auth/user', {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            return response.success;
        } catch (error) {
            return false;
        }
    }

    async refreshToken() {
        if (!this.session?.refresh_token) {
            throw new Error('No refresh token available');
        }

        try {
            const response = await this.apiCall('/api/auth/refresh', {
                method: 'POST',
                body: JSON.stringify({
                    refresh_token: this.session.refresh_token
                })
            });

            if (response.success) {
                // Update session with new tokens
                const wasRemembered = localStorage.getItem('auth_session') !== null;
                this.saveSession(response.session, wasRemembered);
                return response.session;
            } else {
                throw new Error('Token refresh failed');
            }
        } catch (error) {
            console.error('Token refresh error:', error);
            this.clearSession();
            throw error;
        }
    }

    setupTokenRefresh() {
        // Check token expiration every minute
        setInterval(() => {
            if (this.session?.expires_at) {
                const expiresAt = new Date(this.session.expires_at * 1000);
                const now = new Date();
                const timeUntilExpiry = expiresAt.getTime() - now.getTime();

                // Refresh token if it expires in the next 5 minutes
                if (timeUntilExpiry < 5 * 60 * 1000 && timeUntilExpiry > 0) {
                    this.refreshToken().catch(error => {
                        console.error('Automatic token refresh failed:', error);
                    });
                }
            }
        }, 60000); // Check every minute
    }

    // Event handling
    onAuthStateChange(callback) {
        this.authCallbacks.push(callback);

        // Return unsubscribe function
        return () => {
            const index = this.authCallbacks.indexOf(callback);
            if (index > -1) {
                this.authCallbacks.splice(index, 1);
            }
        };
    }

    notifyAuthChange(event) {
        this.authCallbacks.forEach(callback => {
            try {
                callback(event, this.session, this.currentUser);
            } catch (error) {
                console.error('Auth callback error:', error);
            }
        });
    }

    // API utilities
    async apiCall(url, options = {}) {
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            }
        };

        const response = await fetch(url, { ...defaultOptions, ...options });

        if (!response.ok) {
            const error = await response.json().catch(() => ({ error: 'Network error' }));
            throw new Error(error.error || `HTTP ${response.status}`);
        }

        return await response.json();
    }

    async makeAuthenticatedRequest(url, options = {}) {
        if (!this.session?.access_token) {
            throw new Error('No authentication token available');
        }

        const authOptions = {
            ...options,
            headers: {
                'Authorization': `Bearer ${this.session.access_token}`,
                ...options.headers
            }
        };

        try {
            return await this.apiCall(url, authOptions);
        } catch (error) {
            // If token is expired, try to refresh and retry
            if (error.message.includes('expired') || error.message.includes('401')) {
                try {
                    await this.refreshToken();
                    authOptions.headers['Authorization'] = `Bearer ${this.session.access_token}`;
                    return await this.apiCall(url, authOptions);
                } catch (refreshError) {
                    console.error('Token refresh failed during retry:', refreshError);
                    this.clearSession();
                    throw new Error('Authentication expired. Please sign in again.');
                }
            }
            throw error;
        }
    }

    // Getters
    isAuthenticated() {
        return this.currentUser !== null && this.session !== null;
    }

    getCurrentUser() {
        return this.currentUser;
    }

    getAccessToken() {
        return this.session?.access_token;
    }

    getUserEmail() {
        return this.currentUser?.email;
    }

    getUserMetadata() {
        return this.currentUser?.user_metadata || {};
    }

    // Utility methods
    requireAuth() {
        if (!this.isAuthenticated()) {
            window.location.href = '/auth';
            return false;
        }
        return true;
    }

    redirectToAuth() {
        window.location.href = '/auth';
    }

    redirectToApp() {
        window.location.href = '/';
    }
}

// Create global auth manager instance
window.authManager = new AuthManager();

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AuthManager;
}

// Auto-redirect if not authenticated (for protected pages)
document.addEventListener('DOMContentLoaded', () => {
    // Check if current page requires authentication
    const requiresAuth = document.body.dataset.requiresAuth === 'true';

    if (requiresAuth && !window.authManager.isAuthenticated()) {
        window.authManager.redirectToAuth();
    }
});

// Handle authentication errors globally
window.addEventListener('unhandledrejection', (event) => {
    if (event.reason && event.reason.message &&
        (event.reason.message.includes('Authentication') ||
         event.reason.message.includes('401') ||
         event.reason.message.includes('expired'))) {

        console.warn('Authentication error detected:', event.reason.message);
        window.authManager.clearSession();
    }
});