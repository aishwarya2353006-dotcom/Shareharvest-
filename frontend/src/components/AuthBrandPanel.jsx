import { Link } from 'react-router-dom';

const AuthBrandPanel = () => (
  <aside className="auth-story" aria-label="ShareHarvest">
    <Link className="auth-story-brand" to="/" aria-label="ShareHarvest home">
      <span className="auth-story-mark" aria-hidden="true">
        <svg viewBox="0 0 32 32" fill="none">
          <path d="M26.5 5.5C15.2 5.8 7.1 9.4 7.1 18.2c0 4.3 3.1 7.2 7.1 7.2 8.9 0 12.5-8.2 12.3-19.9Z" fill="currentColor" />
          <path d="M5.5 27c4.3-6.8 8.8-10.5 15.2-14.3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
      </span>
      <span>share<span className="auth-story-brand-accent">harvest</span></span>
    </Link>
    <div className="auth-story-copy">
      <p className="auth-story-eyebrow">GOOD FOOD. SHARED WITH PURPOSE.</p>
      <h1>Good food deserves a second chance.</h1>
      <p>Share surplus food with local organizations and help more of it reach the people who need it.</p>
    </div>
    <div className="auth-story-art" aria-hidden="true">
      <span className="auth-story-orbit auth-story-orbit-one" />
      <span className="auth-story-orbit auth-story-orbit-two" />
      <span className="auth-story-sun" />
      <span className="auth-story-leaf">
        <svg viewBox="0 0 80 80" fill="none">
          <path d="M67 12C38 13 17 22 17 44c0 11 8 19 18 19 22 0 33-21 32-51Z" fill="currentColor" />
          <path d="M13 68c11-18 23-28 41-38" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
        </svg>
      </span>
      <div className="auth-story-note">
        <span className="auth-story-note-mark">✳</span>
        <span><strong>Local food.</strong><br />Local impact.</span>
      </div>
    </div>
    <p className="auth-story-caption">Connecting food donors with verified recipient organizations.</p>
  </aside>
);

export default AuthBrandPanel;
