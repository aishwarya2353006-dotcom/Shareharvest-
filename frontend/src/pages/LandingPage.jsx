import { useState } from 'react';
import { Link } from 'react-router-dom';
import Button from '../components/Button';
import api from '../services/api';

const LeafMark = ({ className = '' }) => (
  <svg className={className} viewBox="0 0 32 32" fill="none" aria-hidden="true">
    <path d="M26.5 5.5C15.2 5.8 7.1 9.4 7.1 18.2c0 4.3 3.1 7.2 7.1 7.2 8.9 0 12.5-8.2 12.3-19.9Z" fill="currentColor" />
    <path d="M5.5 27c4.3-6.8 8.8-10.5 15.2-14.3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
  </svg>
);

const ArrowIcon = () => (
  <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
    <path d="M4 10h11m-4.5-4.5L15 10l-4.5 4.5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

function LandingPage() {
  const [apiStatus, setApiStatus] = useState(null);
  const [checkingApi, setCheckingApi] = useState(false);

  const checkApiHealth = async () => {
    setCheckingApi(true);
    try {
      const response = await api.get('/health/');
      setApiStatus(response.data);
    } catch (error) {
      setApiStatus({ status: 'error', message: error.message });
    } finally {
      setCheckingApi(false);
    }
  };

  return (
    <div className="site-shell">
      <header className="site-header">
        <div className="site-header-inner">
          <Link className="brand" to="/" aria-label="ShareHarvest home">
            <span className="brand-mark"><LeafMark /></span>
            <span>share<span className="brand-name-accent">harvest</span></span>
          </Link>

          <nav className="desktop-nav" aria-label="Main navigation">
            <a href="#how-it-works">How it works</a>
            <a href="#for-donors">For donors</a>
            <a href="#for-recipients">For recipients</a>
            <a href="#our-impact">Our impact</a>
          </nav>

          <div className="header-actions">
            <Link className="header-login" to="/login">Log in</Link>
            <Button asLink to="/register" className="header-cta" size="small">
              Get started <ArrowIcon />
            </Button>
          </div>

          <details className="mobile-menu">
            <summary aria-label="Open navigation menu"><span /><span /><span /></summary>
            <nav aria-label="Mobile navigation">
              <a href="#how-it-works">How it works</a>
              <a href="#for-donors">For donors</a>
              <a href="#for-recipients">For recipients</a>
              <a href="#our-impact">Our impact</a>
              <Link to="/login">Log in</Link>
              <Link to="/register">Get started <ArrowIcon /></Link>
            </nav>
          </details>
        </div>
      </header>

      <main>
        <section className="hero-section">
          <div className="hero-inner page-width">
            <div className="hero-copy">
              <div className="eyebrow"><span className="eyebrow-dot" /> FOOD, SHARED WITH PURPOSE</div>
              <h1>Good food deserves <span>a second chance.</span></h1>
              <p className="hero-description">
                Help surplus food reach the communities that need it. ShareHarvest connects food donors with verified recipient organizations.
              </p>
              <div className="hero-actions">
                <Button asLink to="/register" size="large">Get started <ArrowIcon /></Button>
                <a className="text-action" href="#how-it-works">Explore how it works <span aria-hidden="true">↓</span></a>
              </div>
              <div className="hero-proof">
                <span className="proof-mark"><LeafMark /></span>
                <p><strong>Local food. Local impact.</strong><br />A simpler way to share what’s good.</p>
              </div>
            </div>

            <div className="hero-visual" aria-hidden="true">
              <div className="visual-sun" />
              <div className="visual-orbit orbit-one" />
              <div className="visual-orbit orbit-two" />
              <div className="visual-leaf leaf-one">✦</div>
              <div className="visual-leaf leaf-two">✳</div>
              <div className="produce-card">
                <div className="produce-label"><span className="produce-status" /> READY TO SHARE</div>
                <div className="produce-basket">
                  <span className="produce-item produce-orange">●</span>
                  <span className="produce-item produce-red">●</span>
                  <span className="produce-item produce-green">●</span>
                  <span className="produce-item produce-yellow">●</span>
                  <span className="produce-item produce-tomato">●</span>
                  <span className="produce-leaf leaf-a">✦</span>
                  <span className="produce-leaf leaf-b">✦</span>
                  <span className="produce-leaf leaf-c">✦</span>
                  <div className="basket-body"><span>FRESH &amp; LOCAL</span></div>
                </div>
                <div className="produce-caption"><span>Today’s harvest</span><span className="caption-check">✓</span></div>
              </div>
              <div className="floating-note note-top"><span className="note-icon note-icon-green">↗</span><span><strong>Good food,</strong><br />right on time</span></div>
              <div className="floating-note note-bottom"><span className="note-icon note-icon-peach"><LeafMark /></span><span><strong>Shared locally</strong><br />with purpose</span></div>
              <div className="visual-caption">A little less waste. A lot more good.</div>
            </div>
          </div>
          <div className="hero-bottom-rule" />
        </section>

        <section className="trust-strip" aria-label="How ShareHarvest builds trust">
          <div className="trust-inner page-width">
            <p className="trust-heading">A better way to<br />move good food.</p>
            <div className="trust-item"><span className="trust-icon trust-icon-leaf"><LeafMark /></span><span><strong>Verified organizations</strong><small>Community partners you can trust</small></span></div>
            <div className="trust-item"><span className="trust-icon trust-icon-chart">↗</span><span><strong>Transparent tracking</strong><small>Follow each donation’s journey</small></span></div>
            <div className="trust-item"><span className="trust-icon trust-icon-heart">♡</span><span><strong>Community first</strong><small>Food finds the people who need it</small></span></div>
          </div>
        </section>

        <section className="how-section section-pad" id="how-it-works">
          <div className="page-width">
            <div className="section-heading centered-heading">
              <span className="section-kicker">A SIMPLE WAY TO SHARE</span>
              <h2>Good things happen<br className="desktop-break" /> when we work together.</h2>
              <p>From extra food to a shared meal, every step brings our communities closer.</p>
            </div>
            <div className="steps-grid">
              <article className="step-card">
                <div className="step-number">01 <span>—</span></div>
                <div className="step-art step-art-list"><div className="mini-sheet"><span /><span /><span /></div><span className="mini-plus">+</span></div>
                <h3>List surplus food</h3>
                <p>Share what’s available, how much you have, and when it can be picked up.</p>
              </article>
              <article className="step-card">
                <div className="step-number">02 <span>—</span></div>
                <div className="step-art step-art-connect"><span className="connect-dot dot-a">N</span><span className="connect-dot dot-b">♡</span><span className="connect-line" /></div>
                <h3>Connect with recipients</h3>
                <p>Eligible community organizations find donations and request what they need.</p>
              </article>
              <article className="step-card">
                <div className="step-number">03 <span>—</span></div>
                <div className="step-art step-art-pickup"><span className="pickup-box">✓</span><span className="pickup-spark">✳</span></div>
                <h3>Coordinate pickup</h3>
                <p>Coordinate collection together and keep track as food reaches its destination.</p>
              </article>
            </div>
          </div>
        </section>

        <section className="audience-section page-width">
          <article className="audience-card donor-card" id="for-donors">
            <div className="audience-illustration donor-illustration"><span className="deli-sun" /><div className="deli-window"><span /><span /><span /></div><div className="deli-awning" /><div className="deli-counter" /></div>
            <div className="audience-content"><span className="section-kicker">FOR FOOD BUSINESSES</span><h2>Make your extra<br />food go further.</h2><p>Turn today’s surplus into someone’s good meal. Share details with local organizations and coordinate a pickup that works for you.</p><Link className="inline-link" to="/register">Start donating <ArrowIcon /></Link></div>
          </article>
          <article className="audience-card recipient-card" id="for-recipients">
            <div className="audience-illustration recipient-illustration"><span className="community-sun" /><div className="community-person person-one" /><div className="community-person person-two" /><div className="community-person person-three" /><div className="community-bowl">♡</div><div className="community-ground" /></div>
            <div className="audience-content"><span className="section-kicker">FOR COMMUNITY ORGANIZATIONS</span><h2>Find good food<br />for your community.</h2><p>Discover available food from local donors, request what your organization needs, and plan the next step together.</p><Link className="inline-link" to="/register">Join as a recipient <ArrowIcon /></Link></div>
          </article>
        </section>

        <section className="impact-section" id="our-impact">
          <div className="impact-inner page-width">
            <div className="impact-art" aria-hidden="true"><div className="impact-ring ring-a" /><div className="impact-ring ring-b" /><div className="impact-sprout"><span /><span /><i /></div><span className="impact-star star-a">✳</span><span className="impact-star star-b">✦</span><span className="impact-star star-c">·</span></div>
            <div className="impact-copy"><span className="section-kicker">OUR SHARED IMPACT</span><h2>Small actions.<br /><span>Lasting good.</span></h2><p>When good food moves through a community, everyone has a part to play. ShareHarvest helps make those connections easier to find and follow.</p><Link className="impact-link" to="/register">Be part of the story <ArrowIcon /></Link></div>
            <div className="impact-side-note"><span className="impact-side-mark"><LeafMark /></span><p>Every shared meal starts with a connection.</p></div>
          </div>
        </section>

        <section className="closing-cta page-width">
          <div className="closing-cta-inner"><span className="closing-mark"><LeafMark /></span><div><span className="section-kicker">LET’S MAKE GOOD THINGS HAPPEN</span><h2>Have food to share? Need food for your community?</h2><p>There’s a place for you here.</p></div><Button asLink to="/register" variant="light" size="large">Get started <ArrowIcon /></Button></div>
        </section>

        <details className="api-diagnostic page-width">
          <summary>Developer diagnostic: API health</summary>
          <Button onClick={checkApiHealth} disabled={checkingApi} variant="outline" size="small">{checkingApi ? 'Checking…' : 'Check API health'}</Button>
          {apiStatus && <pre role="status">{JSON.stringify(apiStatus, null, 2)}</pre>}
        </details>
      </main>

      <footer className="site-footer">
        <div className="footer-main page-width">
          <div className="footer-brand-block"><Link className="brand footer-brand" to="/"><span className="brand-mark"><LeafMark /></span><span>share<span className="brand-name-accent">harvest</span></span></Link><p>Good Food. Shared with Purpose.</p></div>
          <nav className="footer-nav" aria-label="Footer navigation"><a href="#how-it-works">How it works</a><a href="#for-donors">For donors</a><a href="#for-recipients">For recipients</a><a href="#our-impact">Our impact</a></nav>
          <div className="footer-account"><Link to="/login">Log in</Link><Link to="/register">Create an account <ArrowIcon /></Link></div>
        </div>
        <div className="footer-bottom page-width"><span>© {new Date().getFullYear()} ShareHarvest</span><span>Good food, shared with purpose.</span></div>
      </footer>
    </div>
  );
}

export default LandingPage;
