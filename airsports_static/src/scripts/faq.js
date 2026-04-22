// Accordion logic for FAQ
export function initFaq() {
    const buttons = document.querySelectorAll('.faq-button');
    
    buttons.forEach(button => {
        button.addEventListener('click', () => {
            const container = button.parentElement;
            const content = button.nextElementSibling;
            const svg = button.querySelector('svg');
            const isHidden = content.classList.contains('hidden');
            
            // Close all others
            document.querySelectorAll('.faq-content').forEach(c => {
                if (c !== content) {
                    c.classList.add('hidden');
                    const otherSvg = c.parentElement.querySelector('svg');
                    if (otherSvg) otherSvg.classList.remove('rotate-180');
                    c.parentElement.classList.remove('border-blue-200', 'shadow-blue-100');
                }
            });
            
            if (isHidden) {
                content.classList.remove('hidden');
                svg.classList.add('rotate-180');
                container.classList.add('border-blue-200', 'shadow-blue-100');
            } else {
                content.classList.add('hidden');
                svg.classList.remove('rotate-180');
                container.classList.remove('border-blue-200', 'shadow-blue-100');
            }
        });
    });

    // Handle anchor links
    if (window.location.hash) {
        const id = window.location.hash.substring(1);
        const el = document.getElementById(id);
        if (el) {
            const btn = el.querySelector('button');
            if (btn) btn.click();
            setTimeout(() => el.scrollIntoView({ behavior: 'smooth' }), 100);
        }
    }
}
