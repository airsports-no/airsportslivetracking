import React, { useEffect, useState } from 'react';
import ContestPermissionsPanel from '../contest-management/components/ContestPermissionsPanel';
import { SeriesPermissionGrant, addSeriesPermission, changeSeriesPermission, fetchSeriesPermissions, removeSeriesPermission } from './api';

/** Who may see, run and delete a series: the same levels and rules as for a contest. */
const SeriesPermissions: React.FC<{ seriesId: number }> = ({ seriesId }) => {
    const [grants, setGrants] = useState<SeriesPermissionGrant[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [reloads, setReloads] = useState(0);
    const reload = () => setReloads(count => count + 1);

    useEffect(() => {
        let cancelled = false;
        fetchSeriesPermissions(seriesId)
            .then(list => {
                if (cancelled) return;
                setGrants(list);
                setError(null);
                setLoading(false);
            })
            .catch(e => {
                if (cancelled) return;
                setError((e as Error).message);
                setLoading(false);
            });
        return () => {
            cancelled = true;
        };
    }, [seriesId, reloads]);

    return (
        <>
            {error && <div role="alert" className="alert alert-error">{error}</div>}
            <ContestPermissionsPanel
                grants={grants}
                currentUserId={document.configuration.userId ?? -1}
                loading={loading}
                description={
                    <>
                        Give others access to this series. <strong>View</strong> lets somebody see a private series and its standings.{' '}
                        <strong>Manage</strong> also lets them change the settings, add and remove contests, answer requests and give
                        others access at any level. <strong>Manage &amp; delete</strong> may also delete the series. A public series
                        can be seen by everybody.
                    </>
                }
                levelLabels={{ view: 'view', change: 'manage', delete: 'manage & delete' }}
                onAdd={async (identifier, level) => {
                    await addSeriesPermission(seriesId, identifier, level);
                    reload();
                }}
                onChange={async (userId, level) => {
                    await changeSeriesPermission(seriesId, userId, level);
                    reload();
                }}
                onRemove={async userId => {
                    await removeSeriesPermission(seriesId, userId);
                    reload();
                }}
            />
        </>
    );
};

export default SeriesPermissions;
