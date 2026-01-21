/* ============================================
   CONCALAB-UASD - JavaScript Principal
   ============================================ */

// Esperar a que el DOM esté completamente cargado
document.addEventListener('DOMContentLoaded', function() {
    
    // ==========================================
    // NAVEGACIÓN MÓVIL
    // ==========================================
    const menuToggle = document.querySelector('.menu-toggle');
    const navMain = document.querySelector('.nav-main');
    const navOverlay = document.querySelector('.nav-overlay');
    const body = document.body;

    // Toggle menú móvil
    if (menuToggle) {
        menuToggle.addEventListener('click', function() {
            navMain.classList.toggle('active');
            if (navOverlay) {
                navOverlay.classList.toggle('active');
            }
            body.style.overflow = navMain.classList.contains('active') ? 'hidden' : '';
            
            // Cambiar icono del menú
            const icon = this.querySelector('i') || this;
            if (navMain.classList.contains('active')) {
                icon.innerHTML = '✕';
            } else {
                icon.innerHTML = '☰';
            }
        });
    }

    // Cerrar menú al hacer click en overlay
    if (navOverlay) {
        navOverlay.addEventListener('click', function() {
            navMain.classList.remove('active');
            navOverlay.classList.remove('active');
            body.style.overflow = '';
            if (menuToggle) {
                const icon = menuToggle.querySelector('i') || menuToggle;
                icon.innerHTML = '☰';
            }
        });
    }

    // Cerrar menú móvil al hacer click en un enlace
    const navLinks = document.querySelectorAll('.nav-link');
    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            // Si es un dropdown, no cerrar el menú
            const parent = this.parentElement;
            if (parent.classList.contains('dropdown') && window.innerWidth <= 768) {
                e.preventDefault();
                parent.classList.toggle('active');
            } else if (window.innerWidth <= 768) {
                // Cerrar menú móvil
                navMain.classList.remove('active');
                if (navOverlay) {
                    navOverlay.classList.remove('active');
                }
                body.style.overflow = '';
                if (menuToggle) {
                    const icon = menuToggle.querySelector('i') || menuToggle;
                    icon.innerHTML = '☰';
                }
            }
        });
    });

    // ==========================================
    // HEADER SCROLL EFFECT
    // ==========================================
    const header = document.querySelector('.header');
    let lastScroll = 0;

    window.addEventListener('scroll', function() {
        const currentScroll = window.pageYOffset;

        // Agregar clase cuando se hace scroll
        if (currentScroll > 100) {
            header.classList.add('scrolled');
        } else {
            header.classList.remove('scrolled');
        }

        lastScroll = currentScroll;
    });

    // ==========================================
    // NAVEGACIÓN ACTIVA
    // ==========================================
    function setActiveNavLink() {
        const currentPage = window.location.pathname.split('/').pop() || 'index.html';
        
        navLinks.forEach(link => {
            const href = link.getAttribute('href');
            if (href === currentPage || 
                (currentPage === '' && href === 'index.html') ||
                (currentPage === 'index.html' && href === 'index.html')) {
                link.classList.add('active');
            } else {
                link.classList.remove('active');
            }
        });
    }

    setActiveNavLink();

    // ==========================================
    // SMOOTH SCROLL PARA ENLACES INTERNOS
    // ==========================================
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            
            if (target) {
                const headerOffset = 100;
                const elementPosition = target.getBoundingClientRect().top;
                const offsetPosition = elementPosition + window.pageYOffset - headerOffset;

                window.scrollTo({
                    top: offsetPosition,
                    behavior: 'smooth'
                });
            }
        });
    });

    // ==========================================
    // FORMULARIOS - VALIDACIÓN
    // ==========================================
    const forms = document.querySelectorAll('form');
    
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // Validación básica
            let isValid = true;
            const inputs = form.querySelectorAll('input[required], textarea[required], select[required]');
            
            inputs.forEach(input => {
                if (!input.value.trim()) {
                    isValid = false;
                    input.classList.add('error');
                    showError(input, 'Este campo es requerido');
                } else {
                    input.classList.remove('error');
                    removeError(input);
                }

                // Validar email
                if (input.type === 'email' && input.value) {
                    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
                    if (!emailRegex.test(input.value)) {
                        isValid = false;
                        input.classList.add('error');
                        showError(input, 'Email inválido');
                    }
                }

                // Validar teléfono
                if (input.type === 'tel' && input.value) {
                    const phoneRegex = /^[\d\s\-\+\(\)]+$/;
                    if (!phoneRegex.test(input.value)) {
                        isValid = false;
                        input.classList.add('error');
                        showError(input, 'Teléfono inválido');
                    }
                }
            });

            if (isValid) {
                // Aquí iría la lógica para enviar el formulario
                console.log('Formulario válido, listo para enviar');
                showSuccessMessage(form, '¡Formulario enviado exitosamente!');
                form.reset();
            }
        });

        // Remover error al escribir
        const inputs = form.querySelectorAll('input, textarea, select');
        inputs.forEach(input => {
            input.addEventListener('input', function() {
                this.classList.remove('error');
                removeError(this);
            });
        });
    });

    // Funciones auxiliares para mensajes de error
    function showError(input, message) {
        removeError(input);
        const error = document.createElement('div');
        error.className = 'error-message';
        error.textContent = message;
        error.style.color = 'var(--error-color)';
        error.style.fontSize = '0.875rem';
        error.style.marginTop = '0.25rem';
        input.parentNode.appendChild(error);
    }

    function removeError(input) {
        const error = input.parentNode.querySelector('.error-message');
        if (error) {
            error.remove();
        }
    }

    function showSuccessMessage(form, message) {
        const success = document.createElement('div');
        success.className = 'success-message';
        success.textContent = message;
        success.style.cssText = `
            background-color: var(--success-color);
            color: white;
            padding: 1rem;
            border-radius: 8px;
            margin-top: 1rem;
            text-align: center;
        `;
        form.appendChild(success);

        setTimeout(() => {
            success.remove();
        }, 5000);
    }

    // ==========================================
    // CONTADORES ANIMADOS
    // ==========================================
    function animateCounter(element, target, duration = 2000) {
        let start = 0;
        const increment = target / (duration / 16);
        
        const timer = setInterval(() => {
            start += increment;
            if (start >= target) {
                element.textContent = target;
                clearInterval(timer);
            } else {
                element.textContent = Math.floor(start);
            }
        }, 16);
    }

    // Activar contadores cuando sean visibles
    const counters = document.querySelectorAll('.counter');
    if (counters.length > 0) {
        const counterObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting && !entry.target.classList.contains('counted')) {
                    const target = parseInt(entry.target.getAttribute('data-target'));
                    animateCounter(entry.target, target);
                    entry.target.classList.add('counted');
                }
            });
        }, { threshold: 0.5 });

        counters.forEach(counter => counterObserver.observe(counter));
    }

    // ==========================================
    // ACORDEONES
    // ==========================================
    const accordionHeaders = document.querySelectorAll('.accordion-header');
    
    accordionHeaders.forEach(header => {
        header.addEventListener('click', function() {
            const accordion = this.parentElement;
            const content = accordion.querySelector('.accordion-content');
            const isActive = accordion.classList.contains('active');

            // Cerrar todos los acordeones
            document.querySelectorAll('.accordion').forEach(acc => {
                acc.classList.remove('active');
                const accContent = acc.querySelector('.accordion-content');
                if (accContent) {
                    accContent.style.maxHeight = null;
                }
            });

            // Abrir el acordeón clickeado si no estaba activo
            if (!isActive) {
                accordion.classList.add('active');
                content.style.maxHeight = content.scrollHeight + 'px';
            }
        });
    });

    // ==========================================
    // TABS
    // ==========================================
    const tabButtons = document.querySelectorAll('.tab-button');
    
    tabButtons.forEach(button => {
        button.addEventListener('click', function() {
            const tabGroup = this.closest('.tabs');
            const targetId = this.getAttribute('data-tab');
            
            // Remover clase active de todos los botones y contenidos
            tabGroup.querySelectorAll('.tab-button').forEach(btn => {
                btn.classList.remove('active');
            });
            tabGroup.querySelectorAll('.tab-content').forEach(content => {
                content.classList.remove('active');
            });

            // Activar el botón y contenido seleccionado
            this.classList.add('active');
            const targetContent = tabGroup.querySelector(`#${targetId}`);
            if (targetContent) {
                targetContent.classList.add('active');
            }
        });
    });

    // ==========================================
    // MODAL / LIGHTBOX
    // ==========================================
    const modalTriggers = document.querySelectorAll('[data-modal]');
    
    modalTriggers.forEach(trigger => {
        trigger.addEventListener('click', function(e) {
            e.preventDefault();
            const modalId = this.getAttribute('data-modal');
            const modal = document.getElementById(modalId);
            
            if (modal) {
                modal.classList.add('active');
                body.style.overflow = 'hidden';
            }
        });
    });

    // Cerrar modal
    const modalCloses = document.querySelectorAll('.modal-close, .modal-overlay');
    
    modalCloses.forEach(close => {
        close.addEventListener('click', function() {
            const modal = this.closest('.modal');
            if (modal) {
                modal.classList.remove('active');
                body.style.overflow = '';
            }
        });
    });

    // Cerrar modal con tecla ESC
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            const activeModal = document.querySelector('.modal.active');
            if (activeModal) {
                activeModal.classList.remove('active');
                body.style.overflow = '';
            }
        }
    });

    // ==========================================
    // TOOLTIP
    // ==========================================
    const tooltipTriggers = document.querySelectorAll('[data-tooltip]');
    
    tooltipTriggers.forEach(trigger => {
        trigger.addEventListener('mouseenter', function() {
            const text = this.getAttribute('data-tooltip');
            const tooltip = document.createElement('div');
            tooltip.className = 'tooltip';
            tooltip.textContent = text;
            tooltip.style.cssText = `
                position: absolute;
                background: var(--text-dark);
                color: white;
                padding: 0.5rem 1rem;
                border-radius: 4px;
                font-size: 0.875rem;
                white-space: nowrap;
                z-index: 1000;
                pointer-events: none;
            `;
            
            document.body.appendChild(tooltip);
            
            const rect = this.getBoundingClientRect();
            tooltip.style.top = (rect.top - tooltip.offsetHeight - 10) + 'px';
            tooltip.style.left = (rect.left + (rect.width / 2) - (tooltip.offsetWidth / 2)) + 'px';
            
            this.addEventListener('mouseleave', function() {
                tooltip.remove();
            }, { once: true });
        });
    });

    // ==========================================
    // LAZY LOADING PARA IMÁGENES
    // ==========================================
    if ('IntersectionObserver' in window) {
        const imageObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    img.src = img.dataset.src;
                    img.classList.add('loaded');
                    imageObserver.unobserve(img);
                }
            });
        });

        document.querySelectorAll('img[data-src]').forEach(img => {
            imageObserver.observe(img);
        });
    }

    // ==========================================
    // BOTÓN VOLVER ARRIBA
    // ==========================================
    const backToTop = document.querySelector('.back-to-top');
    
    if (backToTop) {
        window.addEventListener('scroll', function() {
            if (window.pageYOffset > 300) {
                backToTop.classList.add('visible');
            } else {
                backToTop.classList.remove('visible');
            }
        });

        backToTop.addEventListener('click', function(e) {
            e.preventDefault();
            window.scrollTo({
                top: 0,
                behavior: 'smooth'
            });
        });
    }

    console.log('CONCALAB-UASD: JavaScript cargado correctamente');
});

