"""DisasterAI test console: send an incident to the n8n workflow and read the result.

    streamlit run ui/app.py

The n8n webhook answers once, at the end of the run, so the progress bar is a timer, not the real step. The Pipeline tab shows the real
steps afterwards. Nothing here changes the workflow.
"""
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from ui import client, history, render, samples  # noqa: E402

st.set_page_config(page_title="DisasterAI test console", page_icon="🛰️", layout="wide")

DISCLAIMER = "Decision support from an AI prototype. It does not replace emergency services. The severity scale is this project's own working scale, not an official one."
STATE_ICON = {"ok": "🟢", "warn": "🟡", "down": "🔴"}
STATE_WORD = {"ok": "ready", "warn": "limited", "down": "down"}


@st.cache_data(ttl=20, show_spinner=False)
def cached_health(webhook_url):
    return client.check_services(webhook_url)


@st.cache_data(show_spinner=False)
def cached_samples():
    return samples.load_samples()


def alert(level, title, message=""):
    text = f"**{title}**" + (f"  \n{message}" if message else "")
    {"success": st.success, "warning": st.warning, "error": st.error}.get(level, st.info)(text)


# ---------------------------------------------------------------- sidebar
def sidebar():
    st.sidebar.title("🛰️ DisasterAI")
    st.sidebar.caption("Test console for the n8n workflow")
    st.sidebar.subheader("Target")
    names = list(client.PROFILES) + ["Custom URL"]
    choice = st.sidebar.selectbox("n8n instance", names, index=names.index(client.DEFAULT_PROFILE), key="profile")
    if choice == "Custom URL":
        url = st.sidebar.text_input("Webhook URL", "http://localhost:5678/webhook/incident", key="custom_url")
        mock_default = False
    else:
        url, mock_default = client.PROFILES[choice]["url"], client.PROFILES[choice]["mock"]
    mock = st.sidebar.checkbox("This n8n uses MOCK agents", value=mock_default, key=f"mock_{choice}",
                               help="Tick it when the workflow is connected to the canned mock. Results are then labelled MOCK, as the project rules require.")
    st.sidebar.code(url, language=None)
    timeout = st.sidebar.number_input("Timeout (seconds)", 30, 900, 300, step=30, help="Runs usually take 20 s to 2 minutes; slow models can take longer.")
    language = st.sidebar.radio("Report language", ["en", "fr"], horizontal=True, key="language")
    save = st.sidebar.toggle("Save every run to eval/results/ui_runs", value=True)

    st.sidebar.subheader("Is everything up?")
    if st.sidebar.button("Refresh", key="refresh_health"):
        cached_health.clear()
    for name, state, detail in cached_health(url):
        st.sidebar.markdown(f"{STATE_ICON[state]} **{name}**: {STATE_WORD[state]}  \n<small>{detail}</small>", unsafe_allow_html=True)
    return {"url": url, "profile": choice, "mock": mock, "timeout": int(timeout), "language": language, "save": save}


