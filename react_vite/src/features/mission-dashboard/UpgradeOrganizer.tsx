import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getCookie } from '../../utils/csrf';
import routes from '../../routes.json';

const UpgradeOrganizer = () => {
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleUpgrade = async () => {
        setLoading(true);
        setError(null);
        try {
            const response = await fetch('/display/users/upgrade/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken') || '',
                },
            });
            if (response.ok) {
                // Success - redirect to Upgrade Success page
                // We use navigate if we don't want a full reload, 
                // but window.location.href ensures document.configuration.isOrganizer is refreshed from the server
                window.location.href = `/${routes.UPGRADE_SUCCESS}`;
            } else {
                const data = await response.json();
                setError(data.message || 'Upgrade failed');
            }
        } catch (err) {
            setError('An error occurred during upgrade');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="container mx-auto p-4 max-w-4xl" data-theme="aviation">
            <div className="card bg-base-100 shadow-xl border border-primary/20">
                <div className="card-body prose max-w-none">
                    <h1 className="text-4xl font-bold text-primary mb-6">Upgrade to Contest Organizer</h1>
                    
                    <p className="text-xl">
                        You are about to upgrade your account to include contest creation privileges. 
                        <strong> This upgrade is completely free of charge.</strong>
                    </p>

                    <div className="divider">What's New?</div>

                    <h2 className="text-2xl font-semibold">Route Editor</h2>
                    <p>
                        The Route Editor is a powerful tool that allows you to design flying routes with ease. 
                        You can create waypoints, define turn points, and set up various gate types. 
                        It supports importing routes from common formats like GPX, KML, and CSV.
                    </p>

                    <h2 className="text-2xl font-semibold">Creating Contests</h2>
                    <p>
                        As an organizer, you can create and manage your own contests. 
                        A contest serves as a container for multiple navigation tasks and participants. 
                        You can set contest dates, location, and control who can see or participate in your events.
                    </p>

                    <h2 className="text-2xl font-semibold">Navigation Tasks</h2>
                    <p>
                        Once you have created a route in the Route Editor, you can easily turn it into a Navigation Task 
                        within a contest. The task inherits all properties from the route and allows you to set specific 
                        wind conditions, planning times, and scoring rules.
                    </p>

                    <h2 className="text-2xl font-semibold">Teams and Contestants</h2>
                    <p>
                        You can add teams to your contest, providing details about pilots, co-pilots, and aircraft. 
                        These teams can then be assigned as contestants to your navigation tasks. 
                        The system will then generate personalized flight orders and track their progress in real-time.
                    </p>

                    <h2 className="text-2xl font-semibold">Custom Background Maps</h2>
                    <p>
                        Enhance your flight orders by uploading your own background maps in <strong>mbtiles</strong> format. 
                        This feature allows you to use highly detailed or specialized aeronautical charts that are 
                        perfectly tailored for your specific navigation tasks, ensuring participants have the best 
                        possible visual aids.
                    </p>

                    <h2 className="text-2xl font-semibold">Self-Management</h2>
                    <p>
                        If you enable "Self-Management" for a navigation task, other users can sign up for the task 
                        on their own. They can register their team, aircraft, and schedule their own takeoff time 
                        directly through the Mission Dashboard. This is perfect for practice sessions or distributed 
                        competitions where participants fly at different times.
                    </p>

                    <div className="card-actions justify-center mt-8">
                        <button 
                            className={`btn btn-primary btn-lg ${loading ? 'loading' : ''}`}
                            onClick={handleUpgrade}
                            disabled={loading}
                        >
                            {loading && <span className="loading loading-spinner"></span>}
                            {loading ? 'Upgrading...' : 'Upgrade My Account Now'}
                        </button>
                    </div>
                    {error && (
                        <div className="alert alert-error mt-4 shadow-lg">
                            <svg xmlns="http://www.w3.org/2000/svg" className="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                            <span>{error}</span>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default UpgradeOrganizer;
