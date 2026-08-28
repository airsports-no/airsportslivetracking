import React from 'react';
import { Link } from 'react-router-dom';
import { reverse } from '../../urls';
import routes from '../../routes.json';

const UpgradeSuccess = () => {
    return (
        <div className="container mx-auto p-4 max-w-4xl" data-theme="aviation">
            <div className="card bg-base-100 shadow-xl border border-success/20">
                <div className="card-body prose max-w-none">
                    <div className="flex flex-col items-center text-center mb-8">
                        <div className="w-20 h-20 bg-success/10 text-success rounded-full flex items-center justify-center mb-4">
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-12 h-12">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                            </svg>
                        </div>
                        <h1 className="text-4xl font-bold text-success m-0">Account Upgraded!</h1>
                        <p className="text-xl mt-2">You now have full Contest Organizer privileges.</p>
                    </div>

                    <p>
                        Welcome to the organizer community!
                    </p>

                    <h2 className="text-2xl font-semibold border-b pb-2">The Basic Workflow</h2>
                    
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 my-6 not-prose">
                        <div className="card bg-base-200">
                            <div className="card-body p-4">
                                <h3 className="font-bold text-lg">1. Create a Contest</h3>
                                <p className="text-sm">Set up your event container. Control visibility, dates, and sharing.</p>
                            </div>
                        </div>
                        <div className="card bg-base-200">
                            <div className="card-body p-4">
                                <h3 className="font-bold text-lg">2. Design Routes</h3>
                                <p className="text-sm">Use the Route Editor to create waypoints and competition tasks.</p>
                            </div>
                        </div>
                        <div className="card bg-base-200">
                            <div className="card-body p-4">
                                <h3 className="font-bold text-lg">3. Add Participants</h3>
                                <p className="text-sm">Manage teams and assign them to tasks for live tracking.</p>
                            </div>
                        </div>
                    </div>

                    <h2 className="text-2xl font-semibold border-b pb-2">Key Features</h2>
                    
                    <h3 className="font-bold text-lg mt-4">Route Editor</h3>
                    <p>
                        The Route Editor is your primary tool for task creation. You can draw routes, define gate types, 
                        and set up scoring parameters. <strong>We encourage you to play with the editor</strong> to get a 
                        feel for its capabilities.
                    </p>

                    <h3 className="font-bold text-lg mt-4">Custom Maps</h3>
                    <p>
                        You can upload your own background maps in <code>mbtiles</code> format. This allows you to use 
                        specific aeronautical charts or local imagery for your flight orders.
                    </p>

                    <h3 className="font-bold text-lg mt-4">Self-Registration & Scheduling</h3>
                    <p>
                        For informal events or practice, you can enable self-management. This allows pilots to sign 
                        up and schedule their own flights, automatically receiving their flight orders by email.
                    </p>

                    <div className="alert alert-info shadow-sm not-prose mt-8">
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" className="stroke-current shrink-0 w-6 h-6"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                        <div>
                            <h3 className="font-bold">Getting Started Tip</h3>
                            <p className="text-sm">Create a "Test Competition" and a few routes. It's the best way to learn how the live tracking and scoring system works before your first real event!</p>
                        </div>
                    </div>

                    <div className="divider my-8">Quick Links</div>

                    <div className="flex flex-wrap gap-4 justify-center not-prose">
                        <a href="/?tab=editorContests" className="btn btn-primary">
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5 mr-2">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                            </svg>
                            My Contests
                        </a>
                        <Link to={`/${routes.ROUTE_EDITOR_LIST}`} className="btn btn-secondary">
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5 mr-2">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M9 6.75V15m6-10.5v.75m.001 3v.75m0 3v.75m0 3V18m-6-11.25h.008v.008h-.008V6.75zm.001 3h.008v.008h-.008V9.75zm.001 3h.008v.008h-.008v-.008zm3-6h.008v.008h-.008V6.75zm.001 3h.008v.008h-.008V9.75zm.001 3h.008v.008h-.008v-.008zM6 6.75h.007v.008H6V6.75zm.001 3h.007v.008H6.001V9.75zm.001 3h.007v.008H6.002v-.008zm3 6h.007v.008h-.007v-.008zm3 0h.007v.008h-.007v-.008zm3 0h.007v.008h-.007v-.008z" />
                            </svg>
                            Route Editor
                        </Link>
                        <a href={reverse('useruploadedmap_list')} className="btn btn-accent text-accent-content">
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5 mr-2">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M9 6.75V15m6-10.5v.75m.001 3v.75m0 3v.75m0 3V18m-6-11.25h.008v.008h-.008V6.75zm.001 3h.008v.008h-.008V9.75zm.001 3h.008v.008h-.008v-.008zm3-6h.008v.008h-.008V6.75zm.001 3h.008v.008h-.008V9.75zm.001 3h.008v.008h-.008v-.008zM6 6.75h.007v.008H6V6.75zm.001 3h.007v.008H6.001V9.75zm.001 3h.007v.008H6.002v-.008zm3 6h.007v.008h-.007v-.008zm3 0h.007v.008h-.007v-.008zm3 0h.007v.008h-.007v-.008z" />
                            </svg>
                            My Maps
                        </a>
                    </div>
                    <p className="text-center mt-6 text-gray-500 italic">You find all these links under the management tab in the navigation bar.</p>
                </div>
            </div>
        </div>
    );
};

export default UpgradeSuccess;