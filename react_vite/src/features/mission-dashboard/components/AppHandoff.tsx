import React from 'react';
import { Smartphone } from 'lucide-react';
import { isEmbeddedInApp } from '../../../utils/appBridge';

const PLAY_STORE_URL = 'https://play.google.com/store/apps/details?id=no.airsports.android.livetracking';
const APP_STORE_URL = 'https://apps.apple.com/us/app/air-sports-live-tracking/id1559193686';

/** Tells a pilot with a booked flight what to do on the day: use the phone app with the same email. */
const AppHandoff: React.FC = () => {
    // Already in the app: nothing to install.
    if (isEmbeddedInApp()) return null;
    const email = document.configuration.userEmail;
    return (
        <div className="alert alert-info alert-soft items-start mb-4">
            <Smartphone size={20} className="shrink-0 mt-0.5" />
            <div className="text-sm">
                <div className="font-bold">On the day: start tracking in the app</div>
                <ol className="list-decimal list-inside mt-1 space-y-0.5">
                    <li>
                        Install the ASLT app (<a className="link" href={PLAY_STORE_URL} target="_blank" rel="noreferrer">Android</a>
                        {' / '}
                        <a className="link" href={APP_STORE_URL} target="_blank" rel="noreferrer">iOS</a>).
                    </li>
                    <li>Log in with {email ? <strong>{email}</strong> : 'the same email you use here'}. Your flight appears automatically.</li>
                    <li>Press <em>Start tracking</em> before you take off.</li>
                </ol>
                <p className="mt-2 opacity-80">
                    Don&apos;t see a flight you expected? The organizer may have registered you with a different email address.
                </p>
            </div>
        </div>
    );
};

export default AppHandoff;
