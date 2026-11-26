/** Do not present an infrastructure failure as an access denial or sign-out. */
export function SettingsUnavailable() {
  return <section role="alert" style={{ maxWidth: "42rem", margin: "3rem auto", padding: "1rem" }}>
    <h1>Account service temporarily unavailable</h1>
    <p>The account data service is not responding. Your access has not been changed.</p>
    <p>Wait a few minutes before reloading. If the daily database quota has been reached, access will return when the quota resets or the service is restored.</p>
  </section>;
}
