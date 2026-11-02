const STATUS_LABELS = {
  draft: 'Draft',
  published: 'Available',
  expired: 'Expired',
  reserved: 'Reserved',
  pending: 'Pending',
  submitted: 'Submitted for review',
  partially_approved: 'Partially approved',
  approved: 'Approved',
  rejected: 'Rejected',
  cancelled: 'Cancelled',
  fulfilled: 'Fulfilled',
  scheduled: 'Scheduled',
  in_progress: 'In progress',
  completed: 'Completed',
  failed: 'Failed',
  no_show: 'No-show',
  verified: 'Verified',
  unknown: 'Unknown',
};

const readable = value => STATUS_LABELS[value] || String(value || 'Unknown').replaceAll('_', ' ');

/**
 * One status badge for every domain status value (donations, requests,
 * pickups, organizations). Replaces the per-page `donor-status-*` and
 * `pickup-status-*` fragments.
 */
const StatusBadge = ({ status, className = '' }) => (
  <span className={`status-badge status-${status || 'unknown'} ${className}`.trim()}>
    {readable(status)}
  </span>
);

export default StatusBadge;