# ---------------------------------------------------------------- result
def result_view(rec, expected=None, manual_checks=None, key="r"):
    """rec: dict with kind, message, hint, seconds, body, text, image (tuple or None), mock."""
    body, kind = rec.get("body"), rec["kind"]
    if rec.get("mock"):
        st.warning("**MOCK run.** The agents were canned. Do not quote any of this as a model result.")
    if body is None or kind in ("rejected",) and not body.get("report"):
        if body is not None:
            alert(*render.status_banner(body))
        else:
            alert("error", "The run did not complete", rec.get("message", ""))
            if rec.get("hint"):
                st.info("What to do: " + rec["hint"])
            st.caption(f"Failed after {rec.get('seconds', 0):.1f} s.")
        return
    level, title, msg = render.status_banner(body)
    alert(level, title, msg)
    st.caption(DISCLAIMER)

    stats = [("Severity", str(body.get("severity") or "-")), ("Incident type", str(body.get("incident_type") or "-").replace("_", " ")),
             ("Guidance coverage", str(body.get("knowledge_coverage") or "-")), ("Validation", render.validation_view(body.get("validation"))[0]),
             ("Run time", f"{rec.get('seconds', 0):.0f} s")]
    # a wrapping row of tiles, not st.metric in st.columns: those cut or break words ("fore...", "Severi ty") in a narrow window
    tiles = "".join(f"<div style='min-width:7.5rem'><div style='font-size:0.8rem;opacity:0.7;white-space:nowrap'>{label}</div>"
                    f"<div style='font-size:1.3rem;font-weight:600;line-height:1.3;white-space:nowrap'>{value}</div></div>" for label, value in stats)
    st.markdown(f"<div style='display:flex;flex-wrap:wrap;gap:0.6rem 1.6rem;margin:0.4rem 0 0.8rem'>{tiles}</div>", unsafe_allow_html=True)

    if expected:
        with st.expander("Expected values for this fixed incident", expanded=True):
            for label, ok in render.check_expected(expected, body):
                st.markdown(("✅ " if ok else "❌ ") + label)
    if manual_checks:
        with st.expander("Manual checks to score by reading the report"):
            for i, item in enumerate(manual_checks):
                st.checkbox(item, key=f"{key}_manual_{i}")

    report = body.get("report") or {}
    t_report, t_image, t_pipe, t_raw = st.tabs(["Report", "Image and report", "Pipeline", "Raw JSON"])
    with t_report:
        report_tab(body, report)
    with t_image:
        image_tab(rec, report)
    with t_pipe:
        pipeline_tab(body)
    with t_raw:
        st.download_button("Download the raw answer (.json)", render.dumps(body), file_name="answer.json", mime="application/json", key=f"{key}_dl_json")
        st.json(body, expanded=False)


def source_list(items, empty="Nothing listed."):
    items = items or []
    if not items:
        st.caption(empty)
    for it in items:
        if isinstance(it, str):
            st.markdown(f"- {it}")
        else:
            conf = f" · confidence {it['confidence']}" if it.get("confidence") else ""
            st.markdown(f"- {it.get('text', '')}  \n  <small>{render.chips(it.get('source'))}{conf}</small>", unsafe_allow_html=True)


def report_tab(body, report):
    if not report:
        st.info("No structured report. See the Pipeline tab for what failed.")
        return
    if report.get("summary"):
        st.markdown(f"#### Summary\n{report['summary']}")
    if report.get("location"):
        st.markdown(f"**Location:** {report['location']}")
    left, right = st.columns(2)
    with left:
        st.markdown("##### What the report says")
        source_list(report.get("reported"))
        st.markdown("##### What the image shows")
        source_list(report.get("observed"), "No image observations.")
    assessment = report.get("assessment") or {}
    with right:
        st.markdown("##### Assessment")
        source_list(assessment.get("basis"))
        if assessment.get("risks"):
            st.markdown("**Risks**")
            source_list(assessment["risks"])
        if assessment.get("possibly_affected"):
            st.markdown("**Possibly affected**")
            source_list(assessment["possibly_affected"])
    for conflict in assessment.get("conflicts") or []:
        st.warning("**The sources disagree.** " + str(conflict))

    st.markdown("##### Recommended actions")
    knowledge = report.get("knowledge") or {}
    if knowledge.get("no_guidance_statement"):
        st.info(knowledge["no_guidance_statement"])
    for i, rec in enumerate(report.get("recommendations") or []):
        e = render.entry(rec.get("entry_id")) if rec.get("entry_id") else None
        st.markdown(f"{i + 1}. {rec.get('text', '')}  \n   <small>{render.chips(rec.get('source'))}" + (f" · entry {rec['entry_id']}" if rec.get("entry_id") else "") + "</small>",
                    unsafe_allow_html=True)
        if e:
            with st.expander(f"Source passage {rec['entry_id']}: {render.short(e['title'], 80)}"):
                st.write(e["text"])
                st.caption(f"{e['source']} · corpus language {e['language']}")
    if not report.get("recommendations"):
        st.caption("No recommendations were produced.")
    st.markdown("##### What is uncertain")
    source_list(report.get("uncertainties"), "Nothing listed.")
    st.markdown("##### Information still needed")
    source_list(report.get("information_needed"), "Nothing listed.")
    if body.get("report_markdown"):
        with st.expander("The report as the workflow wrote it (markdown)"):
            st.markdown(body["report_markdown"])
        st.download_button("Download report (.md)", body["report_markdown"], file_name="report.md", mime="text/markdown", key="dl_md_" + str(id(body)))
    if report.get("disclaimer"):
        st.caption(report["disclaimer"])


