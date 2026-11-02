import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Loading from '../../components/Loading';
import PageIntro from '../../components/PageIntro';
import StatusBadge from '../../components/StatusBadge';
import { getApiErrorMessage } from '../../services/donorApi';
import { getAdminDashboardData } from '../../services/adminApi';

function MetricCard({ label, value, hint, to }) {
  const content = <>
    <span className="donor-metric-label">{label}</span>
    <strong>{value}</strong>
    <span className="donor-metric-hint">{hint}</span>
  </>;

  return <Link className="donor-metric-card" to={to}>{content}</Link>;
}

export default function AdminDashboardPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      setData(await getAdminDashboardData());
    } catch (loadError) {
      setData(null);
      setError(getApiErrorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) {
    return <div className="donor-dashboard-loading" role="status"><Loading message="Loading admin dashboard…" /></div>;
  }

  if (error) {
    return (
      <section className="donor-state-panel" role="alert">
        <h2>We couldn’t load the admin dashboard</h2>
        <p>{error}</p>
        <button type="button" className="donor-button donor-button-secondary" onClick={load}>Try again</button>
      </section>
    );
  }

  const pendingCompliance = data.complianceRecords.filter(record => record.compliance_status === 'submitted');
  const pendingAllergens = data.allergenDeclarations.filter(declaration => declaration.declaration_status === 'pending');

  return (
    <div className="donor-overview-page admin-dashboard">
      <PageIntro
        eyebrow="PLATFORM ADMINISTRATION"
        title="Admin Dashboard"
        description="Monitor ShareHarvest organizations, donations, requests, and food-safety reviews."
        action={<Link className="donor-text-link" to="/admin/organizations">Manage organizations <span aria-hidden="true">→</span></Link>}
      />

      <section className="donor-metrics-grid" aria-label="Platform overview">
        <MetricCard label="Registered organizations" value={data.organizations.length} hint="Across the platform" to="/admin/organizations" />
        <MetricCard label="Donations" value={data.donations.length} hint="Across all statuses" to="/admin/dashboard#donation-monitor" />
        <MetricCard label="Pending requests" value={data.pendingRequests.length} hint="Awaiting organization review" to="/admin/dashboard#request-monitor" />
        <MetricCard label="Pending compliance reviews" value={pendingCompliance.length} hint="FSSAI submissions to review" to="/compliance" />
      </section>

      <section className="donor-overview-lower">
        <div className="donor-panel" id="request-monitor">
          <div className="donor-panel-heading">
            <div><p className="donor-eyebrow">REQUEST MONITOR</p><h2>Pending donation requests</h2></div>
          </div>
          {data.pendingRequests.length === 0 ? (
            <p className="donor-empty-copy">There are no pending requests.</p>
          ) : (
            <div className="donor-recent-list">
              {data.pendingRequests.slice(0, 5).map(request => (
                <div className="donor-recent-row" key={request.id}>
                  <span className="donor-recent-copy">
                    <strong>{request.donation_title || `Donation #${request.donation}`}</strong>
                    <small>{request.organization_name} · {request.requested_quantity} {request.requested_unit}</small>
                  </span>
                  <StatusBadge status={request.status} />
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="donor-panel" id="donation-monitor">
          <div className="donor-panel-heading">
            <div><p className="donor-eyebrow">DONATION MONITOR</p><h2>Recent donations</h2></div>
          </div>
          {data.donations.length === 0 ? (
            <p className="donor-empty-copy">There are no donations to show.</p>
          ) : (
            <div className="donor-recent-list">
              {data.donations.slice(0, 5).map(donation => (
                <div className="donor-recent-row" key={donation.id}>
                  <span className="donor-recent-copy">
                    <strong>{donation.title}</strong>
                    <small>{donation.organization_name || `Organization #${donation.organization}`} · {donation.quantity} {donation.unit}</small>
                  </span>
                  <StatusBadge status={donation.status} />
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      <section className="donor-panel admin-review-panel">
        <div className="donor-panel-heading">
          <div><p className="donor-eyebrow">FOOD SAFETY</p><h2>Compliance and allergen reviews</h2></div>
          <Link to="/compliance">Open review queue</Link>
        </div>
        <p className="donor-empty-copy">
          {pendingCompliance.length} FSSAI submissions and {pendingAllergens.length} allergen declarations are awaiting review.
        </p>
        <p className="donor-empty-copy">Allergen declarations include declared ingredients and cross-contamination details.</p>
      </section>
    </div>
  );
}
