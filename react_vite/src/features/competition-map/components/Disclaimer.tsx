import React, { useState, useEffect } from 'react';
import { fetchDisclaimerHtml } from '../api'; // Import new API function

const Disclaimer = () => {
    const [isOpen, setIsOpen] = useState(false);
    const [disclaimer, setDisclaimer] = useState('');

    useEffect(() => {
        fetchDisclaimerHtml()
            .then(setDisclaimer)
            .catch(error => {
                console.error("Failed to fetch disclaimer:", error);
                setDisclaimer("<p>Failed to load terms and conditions. Please try again later.</p>");
            });
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
