const isPresent = value => value !== null && value !== undefined && value !== '' && value !== false;

/**
 * Accessible fact grid replacing the six duplicated
 * `donor-*-facts` / `recipient-*-facts` / `org-facts` / `pickup-*` markup
 * blocks. Blank values are dropped so "Not provided" states stay explicit
 * where callers supply them.
 */
const FactList = ({ items, className = '' }) => {
  const facts = (items || []).filter(([, value]) => isPresent(value));
  if (!facts.length) return null;
  return (
    <dl className={`fact-list ${className}`.trim()}>
      {facts.map(([label, value]) => (
        <div className="fact-item" key={label}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
};

export default FactList;
