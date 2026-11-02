import { useCallback, useEffect, useState } from 'react';
import AnimatedMetric from '../../components/AnimatedMetric';
import Loading from '../../components/Loading';
import PageIntro from '../../components/PageIntro';
import { getApiErrorMessage } from '../../services/donorApi';
import { getImpactSummary } from '../../services/impactApi';

export default function ImpactDashboardPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      setData(await getImpactSummary());
    } catch (loadError) {
      setData(null);
      setError(getApiErrorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) {
    return <div className="donor-dashboard-loading" role="status"><Loading message="Loading impact dashboard…" /></div>;
  }

  if (error) {
    return (
      <main className="access-denied" role="alert">
        <h1>Impact data unavailable</h1>
        <p>{error}</p>
        <button className="access-retry" type="button" onClick={load}>Try again</button>
      </main>
    );
  }

  const summary = data || {};
  const hasData = summary.organizations > 0 || summary.completed_pickups > 0
    || summary.donations_published > 0 || summary.total_allocated_kg > 0;

  return (
    <section className="donor-dashboard">
      <PageIntro eyebrow="Impact" title="Impact reporting" description="Aggregated outcomes from completed pickups and published donations." />
      {!hasData ? (
        <p className="donor-empty-state">No impact data is available yet.</p>
      ) : (
        <div className="donor-metric-grid">
          <div className="donor-metric-card">
            <span className="donor-metric-label">Completed pickups</span>
            <strong><AnimatedMetric value={summary.completed_pickups ?? 0} /></strong>
            <span className="donor-metric-hint">Successful pickups recorded</span>
          </div>
          <div className="donor-metric-card">
            <span className="donor-metric-label">Allocated quantity (kg)</span>
            <strong><AnimatedMetric value={summary.total_allocated_kg ?? 0} decimals={2} /></strong>
            <span className="donor-metric-hint">Mass allocations converted to kg</span>
          </div>
          <div className="donor-metric-card">
            <span className="donor-metric-label">Published donations</span>
            <strong><AnimatedMetric value={summary.donations_published ?? 0} /></strong>
            <span className="donor-metric-hint">Currently published donations</span>
          </div>
          <div className="donor-metric-card">
            <span className="donor-metric-label">Organizations</span>
            <strong><AnimatedMetric value={summary.organizations ?? 0} /></strong>
            <span className="donor-metric-hint">Organizations in scope</span>
          </div>
        </div>
      )}
    </section>
  );
}
