/* ============================================
   CONCALAB-UASD - Buscador Global
   ============================================ */

class SiteSearch {
    constructor() {
        this.searchInput = document.querySelector('.search-input');
        this.searchBtn = document.querySelector('.search-btn');
        this.resultsContainer = null;
        this.searchableContent = [];
        this.minChars = 3;
        
        if (this.searchInput) {
            this.init();
        }
    }

    init() {
        // Crear contenedor de resultados
        this.createResultsContainer();
        
        // Indexar contenido de la página actual
        this.indexPageContent();
        
        // Event listeners
        this.searchInput.addEventListener('input', this.debounce(this.handleSearch.bind(this), 300));
        this.searchBtn.addEventListener('click', (e) => {
            e.preventDefault();
            this.handleSearch();
        });
        
        // Cerrar resultados al hacer click fuera
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.search-container')) {
                this.hideResults();
            }
        });
        
        // Buscar con Enter
        this.searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                this.handleSearch();
            }
        });
    }

    createResultsContainer() {
        this.resultsContainer = document.createElement('div');
        this.resultsContainer.className = 'search-results';
        this.resultsContainer.style.cssText = `
            position: absolute;
            top: calc(100% + 10px);
            left: 0;
            right: 0;
            background: white;
            border-radius: 8px;
            box-shadow: 0 5px 20px rgba(0,0,0,0.15);
            max-height: 400px;
            overflow-y: auto;
            display: none;
            z-index: 1000;
        `;
        
        const searchContainer = this.searchInput.closest('.search-container');
        searchContainer.style.position = 'relative';
        searchContainer.appendChild(this.resultsContainer);
    }

    indexPageContent() {
        this.searchableContent = [];
        
        // Obtener título de la página
        const pageTitle = document.title;
        const pagePath = window.location.pathname;
        
        // Indexar encabezados
        const headings = document.querySelectorAll('h1, h2, h3, h4');
        headings.forEach(heading => {
            if (heading.textContent.trim() && !this.isInHeader(heading)) {
                this.searchableContent.push({
                    title: heading.textContent.trim(),
                    content: this.getContextText(heading),
                    type: 'heading',
                    element: heading,
                    page: pageTitle,
                    path: pagePath
                });
            }
        });
        
        // Indexar párrafos
        const paragraphs = document.querySelectorAll('p');
        paragraphs.forEach(p => {
            if (p.textContent.trim().length > 30 && !this.isInHeader(p)) {
                this.searchableContent.push({
                    title: this.getPreviousHeading(p),
                    content: p.textContent.trim(),
                    type: 'paragraph',
                    element: p,
                    page: pageTitle,
                    path: pagePath
                });
            }
        });
        
        // Indexar cards
        const cards = document.querySelectorAll('.card');
        cards.forEach(card => {
            const title = card.querySelector('.card-title, h3, h4');
            const content = card.querySelector('.card-text, p');
            
            if (title && content) {
                this.searchableContent.push({
                    title: title.textContent.trim(),
                    content: content.textContent.trim(),
                    type: 'card',
                    element: card,
                    page: pageTitle,
                    path: pagePath
                });
            }
        });
    }

    isInHeader(element) {
        return element.closest('.header') !== null;
    }

    getPreviousHeading(element) {
        let current = element.previousElementSibling;
        while (current) {
            if (current.matches('h1, h2, h3, h4, h5, h6')) {
                return current.textContent.trim();
            }
            current = current.previousElementSibling;
        }
        return 'Contenido';
    }

    getContextText(element) {
        let context = '';
        let sibling = element.nextElementSibling;
        let count = 0;
        
        while (sibling && count < 2) {
            if (sibling.matches('p')) {
                context += sibling.textContent.trim() + ' ';
                count++;
            }
            sibling = sibling.nextElementSibling;
        }
        
        return context.substring(0, 150) + (context.length > 150 ? '...' : '');
    }

    handleSearch() {
        const query = this.searchInput.value.trim().toLowerCase();
        
        if (query.length < this.minChars) {
            this.hideResults();
            return;
        }
        
        const results = this.search(query);
        this.displayResults(results, query);
    }

    search(query) {
        const results = [];
        const words = query.split(' ').filter(w => w.length > 0);
        
        this.searchableContent.forEach(item => {
            let score = 0;
            const titleLower = item.title.toLowerCase();
            const contentLower = item.content.toLowerCase();
            
            // Búsqueda exacta en título (mayor peso)
            if (titleLower.includes(query)) {
                score += 10;
            }
            
            // Búsqueda exacta en contenido
            if (contentLower.includes(query)) {
                score += 5;
            }
            
            // Búsqueda por palabras individuales
            words.forEach(word => {
                if (titleLower.includes(word)) score += 3;
                if (contentLower.includes(word)) score += 1;
            });
            
            if (score > 0) {
                results.push({ ...item, score });
            }
        });
        
        // Ordenar por score descendente
        return results.sort((a, b) => b.score - a.score).slice(0, 10);
    }

    displayResults(results, query) {
        if (results.length === 0) {
            this.resultsContainer.innerHTML = `
                <div style="padding: 1.5rem; text-align: center; color: #666;">
                    <p>No se encontraron resultados para "<strong>${this.escapeHtml(query)}</strong>"</p>
                </div>
            `;
            this.showResults();
            return;
        }
        
        let html = `
            <div style="padding: 0.75rem 1rem; background: #f8f9fa; border-bottom: 1px solid #e0e0e0; font-weight: 600; font-size: 0.875rem;">
                ${results.length} resultado(s) encontrado(s)
            </div>
        `;
        
        results.forEach(result => {
            const highlightedTitle = this.highlightText(result.title, query);
            const highlightedContent = this.highlightText(
                result.content.substring(0, 120) + (result.content.length > 120 ? '...' : ''),
                query
            );
            
            html += `
                <div class="search-result-item" style="
                    padding: 1rem;
                    border-bottom: 1px solid #e0e0e0;
                    cursor: pointer;
                    transition: background-color 0.2s;
                " onmouseover="this.style.backgroundColor='#f8f9fa'" 
                   onmouseout="this.style.backgroundColor='white'"
                   data-element-id="${this.getElementId(result.element)}">
                    <div style="font-weight: 600; color: var(--primary-color); margin-bottom: 0.25rem;">
                        ${highlightedTitle}
                    </div>
                    <div style="font-size: 0.875rem; color: #666; line-height: 1.5;">
                        ${highlightedContent}
                    </div>
                    <div style="font-size: 0.75rem; color: #999; margin-top: 0.25rem;">
                        <span style="text-transform: capitalize;">${result.type}</span> • ${result.page}
                    </div>
                </div>
            `;
        });
        
        this.resultsContainer.innerHTML = html;
        this.showResults();
        
        // Agregar event listeners a los resultados
        this.resultsContainer.querySelectorAll('.search-result-item').forEach((item, index) => {
            item.addEventListener('click', () => {
                this.scrollToResult(results[index].element);
                this.hideResults();
            });
        });
    }

    getElementId(element) {
        if (!element.id) {
            element.id = 'search-target-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
        }
        return element.id;
    }

    scrollToResult(element) {
        const headerOffset = 100;
        const elementPosition = element.getBoundingClientRect().top;
        const offsetPosition = elementPosition + window.pageYOffset - headerOffset;

        window.scrollTo({
            top: offsetPosition,
            behavior: 'smooth'
        });

        // Highlight temporal
        element.style.transition = 'background-color 0.5s';
        element.style.backgroundColor = '#fff3cd';
        
        setTimeout(() => {
            element.style.backgroundColor = '';
        }, 2000);
    }

    highlightText(text, query) {
        const words = query.split(' ').filter(w => w.length > 0);
        let highlightedText = this.escapeHtml(text);
        
        words.forEach(word => {
            const regex = new RegExp(`(${this.escapeRegex(word)})`, 'gi');
            highlightedText = highlightedText.replace(regex, '<mark style="background-color: #fdb913; padding: 0 2px;">$1</mark>');
        });
        
        return highlightedText;
    }

    showResults() {
        this.resultsContainer.style.display = 'block';
    }

    hideResults() {
        this.resultsContainer.style.display = 'none';
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    escapeRegex(string) {
        return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    debounce(func, wait) {
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
}

// Inicializar el buscador cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
    new SiteSearch();
    console.log('CONCALAB-UASD: Buscador inicializado');
});

