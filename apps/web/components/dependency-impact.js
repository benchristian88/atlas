"use client";

import { useState } from "react";
import { DEPENDENCY_REQUIREMENT_LABELS, DEPENDENCY_STRATEGY_LABELS, FAILURE_EFFECT_LABELS, singletonImpactRequest, dependencyGroupLabel, availableDependencyName } from "../lib/dependency-semantics.mjs";

function EffectChoices({ label, value, disabled, onChange }) {
  return <fieldset className="impact-choices" disabled={disabled}><legend>{label}</legend><div>{Object.entries(FAILURE_EFFECT_LABELS).map(([effect, text]) => <button key={effect} type="button" className="button button-secondary" aria-pressed={value === effect} onClick={() => onChange(effect)}>{value === effect && <span aria-hidden="true">✓ </span>}{effect === "unknown" ? "Not sure / Unknown" : text}</button>)}</div></fieldset>;
}

function GroupEditor({ group, service, groups, dependencies, saving, onSave }) {
  const [form, setForm] = useState(group || { name: "", strategy: "any", requirement: "required", failure_effect: "unknown", asset_dependency_ids: [], service_dependency_ids: [] });
  const update = (key, value) => setForm(current => ({ ...current, [key]: value }));
  const eligible = dependencies.filter(d => !d.dependency_group_id || d.dependency_group_id === group?.id);
  const count = form.asset_dependency_ids.length + form.service_dependency_ids.length;
  return <form className="dependency-group-form" onSubmit={event => {
    event.preventDefault();
    const { name, strategy, requirement, failure_effect, asset_dependency_ids, service_dependency_ids } = form;
    onSave({ name: name.trim() || availableDependencyName(`${service.name} Providers`, groups), strategy, requirement, failure_effect, asset_dependency_ids, service_dependency_ids });
  }}><fieldset disabled={saving}><legend>Dependencies that provide the same capability</legend><div className="dependency-member-options">{eligible.map(d => {
    const field = d.kind === "asset" ? "asset_dependency_ids" : "service_dependency_ids";
    return <label className="checkbox-field" key={`${d.kind}:${d.id}`}><input type="checkbox" checked={form[field].includes(d.id)} onChange={event => update(field, event.target.checked ? [...form[field], d.id] : form[field].filter(id => id !== d.id))} /><span>{d.name}</span></label>;
  })}</div><div className="form-grid"><label><span>Group name (optional)</span><input maxLength={255} value={form.name} onChange={event => update("name", event.target.value)} /></label><label><span>How do these providers work together?</span><select value={form.strategy} onChange={event => update("strategy", event.target.value)}>{Object.entries(DEPENDENCY_STRATEGY_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label><span>Requirement</span><select value={form.requirement} onChange={event => update("requirement", event.target.value)}>{Object.entries(DEPENDENCY_REQUIREMENT_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label><span>If this requirement cannot be met</span><select value={form.failure_effect} onChange={event => update("failure_effect", event.target.value)}>{Object.entries(FAILURE_EFFECT_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label></div><button className="button button-secondary" disabled={!count} type="submit">Save dependency impact</button></fieldset></form>;
}

export function DependencyImpact({ service, assets, services, groups, canManage, saving, mutate }) {
  const dependencies = [...assets.map(d => ({ ...d, kind: "asset", name: d.asset_name || "Unavailable Asset" })), ...services.map(d => ({ ...d, kind: "service", name: d.target_service_name || "Unavailable Service" }))];
  const members = group => dependencies.filter(d => (d.kind === "asset" ? group.asset_dependency_ids : group.service_dependency_ids).includes(d.id));
  const singletons = dependencies.filter(d => !d.dependency_group_id || groups.some(g => g.id === d.dependency_group_id && g.asset_dependency_ids.length + g.service_dependency_ids.length === 1));
  function saveSingleton(d, group, changes) {
    const request = singletonImpactRequest(service.id, d, d.kind, group, changes, { serviceName: service.name, groups });
    return mutate(`impact-${d.id}`, request.path, request.body, request.method);
  }
  return <section className="ops-card entity-section" id="dependency-impact" aria-label="Dependency impact"><div className="form-card-header"><h2>Dependency impact</h2></div><p>Define what happens to this Service when its dependencies are unavailable.</p>
    {!dependencies.length && <p className="empty-state">Add an Asset or Service dependency to describe its impact.</p>}
    <div className="dependency-impact-list">{singletons.map(d => {
      const group = groups.find(g => g.id === d.dependency_group_id);
      const requirement = group?.requirement || (d.required_for_operation ? "required" : "optional");
      return <article className="dependency-impact-row" key={`${d.kind}:${d.id}`}><strong>{d.name}</strong><p>{DEPENDENCY_REQUIREMENT_LABELS[requirement]} dependency · {d.source_label || d.relationship_type_name || "Recorded relationship"}</p>
        {canManage ? <EffectChoices label={`What happens to ${service.name} if ${d.name} is unavailable?`} value={group?.failure_effect || "unknown"} disabled={Boolean(saving)} onChange={failure_effect => saveSingleton(d, group, { failure_effect })} /> : <p>If unavailable: {FAILURE_EFFECT_LABELS[group?.failure_effect || "unknown"]}</p>}
        {canManage && <label className="impact-requirement"><span>Requirement for {d.name}</span><select disabled={Boolean(saving)} value={requirement} onChange={event => group ? saveSingleton(d, group, { requirement: event.target.value }) : mutate(`requirement-${d.id}`, d.kind === "asset" ? `/service-asset-dependencies/${d.id}` : `/service-dependencies/${d.id}`, { required_for_operation: event.target.value === "required" }, "PATCH")}><option value="required">Required</option><option value="optional">Optional</option></select></label>}
      </article>;
    })}{groups.filter(g => g.asset_dependency_ids.length + g.service_dependency_ids.length > 1).map(group => <article className="dependency-impact-row" key={group.id}><strong>{dependencyGroupLabel(group, service.name)}</strong><p>{members(group).map(d => d.name).join(" · ")}</p><p>{DEPENDENCY_REQUIREMENT_LABELS[group.requirement]} · {DEPENDENCY_STRATEGY_LABELS[group.strategy]}</p>{canManage ? <><label><span>How do these providers work together?</span><select disabled={Boolean(saving)} value={group.strategy} onChange={event => mutate(`group-${group.id}`, `/dependency-groups/${group.id}`, { strategy: event.target.value }, "PATCH")}><option value="all">All required</option><option value="any">Any one is sufficient</option></select></label><EffectChoices label={`What happens to ${service.name} if this requirement can no longer be met?`} value={group.failure_effect} disabled={Boolean(saving)} onChange={failure_effect => mutate(`group-${group.id}`, `/dependency-groups/${group.id}`, { failure_effect }, "PATCH")} /></> : <p>If unavailable: {FAILURE_EFFECT_LABELS[group.failure_effect]}</p>}</article>)}</div>
    {canManage && dependencies.some(d => !d.dependency_group_id) && <details className="entity-edit-disclosure"><summary>Combine providers for the same capability</summary><p>Use this when multiple dependencies work together. Saving applies the chosen requirement to every selected relationship.</p><GroupEditor service={service} groups={groups} key={groups.map(group => group.id).join(":")} dependencies={dependencies} saving={Boolean(saving)} onSave={body => mutate("group-new", `/services/${service.id}/dependency-groups`, body)} /></details>}
    <details className="entity-edit-disclosure"><summary>Advanced configuration</summary><p>Dependency groups retain names, membership, requirements and recorded effects. Changing a group requirement applies to every member.</p>{groups.map(group => <details key={group.id}><summary>{dependencyGroupLabel(group, service.name)} · {DEPENDENCY_STRATEGY_LABELS[group.strategy]}</summary>{canManage ? <><GroupEditor service={service} groups={groups} group={group} dependencies={dependencies} saving={Boolean(saving)} onSave={body => mutate(`group-${group.id}`, `/dependency-groups/${group.id}`, body, "PATCH")} /><button type="button" className="text-button text-danger" disabled={Boolean(saving)} onClick={() => mutate(group.id, `/dependency-groups/${group.id}`, null, "DELETE")}>Remove dependency group</button></> : <p>{members(group).map(d => d.name).join(" · ")} · {DEPENDENCY_REQUIREMENT_LABELS[group.requirement]} · {FAILURE_EFFECT_LABELS[group.failure_effect]}</p>}</details>)}</details>
  </section>;
}
