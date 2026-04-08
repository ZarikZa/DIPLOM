class ThemeManager {
    constructor() {
        this.theme = this.getInitialTheme();
        this.init();
    }

    getInitialTheme() {
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme) {
            return savedTheme;
        }
        
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
            return 'dark';
        }
        
        return 'light';
    }

    init() {
        this.applyTheme(this.theme);
        this.bindEvents();
        this.updateUserThemeInDatabase(this.theme);
    }

    applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
        
        this.updateToggleIcon(theme);
    }

    updateToggleIcon(theme) {
        const icon = document.querySelector('.theme-icon');
        if (icon) {
            icon.textContent = theme === 'dark' ? '🌙' : '☀️';
        }
    }

    async toggleTheme() {
        this.theme = this.theme === 'light' ? 'dark' : 'light';
        this.applyTheme(this.theme);
        
        await this.updateUserThemeInDatabase(this.theme);
    }

    async updateUserThemeInDatabase(theme) {
        if (!userData.isAuthenticated) return;

        try {
            const response = await fetch('/update-theme/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': userData.csrfToken
                },
                body: JSON.stringify({
                    theme: theme,
                    user_type: userData.userType
                })
            });

            if (!response.ok) {
                console.error('Ошибка при сохранении темы в БД');
            }
        } catch (error) {
            console.error('Ошибка:', error);
        }
    }

    bindEvents() {
        const toggleBtn = document.querySelector('.theme-toggle');
        if (toggleBtn) {
            toggleBtn.addEventListener('click', () => this.toggleTheme());
        }
    }

    getCurrentTheme() {
        return this.theme;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.themeManager = new ThemeManager();
});