def image_tab(rec, report):
    level, text, status = render.image_message(report, bool(rec.get("image")))
    alert(level, text)
    if rec.get("image"):
        left, right = st.columns([1, 1])
        left.image(rec["image"][0], caption=rec["image"][1], width="stretch")
        with right:
            st.markdown("**Observed in the image**")
            source_list(report.get("observed"), "No observations.")
            for conflict in (report.get("assessment") or {}).get("conflicts") or []:
                st.warning(str(conflict))


def pipeline_tab(body):
    rows = render.timeline_rows(body.get("models_used"))
    total = sum(r["seconds"] for r in rows)
    slow = render.slowest_step(rows)
    if rows:
        st.markdown(f"**{len(rows)} model calls, {total:.0f} s of model time.**" + (f" Slowest: {slow['step']} ({slow['seconds']:.0f} s on {slow['model']})." if slow else ""))
        st.dataframe(rows, hide_index=True, column_config={"seconds": st.column_config.ProgressColumn("seconds", min_value=0, max_value=max(total, 1), format="%.1f")})
        retried = [r for r in rows if r["failed attempts"]]
        if retried:
            st.caption("Some calls fell back to another model first: " + "; ".join(f"{r['step']} ({r['failed detail']})" for r in retried))
    else:
        st.info("The answer lists no model calls.")
    lines = render.degraded_lines(body.get("degraded_steps"))
    st.markdown("##### Degraded steps")
    if lines:
        for line in lines:
            st.warning(line)
    else:
        st.success("None.")
    status, repaired, now, first = render.validation_view(body.get("validation"))
    st.markdown("##### Automatic checks")
    st.markdown(f"Final status **{status}**" + (", after one repair pass" if repaired else ""))
    if first:
        st.markdown("Problems found in the first version, before the repair:")
        for check, msg in first:
            st.markdown(f"- `{check}`: {msg}")
    elif repaired:
        st.caption("The workflow did not record the reason for the repair (this answer has no first_violations).")
    for check, msg in now:
        st.error(f"`{check}`: {msg}")
    st.markdown("##### Retrieved knowledge entries")
    ids = body.get("retrieved_entry_ids") or []
    if not ids:
        st.caption("None.")
    for i in ids:
        e = render.entry(i)
        with st.expander(f"{i}: {render.short(e['title'], 80) if e else 'not found in rag/corpus'}"):
            if e:
                st.write(e["text"])
                st.caption(e["source"])
    st.markdown("##### Versions")
    st.json(body.get("prompt_versions") or {}, expanded=False)


