import React, { useState } from 'react';
import { NavigationTask } from '../types';
import { sendContestAnnouncement } from '../api';

interface Props {
    contestId: number;
    tasks: NavigationTask[];
}

const MAX_LENGTH = 500;

/**
 * Lets the organizers send a message to the pilots of the contest, or of one task: a push notification to their phones
 * and a notice in the Air Sports app for the next 24 hours.
 */
const AnnouncementPanel: React.FC<Props> = ({ contestId, tasks }) => {
    const [message, setMessage] = useState('');
    const [taskId, setTaskId] = useState<string>('');
    const [sending, setSending] = useState(false);
    const [result, setResult] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    const send = async () => {
        if (!window.confirm('Send this message to the pilots now? It cannot be recalled.')) return;
        setSending(true);
        setError(null);
        setResult(null);
        try {
            const sent = await sendContestAnnouncement(contestId, message.trim(), taskId === '' ? null : Number(taskId));
            setResult(`Sent. ${sent.people_reached} ${sent.people_reached === 1 ? 'person' : 'people'} reached by push notification; everybody concerned sees it in the app for 24 hours.`);
            setMessage('');
        } catch (err) {
            setError((err as Error).message);
        } finally {
            setSending(false);
        }
    };

    return (
        <div className="card bg-base-100 shadow-md border border-base-300">
            <div className="card-body p-4 gap-3">
                <h3 className="card-title text-lg">Message the pilots</h3>
                <div className="text-sm opacity-75">
                    Sent as a push notification to the Air Sports app and shown there for 24 hours. For example a changed briefing time.
                </div>
                <textarea
                    className="textarea textarea-bordered w-full"
                    rows={3}
                    maxLength={MAX_LENGTH}
                    placeholder="Briefing moved to 08:30 in the club house"
                    value={message}
                    onChange={e => setMessage(e.target.value)}
                    aria-label="Message to the pilots"
                />
                <div className="flex flex-wrap items-center gap-3 justify-between">
                    <select
                        className="select select-bordered select-sm"
                        value={taskId}
                        onChange={e => setTaskId(e.target.value)}
                        aria-label="Who gets the message"
                    >
                        <option value="">Everybody registered in the contest</option>
                        {tasks.map(task => (
                            <option key={task.pk} value={task.pk}>
                                Crews flying {task.name}
                            </option>
                        ))}
                    </select>
                    <div className="flex items-center gap-3">
                        <span className="text-xs opacity-60">{message.length}/{MAX_LENGTH}</span>
                        <button className="btn btn-primary btn-sm" disabled={sending || message.trim() === ''} onClick={send}>
                            {sending ? 'Sending…' : 'Send'}
                        </button>
                    </div>
                </div>
                {result && <div className="alert alert-success text-sm">{result}</div>}
                {error && <div className="alert alert-error text-sm">{error}</div>}
            </div>
        </div>
    );
};

export default AnnouncementPanel;
