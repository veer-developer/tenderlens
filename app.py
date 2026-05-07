import streamlit as st
from groq import Groq
import fitz
import json
import re

# ─────────────────────────────────────────────
# CONFIG — paste your Groq API key here
# ─────────────────────────────────────────────
GROQ_API_KEY = "your-groq-api-key-here"
client = Groq(api_key=GROQ_API_KEY)

def ask_ai(prompt):
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
    )
    return response.choices[0].message.content

# ─────────────────────────────────────────────
# PAGE SETUP
# ─────────────────────────────────────────────
st.set_page_config(page_title="TenderLens AI", page_icon="🔍", layout="wide")
st.markdown("""
<style>
    .title{font-size:2.5rem;font-weight:800;color:#4A9EFF;text-align:center}
    .subtitle{font-size:1rem;color:#888;text-align:center;margin-bottom:2rem}
    .section-header{font-size:1.1rem;font-weight:700;color:#4A9EFF;margin-top:1rem;
        border-bottom:2px solid #4A9EFF;padding-bottom:4px;margin-bottom:10px}
    .criterion-box{background:#1e2130;border-radius:8px;padding:10px 14px;margin:5px 0;
        border-left:4px solid #4A9EFF}
    .eligible{background:#0d2b1d;border-left:4px solid #00c853;border-radius:8px;padding:10px 14px;margin:6px 0}
    .not-eligible{background:#2b0d0d;border-left:4px solid #ff1744;border-radius:8px;padding:10px 14px;margin:6px 0}
    .review{background:#2b2200;border-left:4px solid #ffa000;border-radius:8px;padding:10px 14px;margin:6px 0}
    .badge-eligible{background:#00c853;color:white;padding:3px 10px;border-radius:20px;font-size:.75rem;font-weight:700}
    .badge-not{background:#ff1744;color:white;padding:3px 10px;border-radius:20px;font-size:.75rem;font-weight:700}
    .badge-review{background:#ffa000;color:white;padding:3px 10px;border-radius:20px;font-size:.75rem;font-weight:700}
    .summary-card{background:#1e2130;border-radius:12px;padding:20px;text-align:center}
    .big-number{font-size:2.5rem;font-weight:800}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

FALLBACK_CRITERIA = [
    {"id": 1, "criterion": "Minimum annual turnover of Rs. 5 crore", "type": "Financial", "mandatory": True, "threshold": "Rs. 5 crore"},
    {"id": 2, "criterion": "At least 3 similar projects in last 5 years", "type": "Technical", "mandatory": True, "threshold": "3 projects"},
    {"id": 3, "criterion": "Valid GST registration certificate", "type": "Document", "mandatory": True, "threshold": None},
    {"id": 4, "criterion": "ISO 9001 certification", "type": "Compliance", "mandatory": False, "threshold": None},
]

def extract_text_from_pdf(uploaded_file):
    try:
        pdf_bytes = uploaded_file.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = "".join(page.get_text() for page in doc)
        uploaded_file.seek(0)
        return text.strip() or "No text found in PDF."
    except Exception as e:
        return f"Error: {e}"

def clean_json(raw):
    raw = re.sub(r"```json|```", "", raw).strip()
    start = raw.find("[")
    if start == -1:
        start = raw.find("{")
    return raw[start:] if start != -1 else raw

def extract_criteria(tender_text):
    prompt = f"""You are a government procurement analyst.
Extract ALL eligibility criteria from this tender document.
Return ONLY a valid JSON array. No explanation. No markdown. No code blocks.

Each item must have exactly these fields:
{{"id": 1, "criterion": "description", "type": "Financial|Technical|Compliance|Document", "mandatory": true, "threshold": "value or null"}}

TENDER TEXT:
{tender_text[:6000]}

Return only the JSON array starting with [:"""
    try:
        raw = clean_json(ask_ai(prompt))
        return json.loads(raw)
    except:
        return FALLBACK_CRITERIA

def evaluate_bidder(name, text, criteria):
    prompt = f"""You are a strict government procurement evaluator.
Evaluate the bidder against EACH criterion. Return ONLY a valid JSON array. No markdown. No explanation.

Each object must have exactly these fields:
{{"criterion_id": <int>, "criterion_name": "<text>", "verdict": "Eligible|Not Eligible|Needs Review", "confidence": <0.0-1.0>, "evidence": "<specific text found>", "reason": "<explanation>"}}

Rules:
- Clearly meets requirement → Eligible, confidence >= 0.85
- Ambiguous or partial → Needs Review, confidence 0.50-0.84
- Clearly fails or missing → Not Eligible, confidence >= 0.85
- Cannot find info → Needs Review, confidence < 0.55
- NEVER give Not Eligible with low confidence

CRITERIA: {json.dumps(criteria)}
BIDDER: {name}
DOCUMENTS: {text[:5000]}

Return only the JSON array starting with [:"""
    try:
        raw = clean_json(ask_ai(prompt))
        result = json.loads(raw)
        return result if isinstance(result, list) else [result]
    except:
        return [
            {
                "criterion_id": c["id"],
                "criterion_name": c["criterion"],
                "verdict": "Needs Review",
                "confidence": 0.4,
                "evidence": "Could not parse response",
                "reason": "Manual review required"
            }
            for c in criteria
        ]

def overall_verdict(evals, criteria):
    mandatory = {c["id"] for c in criteria if c.get("mandatory", True)}
    has_review = False
    for ev in evals:
        if ev.get("criterion_id") in mandatory:
            if ev.get("verdict") == "Not Eligible": return "Not Eligible"
            if ev.get("verdict") == "Needs Review": has_review = True
    return "Needs Review" if has_review else "Eligible"

def badge(verdict):
    if verdict == "Eligible":     return '<span class="badge-eligible">✅ ELIGIBLE</span>'
    if verdict == "Not Eligible": return '<span class="badge-not">❌ NOT ELIGIBLE</span>'
    return '<span class="badge-review">⚠️ NEEDS REVIEW</span>'

def render_ev(ev, criteria):
    cname   = ev.get("criterion_name") or next((c["criterion"] for c in criteria if c["id"] == ev.get("criterion_id")), "Unknown")
    verdict = ev.get("verdict", "Needs Review")
    conf    = float(ev.get("confidence", 0))
    css     = "eligible" if verdict == "Eligible" else ("not-eligible" if verdict == "Not Eligible" else "review")
    cc      = "#00c853" if conf >= 0.85 else ("#ffa000" if conf >= 0.55 else "#ff1744")
    st.markdown(f"""
    <div class="{css}">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
        <strong style="color:#eee;font-size:.9rem;">{cname}</strong>{badge(verdict)}
      </div>
      <div style="font-size:.8rem;color:#aaa;margin-bottom:4px;">📄 <em>{ev.get("evidence","No evidence")}</em></div>
      <div style="font-size:.8rem;color:#ccc;margin-bottom:6px;">{ev.get("reason","")}</div>
      <span style="color:{cc};font-size:.75rem;">● Confidence: {int(conf*100)}%</span>
    </div>""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────
for k, v in [("criteria", []), ("results", {}), ("ready", False)]:
    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────
st.markdown('<div class="title">🔍 TenderLens AI</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Explainable AI Platform for Government Tender Evaluation | AI for Bharat Hackathon</div>', unsafe_allow_html=True)

left, right = st.columns([1, 2])

with left:
    st.markdown('<div class="section-header">📋 Step 1: Tender Document</div>', unsafe_allow_html=True)
    tf = st.file_uploader("Upload Tender PDF", type=["pdf"], key="t")
    if tf and st.button("🔍 Extract Eligibility Criteria"):
        with st.spinner("Analysing tender with AI..."):
            st.session_state.criteria = extract_criteria(extract_text_from_pdf(tf))
            st.session_state.ready = True
            st.session_state.results = {}
        st.success(f"✅ Extracted {len(st.session_state.criteria)} criteria!")

    if st.session_state.criteria:
        st.markdown('<div class="section-header">📌 Criteria</div>', unsafe_allow_html=True)
        for c in st.session_state.criteria:
            tag = "🔴 Mandatory" if c.get("mandatory") else "🔵 Optional"
            thr = f'<div style="color:#4A9EFF;font-size:.78rem;margin-top:3px;">Threshold: {c["threshold"]}</div>' if c.get("threshold") else ""
            st.markdown(f"""<div class="criterion-box">
              <div style="font-size:.75rem;color:#888;">{tag} · {c.get("type","")}</div>
              <div style="color:#eee;font-size:.88rem;margin-top:3px;">{c.get("criterion","")}</div>{thr}
            </div>""", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown('<div class="section-header">👤 Step 2: Bidder Documents</div>', unsafe_allow_html=True)
    if not st.session_state.ready:
        st.info("Process tender document first.")
    else:
        bname = st.text_input("Bidder / Company Name")
        bf = st.file_uploader("Upload Bidder PDF", type=["pdf"], key="b")
        if bf and bname and st.button("⚡ Evaluate Bidder"):
            with st.spinner(f"Evaluating {bname} with AI..."):
                btext = extract_text_from_pdf(bf)
                evals = evaluate_bidder(bname, btext, st.session_state.criteria)
                ov = overall_verdict(evals, st.session_state.criteria)
                st.session_state.results[bname] = {"evals": evals, "overall": ov}
            st.success(f"✅ {bname} — {ov}")

with right:
    if st.session_state.results:
        st.markdown('<div class="section-header">📊 Evaluation Results</div>', unsafe_allow_html=True)
        el  = sum(1 for v in st.session_state.results.values() if v["overall"] == "Eligible")
        nel = sum(1 for v in st.session_state.results.values() if v["overall"] == "Not Eligible")
        nr  = sum(1 for v in st.session_state.results.values() if v["overall"] == "Needs Review")
        tot = len(st.session_state.results)

        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f'<div class="summary-card"><div class="big-number" style="color:#4A9EFF;">{tot}</div><div style="color:#888;font-size:.85rem;">Total</div></div>', unsafe_allow_html=True)
        c2.markdown(f'<div class="summary-card"><div class="big-number" style="color:#00c853;">{el}</div><div style="color:#888;font-size:.85rem;">Eligible</div></div>', unsafe_allow_html=True)
        c3.markdown(f'<div class="summary-card"><div class="big-number" style="color:#ff1744;">{nel}</div><div style="color:#888;font-size:.85rem;">Not Eligible</div></div>', unsafe_allow_html=True)
        c4.markdown(f'<div class="summary-card"><div class="big-number" style="color:#ffa000;">{nr}</div><div style="color:#888;font-size:.85rem;">Needs Review</div></div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        for bname, res in st.session_state.results.items():
            with st.expander(f"  {bname}  —  {res['overall']}", expanded=True):
                st.markdown(f'<div style="margin-bottom:12px;">Overall: {badge(res["overall"])}</div>', unsafe_allow_html=True)
                st.markdown("**Criterion-by-Criterion Breakdown:**")
                for ev in res["evals"]:
                    render_ev(ev, st.session_state.criteria)
                if res["overall"] == "Needs Review":
                    st.markdown("---")
                    st.markdown("**🧑‍⚖️ Human Review Required**")
                    dec = st.selectbox(
                        "Officer decision:",
                        ["Pending Review", "Override → Eligible", "Override → Not Eligible", "Request More Documents"],
                        key=f"r_{bname}"
                    )
                    if dec != "Pending Review":
                        st.success(f"✅ Recorded: {dec}")

        st.markdown("---")
        lines = ["TENDERLENS AI — EVALUATION REPORT", "=" * 50, ""]
        for bname, res in st.session_state.results.items():
            lines += [f"BIDDER: {bname}", f"VERDICT: {res['overall']}", "-" * 30]
            for ev in res["evals"]:
                lines += [
                    f"  [{ev.get('verdict')}] {ev.get('criterion_name', '')}",
                    f"    Evidence: {ev.get('evidence')}",
                    f"    Reason:   {ev.get('reason')}",
                    f"    Confidence: {int(float(ev.get('confidence', 0)) * 100)}%", ""
                ]
            lines.append("=" * 50)
        st.download_button("📄 Download Report (.txt)", "\n".join(lines), file_name="TenderLens_Report.txt")

    else:
        st.markdown("""<div style="text-align:center;padding:80px 40px;">
          <div style="font-size:4rem;">🔍</div>
          <div style="font-size:1.2rem;margin-top:16px;color:#777;">Upload a tender and evaluate bidders to see results</div>
          <div style="font-size:.9rem;margin-top:8px;color:#555;">Criterion-level verdicts · Confidence scores · Evidence citations</div>
        </div>""", unsafe_allow_html=True)

st.markdown("---")
st.markdown('<div style="text-align:center;color:#555;font-size:.8rem;">TenderLens AI · AI for Bharat Hackathon · PAN IIT Bangalore · Team TenderLens</div>', unsafe_allow_html=True)