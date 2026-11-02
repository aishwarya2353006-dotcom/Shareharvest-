/**
 * Shared page-intro block replacing the duplicated
 * `donor-page-intro` markup on six pages. Renders an h2 (the MainLayout
 * renders the page's h1), an optional action, and an optional note.
 */
const PageIntro = ({ eyebrow, title, description, action, note }) => (
  <div className="page-intro">
    <div>
      {eyebrow && <p className="page-eyebrow">{eyebrow}</p>}
      <h2>{title}</h2>
      {description && <p className="page-intro-description">{description}</p>}
      {note && <p className="page-intro-note">{note}</p>}
    </div>
    {action}
  </div>
);

export default PageIntro;
