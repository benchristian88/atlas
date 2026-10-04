"use client";

import { useEffect, useState } from "react";
import { apiRequest } from "../lib/api";
import { INSTALLATION_LABELS, updateMessage, upgradeGuidance } from "../lib/updates.mjs";
import { Button } from "./button";
import styles from "./updates.module.css";

export function Updates({ buildInfo }) {
  const [info, setInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [nextRefresh, setNextRefresh] = useState(0);
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    let active = true;
    apiRequest("/system-settings/updates").then(result => {
      if (active) {
        setInfo(result);
        const timestamp = Date.now();
        setNow(timestamp);
        setNextRefresh(timestamp + result.refresh_after_seconds * 1000);
      }
    }).catch(() => { if (active) setInfo({ status: "unavailable" }); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (now >= nextRefresh) return;
    const timer = setTimeout(() => setNow(Date.now()), 1000);
    return () => clearTimeout(timer);
  }, [now, nextRefresh]);

  async function check() {
    setLoading(true);
    try {
      const result = await apiRequest("/system-settings/updates/check", { method: "POST" });
      setInfo(result);
      const timestamp = Date.now();
      setNow(timestamp);
      setNextRefresh(timestamp + result.refresh_after_seconds * 1000);
    } catch {
      setInfo({ status: "unavailable" });
    } finally { setLoading(false); }
  }

  const identity = buildInfo || (info?.current_version ? {
    version: info.current_version, release_channel: info.current_channel,
    build_id: info.build_id, install_method: info.install_method,
  } : null);
  const waiting = Math.max(0, Math.ceil((nextRefresh - now) / 1000));

  return <section className="ops-card system-settings-section" aria-labelledby="settings-updates">
    <h2 id="settings-updates">Updates</h2>
    <p className="secondary-text">Release availability and guidance for your installation.</p>
    {identity && <dl className={`detail-list ${styles.identity}`}>
      <dt>Current version</dt><dd>{identity.version}</dd>
      <dt>Release channel</dt><dd>{identity.release_channel}</dd>
      <dt>Build</dt><dd className="mono">{identity.build_id || "Unavailable"}</dd>
      <dt>Installation</dt><dd>{INSTALLATION_LABELS[identity.install_method] || "Unavailable"}</dd>
      {info?.latest_version && <><dt>Latest available</dt><dd>{info.latest_version} ({info.latest_channel})</dd></>}
    </dl>}
    <p role="status" aria-live="polite">{loading ? "Checking release availability…" : updateMessage(info)}</p>
    <div className={styles.actions}>
      <Button variant="secondary" onClick={check} loading={loading} disabled={waiting > 0}>Check for updates</Button>
      {info?.release_url && <Button href={info.release_url} prefetch={false} target="_blank" rel="noopener noreferrer">View release</Button>}
    </div>
    {waiting > 0 && <p className="secondary-text"><small>You can check again in {waiting} seconds.</small></p>}
    {info?.checked_at && <p className="secondary-text"><small>Checked {new Date(info.checked_at).toLocaleString()}{info.cached ? " · cached result" : ""}.</small></p>}
    {identity && <div className={styles.guidance}>
      <h3>Upgrade guidance</h3>
      <p>{upgradeGuidance(identity.install_method)}</p>
      {info?.upgrade_guide_url && <Button variant="quiet" href={info.upgrade_guide_url} prefetch={false} target="_blank" rel="noopener noreferrer">Read upgrade guide</Button>}
      <p className="secondary-text">Updates are installed by your deployment operator. Atlas remains available when update information cannot be retrieved.</p>
    </div>}
  </section>;
}
