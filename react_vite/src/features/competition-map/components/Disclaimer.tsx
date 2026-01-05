import React, { useState, useEffect } from 'react';

const Disclaimer = () => {
    const [isOpen, setIsOpen] = useState(false);
    const [disclaimer, setDisclaimer] = useState('');

    useEffect(() => {
        if (document.configuration && document.configuration.TERMS_AND_CONDITIONS_URL) {
            fetch(document.configuration.TERMS_AND_CONDITIONS_URL)
                .then(res => {
                    if (res.ok) {
                        return res.text();
                    }
                    throw new Error('Network response was not ok.');
                })
                .then(html => {
                    const parser = new DOMParser();
                    const doc = parser.parseFromString(html, 'text/html');
                    
                    // Extract styles and links from the head
                    const styleTags = Array.from(doc.head.querySelectorAll('style'));
                    const linkTags = Array.from(doc.head.querySelectorAll('link[rel="stylesheet"]'));
                    const stylesHtml = styleTags.map(tag => tag.outerHTML).join('');
                    const linksHtml = linkTags.map(tag => tag.outerHTML).join('');

                    // Extract body content
                    const bodyContent = doc.body.innerHTML;

                    setDisclaimer(stylesHtml + linksHtml + bodyContent);
                })
                .catch(error => {
                    console.error("Failed to fetch disclaimer:", error);
                    setDisclaimer("<p>Failed to load terms and conditions. Please try again later.</p>");
                });
        } else {
            console.error("Disclaimer URL not found in configuration.");
            setDisclaimer("<p>Configuration error: Disclaimer URL is missing.</p>");
        }
    }, []);

    const openModal = (e: React.MouseEvent) => {
        e.preventDefault();
        setIsOpen(true);
    };
    const closeModal = () => setIsOpen(false);

    return (
        <>
            <a href="#" className="absolute bottom-4 left-4 z-[1000] text-xs link link-hover" onClick={openModal}>
                Terms and Conditions
            </a>

            {isOpen && (
                <dialog id="disclaimer_modal" className="modal modal-open z-[2000]" onClick={closeModal}>
                    <div className="modal-box w-11/12 max-w-5xl relative my-8" onClick={e => e.stopPropagation()}>
                        {/* Top close button */}
                        <form method="dialog">
                            <button className="btn btn-sm btn-circle btn-ghost absolute right-2 top-2" onClick={closeModal}>✕</button>
                        </form>
                        
                        <h3 className="font-bold text-lg mt-4">Terms and Conditions</h3>
                        <div className="py-4 prose max-w-none" dangerouslySetInnerHTML={{ __html: disclaimer }} />
                        <div className="modal-action">
                            <button className="btn" onClick={closeModal}>Close</button>
                        </div>
                    </div>
                </dialog>
            )}
        </>
    );
};

export default React.memo(Disclaimer);