# ---------------------------------------------------------------- run tab
def run_tab(cfg):
    catalog = cached_samples()
    labels = ["Write my own incident"] + list(catalog)

    def on_sample():
        s = catalog.get(st.session_state.get("sample"))
        if s:
            st.session_state["text"] = s["text"]
            st.session_state["language"] = s["language"]
        st.session_state.pop("last", None)

    left, right = st.columns([2, 3], gap="large")
    with left:
        st.subheader("1. Describe the incident")
        st.selectbox("Start from", labels, key="sample", on_change=on_sample)
        sample = catalog.get(st.session_state.get("sample"))
        if sample and sample["note"]:
            st.caption("Designed to test: " + render.short(sample["note"], 220))
        text = st.text_area("Incident report", key="text", height=170, placeholder="What was seen, where, when, how many people. Any language.")
        st.caption(f"{len(text.strip())} characters" + ("" if len(text.strip()) >= client.MIN_TEXT else f" (at least {client.MIN_TEXT} needed)"))
        uploaded = st.file_uploader("Photo (optional)", type=["png", "jpg", "jpeg", "webp"], help="PNG, JPEG or WebP, up to 8 MB.")
        image = None
        if uploaded is not None:
            image = (uploaded.getvalue(), uploaded.name, uploaded.type)
            st.image(uploaded, width=260)
        elif sample and sample["image"]:
            if st.checkbox(f"Send the sample image ({sample['image'].name})", value=True, key=f"use_sample_image_{sample['id']}"):
                image = samples.image_tuple(sample["image"])
                st.image(image[0], width=260)
        problems = client.check_input(text, image[0] if image else None, image[2] if image else None)
        # no error on an empty form: only say what is missing once something has been typed or attached
        if text.strip() or image:
            for p in problems:
                st.error(p)
        go = st.button("Run the workflow", type="primary", disabled=bool(problems), key="run", help="Sends the incident to n8n and waits for the full report.")
        st.caption("Please do not change the form while a run is in progress.")
        progress = st.empty()  # the progress bar lives here, next to the Run button where the eyes are, not in the result column

    with right:
        st.subheader("2. Read the result")
        if go:
            past = history.list_runs()
            typical = render.typical_seconds(past)
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(client.post_incident, cfg["url"], text, cfg["language"], image, cfg["timeout"])
                bar = progress.progress(0.0, text="Sending…")
                started = time.time()
                while not future.done():
                    elapsed = time.time() - started
                    expect = typical or 90
                    note = f"Usually about {typical:.0f} s here." if typical else "Runs usually take 20 s to 2 minutes."
                    bar.progress(min(elapsed / expect, 0.95), text=f"Running for {elapsed:.0f} s. {note} The real steps appear when it ends.")
                    time.sleep(0.4)
                result = future.result()
            bar.empty()
            rec = {"kind": result.kind, "message": result.message, "hint": result.hint, "seconds": result.seconds, "body": result.body, "text": text, "image": image, "mock": cfg["mock"]}
            if cfg["save"]:
                try:
                    history.save_run(result, cfg["url"], cfg["profile"], cfg["mock"], text, cfg["language"], image, sample["id"] if sample else None)
                except OSError as exc:
                    st.warning(f"The run could not be saved: {exc}")
            st.session_state["last"] = {"rec": rec, "expected": sample["expected"] if sample else None, "manual": sample["manual_checks"] if sample else None}
        last = st.session_state.get("last")
        if last:
            result_view(last["rec"], last["expected"], last["manual"], key="last")
        else:
            st.info("The report will appear here. Pick a fixed incident on the left to try it quickly, or write your own.")


# ---------------------------------------------------------------- history tab
def history_tab():
    runs = history.list_runs()
    if not runs:
        st.info("No saved run yet. Runs are saved in eval/results/ui_runs when the sidebar switch is on.")
        return

    def label(r):
        resp = r.get("response") or {}
        return f"{r['saved_at'][:8]} {r['saved_at'][9:15]} · {r.get('sample_id') or 'free text'} · {r['kind']} · {resp.get('severity') or '-'} · {r.get('seconds')} s" + (" · MOCK" if r.get("mock") else "")

    by_label = {}
    for r in runs:
        name = label(r)
        while name in by_label:  # two runs with the same label must both stay in the list
            name += " ·"
        by_label[name] = r
    names = list(by_label)
    pick = st.selectbox("Saved run", names, key="hist_pick")
    rec = by_label[pick]
    img = history.image_bytes(rec)
    st.caption(f"{rec['url']} · output language {rec['language']}")
    with st.expander("Input text"):
        st.write(rec["text"])
    result_view({"kind": rec["kind"], "message": rec.get("message", ""), "hint": "", "seconds": rec.get("seconds") or 0, "body": rec.get("response"), "text": rec["text"],
                 "image": (img, rec["image_file"], "") if img else None, "mock": rec.get("mock")}, key="hist")
    st.divider()
    st.markdown("##### Compare with another run")
    other = st.selectbox("Other run", [n for n in names if n != pick], key="hist_other") if len(names) > 1 else None
    if other:
        diff = history.compare(rec, by_label[other])
        if diff:
            st.dataframe([{"field": a, "selected run": str(b), "other run": str(c)} for a, b, c in diff], hide_index=True)
        else:
            st.success("The two runs are identical on every compared field.")


def main():
    cfg = sidebar()
    st.title("DisasterAI test console")
    t_run, t_hist = st.tabs(["Run", "History"])
    with t_run:
        run_tab(cfg)
    with t_hist:
        history_tab()


main()
