/* ============================================
   CONCALAB-UASD - Scroll Reveal Effect
   ============================================ */

class ScrollReveal {
    constructor(options = {}) {
        this.options = {
            threshold: options.threshold || 0.15,
            rootMargin: options.rootMargin || '0px 0px -50px 0px',
            revealClass: options.revealClass || 'reveal',
            activeClass: options.activeClass || 'active',
            once: options.once !== undefined ? options.once : true,
            ...options
        };
        
        this.observer = null;
        this.init();
    }

    init() {
        // Verificar soporte para IntersectionObserver
        if (!('IntersectionObserver' in window)) {
            console.warn('IntersectionObserver no soportado, aplicando fallback');
            this.fallback();
            return;
        }

        // Crear el observer
        this.observer = new IntersectionObserver(
            this.handleIntersection.bind(this),
            {
                threshold: this.options.threshold,
                rootMargin: this.options.rootMargin
            }
        );

        // Observar todos los elementos con la clase reveal
        this.observeElements();

        // Re-observar elementos cuando se añadan dinámicamente
        this.observeNewElements();
    }

    observeElements() {
        const elements = document.querySelectorAll(`.${this.options.revealClass}`);
        elements.forEach(element => {
            this.observer.observe(element);
        });
    }

    handleIntersection(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                // Elemento es visible
                entry.target.classList.add(this.options.activeClass);
                
                // Si only es true, dejar de observar después de revelar
                if (this.options.once) {
                    this.observer.unobserve(entry.target);
                }

                // Disparar evento personalizado
                const event = new CustomEvent('revealed', { 
                    detail: { element: entry.target }
                });
                entry.target.dispatchEvent(event);
            } else if (!this.options.once) {
                // Si once es false, ocultar cuando sale de vista
                entry.target.classList.remove(this.options.activeClass);
            }
        });
    }

    observeNewElements() {
        // MutationObserver para detectar nuevos elementos
        const mutationObserver = new MutationObserver(mutations => {
            mutations.forEach(mutation => {
                mutation.addedNodes.forEach(node => {
                    if (node.nodeType === 1) { // Element node
                        if (node.classList && node.classList.contains(this.options.revealClass)) {
                            this.observer.observe(node);
                        }
                        // Buscar elementos reveal dentro del nodo añadido
                        const reveals = node.querySelectorAll?.(`.${this.options.revealClass}`);
                        reveals?.forEach(element => {
                            this.observer.observe(element);
                        });
                    }
                });
            });
        });

        mutationObserver.observe(document.body, {
            childList: true,
            subtree: true
        });
    }

    fallback() {
        // Fallback para navegadores sin soporte
        const elements = document.querySelectorAll(`.${this.options.revealClass}`);
        elements.forEach(element => {
            element.classList.add(this.options.activeClass);
        });
    }

    // Método para revelar manualmente un elemento
    reveal(element) {
        if (element instanceof Element) {
            element.classList.add(this.options.activeClass);
            if (this.options.once && this.observer) {
                this.observer.unobserve(element);
            }
        }
    }

    // Método para ocultar manualmente un elemento
    hide(element) {
        if (element instanceof Element) {
            element.classList.remove(this.options.activeClass);
        }
    }

    // Método para resetear un elemento
    reset(element) {
        if (element instanceof Element) {
            element.classList.remove(this.options.activeClass);
            if (this.observer) {
                this.observer.observe(element);
            }
        }
    }

    // Destruir el observer
    destroy() {
        if (this.observer) {
            this.observer.disconnect();
            this.observer = null;
        }
    }
}

// Auto-inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
    // Configuración por defecto
    window.scrollReveal = new ScrollReveal({
        threshold: 0.15,
        once: true
    });

    // Agregar clase reveal automáticamente a elementos comunes
    autoAddRevealClasses();

    // Fallback: Si después de 2 segundos hay elementos reveal sin activar, activarlos
    setTimeout(() => {
        const hiddenElements = document.querySelectorAll('.reveal:not(.active)');
        if (hiddenElements.length > 0) {
            console.warn('CONCALAB-UASD: Activando fallback para elementos ocultos');
            hiddenElements.forEach(element => {
                // Solo activar elementos que están en el viewport o cerca
                const rect = element.getBoundingClientRect();
                const isNearViewport = rect.top < window.innerHeight + 500;
                if (isNearViewport) {
                    element.classList.add('active');
                }
            });
        }
    }, 2000);

    // Fallback adicional: Activar todos los elementos después de 5 segundos si aún hay ocultos
    setTimeout(() => {
        const stillHidden = document.querySelectorAll('.reveal:not(.active)');
        if (stillHidden.length > 0) {
            console.warn('CONCALAB-UASD: Activando fallback completo para todos los elementos');
            stillHidden.forEach(element => element.classList.add('active'));
        }
    }, 5000);

    console.log('CONCALAB-UASD: Scroll Reveal inicializado');
});

// Función auxiliar para agregar automáticamente clases reveal
function autoAddRevealClasses() {
    // NO agregar automáticamente clases reveal
    // Los elementos ya tienen la clase reveal en el HTML
    // Solo asegurar que elementos visibles inicialmente tengan la clase active
    
    // Elementos que están en el viewport inicial deben ser visibles inmediatamente
    const viewportHeight = window.innerHeight;
    document.querySelectorAll('.reveal').forEach(element => {
        const rect = element.getBoundingClientRect();
        // Si el elemento está en el viewport inicial, activarlo inmediatamente
        if (rect.top < viewportHeight && rect.bottom > 0) {
            element.classList.add('active');
        }
    });
}

// Utilidad para agregar reveal a elementos específicos
function addRevealToElements(selector, options = {}) {
    const elements = document.querySelectorAll(selector);
    elements.forEach((element, index) => {
        element.classList.add('reveal');
        
        if (options.direction) {
            element.classList.add(`reveal-${options.direction}`);
        }
        
        if (options.delay) {
            const delay = typeof options.delay === 'function' 
                ? options.delay(index) 
                : options.delay;
            element.classList.add(`reveal-delay-${delay}`);
        }
        
        if (options.stagger) {
            const staggerDelay = Math.min(index + 1, 5);
            element.classList.add(`reveal-delay-${staggerDelay}`);
        }
    });
}

// Exportar funciones para uso global
window.ScrollRevealUtils = {
    addRevealToElements,
    autoAddRevealClasses
};

// Reveal on scroll para tablas y listas largas (opcional)
// Comentado para evitar agregar automáticamente clases reveal
/*
document.addEventListener('DOMContentLoaded', () => {
    const tables = document.querySelectorAll('table');
    tables.forEach(table => {
        const rows = table.querySelectorAll('tbody tr');
        rows.forEach((row, index) => {
            if (index > 0) { // Skip header
                row.classList.add('reveal', 'reveal-scale');
                const delay = Math.min((index % 5) + 1, 5);
                row.classList.add(`reveal-delay-${delay}`);
            }
        });
    });
});
*/

