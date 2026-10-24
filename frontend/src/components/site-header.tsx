/** Static navigation shared by routes; no browser state or API imports. */
export function SiteHeader(): React.JSX.Element {
  return (
    <>
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <header className="site-header">Incident Response Copilot</header>
    </>
  );
}
