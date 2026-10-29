import { useEffect, useState } from "react";
import {
  ArrowUpRight,
  ArrowRight,
  Compass,
  MapPin,
  CalendarDays,
  Users,
  Plane,
  TrainFront,
  Check,
  LoaderCircle,
  Sun,
  AlertCircle,
  Wallet,
  Download,
  ArrowLeft,
  Leaf,
  Utensils,
  Landmark,
  Mountain,
  Waves,
  ShoppingBag,
} from "lucide-react";
import "./index.css";

const interests = [
  [Utensils, "Food"],
  [Landmark, "Culture"],
  [Leaf, "Nature"],
  [Mountain, "Adventure"],
  [Waves, "Beaches"],
  [ShoppingBag, "Shopping"],
];
const stages = [
  "Checking your trip details",
  "Finding places, stays & travel options",
  "Putting your itinerary together",
  "Checking your costs",
  "Reviewing your journey",
];
const nextStage = {
  prepare_trip: 1,
  research_trip: 2,
  create_itinerary: 3,
  validate_and_price: 4,
  review_itinerary: 2,
};
const money = (value) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(value);
const localDate = (offset) => {
  const d = new Date();
  d.setDate(d.getDate() + offset);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};
const niceDate = (value) =>
  new Date(`${value}T12:00:00`).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
  });
function safeLink(url) {
  try {
    const parsed = new URL(url);
    return ["https:", "http:"].includes(parsed.protocol)
      ? parsed.href
      : undefined;
  } catch {
    return undefined;
  }
}

export default function App() {
  const [form, setForm] = useState({
    source_city: "Bengaluru",
    destination: "Goa",
    start_date: localDate(2),
    end_date: localDate(4),
    budget: 30000,
    passengers: 2,
    rooms: 1,
    food_allowance: 600,
    activity_allowance: 300,
    hotel_allowance: 2500,
    transport_mode: "Flight",
    hotel_type: "Budget",
    train_class: "3A",
    rail_distance_km: "",
    interests: ["Food", "Culture", "Beaches"],
  });
  const [loading, setLoading] = useState(false);
  const [stage, setStage] = useState(0);
  const [revision, setRevision] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [tab, setTab] = useState("Itinerary");
  const [photo, setPhoto] = useState(null);
  useEffect(() => {
    if ((loading || result || error) && window.innerWidth <= 800) {
      document
        .getElementById("journey-area")
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [loading, result, error]);
  const update = (e) =>
    setForm((previous) => ({ ...previous, [e.target.name]: e.target.value }));
  const toggle = (value) =>
    setForm((previous) => ({
      ...previous,
      interests: previous.interests.includes(value)
        ? previous.interests.filter((x) => x !== value)
        : [...previous.interests, value],
    }));
  const days =
    Math.round(
      (new Date(form.end_date) - new Date(form.start_date)) / 86400000,
    ) + 1;

  async function submit(event) {
    event.preventDefault();
    if (days < 1 || days > 30) {
      setError("Choose a trip between 1 and 30 days.");
      return;
    }
    setLoading(true);
    setError("");
    setResult(null);
    setStage(0);
    setRevision(0);
    setTab("Itinerary");
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 30 * 60 * 1000);
    try {
      const response = await fetch("/api/plan/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: controller.signal,
        body: JSON.stringify({
          ...form,
          passengers: Number(form.passengers),
          budget: Number(form.budget),
          rail_distance_km:
            form.transport_mode === "Train"
              ? Number(form.rail_distance_km)
              : null,
        }),
      });
      if (!response.ok) {
        const body = await response.json();
        throw new Error(
          Array.isArray(body.detail)
            ? body.detail.map((x) => x.msg).join(". ")
            : body.detail || "Unable to start planning.",
        );
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let received = false;
      function handle(line) {
        if (!line.trim()) return;
        const message = JSON.parse(line);
        if (message.type === "error") throw new Error(message.message);
        if (message.type === "stage") {
          setStage(nextStage[message.completed] ?? 0);
          if (message.revision_count != null)
            setRevision(message.revision_count);
        }
        if (message.type === "result") {
          setResult(message.data);
          received = true;
        }
      }
      while (true) {
        const { done, value } = await reader.read();
        buffer += decoder.decode(value, { stream: !done });
        const lines = buffer.split("\n");
        buffer = lines.pop();
        lines.forEach(handle);
        if (done) break;
      }
      handle(buffer);
      if (!received)
        throw new Error(
          "The connection ended before the plan was ready. Please try again.",
        );
    } catch (err) {
      setError(
        err.name === "AbortError"
          ? "Planning took too long. Please try a shorter trip."
          : err.message ||
              "Cannot reach the planner. Check that the backend is running.",
      );
    } finally {
      clearTimeout(timeout);
      setLoading(false);
    }
  }

  function download() {
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(result, null, 2)], { type: "application/json" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = `${result.metadata.destination}-itinerary.json`;
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="Voyage home">
          <span className="brand-mark">
            <Compass size={23} />
          </span>
          voyage<span className="brand-dot">.</span>
        </a>
        <span className="header-note">
          A little less planning. A lot more exploring.
        </span>
        <a className="header-link" href="#trip-form">
          Plan a journey <ArrowUpRight size={16} />
        </a>
      </header>
      <main>
        <section className="intro">
          <div>
            <div className="eyebrow">
              <span /> YOUR NEXT CHAPTER STARTS HERE
            </div>
            <h1>
              Go somewhere.
              <br />
              <em>Feel something.</em>
            </h1>
            <p>
              Tell us what your perfect escape looks like.
              <br />
              We’ll bring the details together, one day at a time.
            </p>
          </div>
          <div className="intro-aside">
            <span className="orbit">
              <Compass size={60} strokeWidth={1} />
            </span>
            <span>
              Thoughtfully planned.
              <br />
              Made for you.
            </span>
          </div>
        </section>
        <div className="workspace">
          <aside className="planner" id="trip-form">
            <div className="section-heading">
              <span className="eyebrow">THE STARTING POINT</span>
              <span className="tiny-tag">Your trip, your way</span>
            </div>
            <h2>Make room for a getaway.</h2>
            <form onSubmit={submit}>
              <fieldset disabled={loading}>
                <div className="route-fields">
                  <Field label="Where from?" icon={MapPin}>
                    <input
                      name="source_city"
                      value={form.source_city}
                      onChange={update}
                      required
                      maxLength={100}
                      autoComplete="address-level2"
                    />
                  </Field>
                  <span className="route-connector">↓</span>
                  <Field label="Where to?" icon={Compass}>
                    <input
                      name="destination"
                      value={form.destination}
                      onChange={update}
                      required
                      maxLength={100}
                    />
                  </Field>
                </div>
                <div className="two-cols">
                  <Field label="Departure" icon={CalendarDays}>
                    <input
                      name="start_date"
                      type="date"
                      value={form.start_date}
                      onChange={update}
                      required
                    />
                  </Field>
                  <Field label="Return" icon={CalendarDays}>
                    <input
                      name="end_date"
                      type="date"
                      min={form.start_date}
                      value={form.end_date}
                      onChange={update}
                      required
                    />
                  </Field>
                </div>
                <div className="two-cols">
                  <Field label="Trip budget · INR" icon={Wallet}>
                    <input
                      name="budget"
                      type="number"
                      min="0"
                      step="any"
                      value={form.budget}
                      onChange={update}
                      required
                    />
                  </Field>
                  <Field label="Travelers" icon={Users}>
                    <input
                      name="passengers"
                      type="number"
                      min="1"
                      max="100"
                      value={form.passengers}
                      onChange={update}
                      required
                    />
                  </Field>
                </div>
                <span className="field-label">How are you getting there?</span>
                <div className="segmented">
                  {[
                    [Plane, "Flight"],
                    [TrainFront, "Train"],
                  ].map(([Icon, mode]) => (
                    <button
                      key={mode}
                      type="button"
                      aria-pressed={form.transport_mode === mode}
                      className={form.transport_mode === mode ? "selected" : ""}
                      onClick={() => setForm({ ...form, transport_mode: mode })}
                    >
                      <Icon size={16} />
                      {mode}
                      {form.transport_mode === mode && <Check size={14} />}
                    </button>
                  ))}
                </div>
                {form.transport_mode === "Train" && (
                  <div className="train-fields">
                    <Field label="One-way railway distance · km">
                      <input
                        name="rail_distance_km"
                        type="number"
                        min="0.01"
                        step="any"
                        value={form.rail_distance_km}
                        onChange={update}
                        required
                      />
                    </Field>
                    <Field label="Train class">
                      <select
                        name="train_class"
                        value={form.train_class}
                        onChange={update}
                      >
                        {["SL", "3A", "2A", "1A"].map((x) => (
                          <option key={x}>{x}</option>
                        ))}
                      </select>
                    </Field>
                    <p className="helper">
                      Used for outward and return fare estimates. These are not
                      live ticket quotes.
                    </p>
                  </div>
                )}
                <Field label="Your stay style">
                  <select
                    name="hotel_type"
                    value={form.hotel_type}
                    onChange={update}
                  >
                    <option value="Budget">Simple & comfortable</option>
                    <option value="3-star">
                      A little extra comfort · 3 star
                    </option>
                    <option value="4-star">Something special · 4 star</option>
                    <option value="5-star">A touch of luxury · 5 star</option>
                  </select>
                </Field>
                <details className="allowance-settings">
                  <summary>
                    Spending allowances <span>Adjust estimates</span>
                  </summary>
                  <p className="helper">
                    Your planning amounts, not quoted prices. Applied when live
                    costs are missing.
                  </p>
                  <Field label="Food · INR per person per day">
                    <input
                      type="number"
                      min="0"
                      name="food_allowance"
                      value={form.food_allowance}
                      onChange={update}
                    />
                  </Field>
                  <Field label="Activities · INR per person per day">
                    <input
                      type="number"
                      min="0"
                      name="activity_allowance"
                      value={form.activity_allowance}
                      onChange={update}
                    />
                  </Field>
                  <Field label="Hotel · INR per room per night">
                    <input
                      type="number"
                      min="0"
                      name="hotel_allowance"
                      value={form.hotel_allowance}
                      onChange={update}
                    />
                  </Field>
                  <Field label="Rooms">
                    <input
                      type="number"
                      min="1"
                      max="100"
                      name="rooms"
                      value={form.rooms}
                      onChange={update}
                    />
                  </Field>
                </details>
                <span className="field-label">What brings you joy?</span>
                <div className="interest-chips">
                  {interests.map(([Icon, name]) => (
                    <button
                      type="button"
                      key={name}
                      aria-pressed={form.interests.includes(name)}
                      className={form.interests.includes(name) ? "active" : ""}
                      onClick={() => toggle(name)}
                    >
                      <Icon size={14} />
                      {name}
                    </button>
                  ))}
                </div>
                <button type="submit" className="primary">
                  {loading ? (
                    <>
                      <LoaderCircle className="spin" size={18} /> Planning your
                      escape
                    </>
                  ) : (
                    <>
                      Start planning <ArrowRight size={18} />
                    </>
                  )}
                </button>
                <p className="form-footnote">
                  {days > 0 && days <= 30
                    ? `${days} days of possibility`
                    : "Choose your travel dates"}{" "}
                  <span>·</span> No bookings made
                </p>
              </fieldset>
            </form>
          </aside>
          <section
            className="journey-area"
            id="journey-area"
            aria-live="polite"
            aria-busy={loading}
          >
            {error && (
              <div className="notice error" role="alert">
                <AlertCircle size={20} />
                <div>
                  <strong>We hit a little detour.</strong>
                  <p>{error}</p>
                </div>
              </div>
            )}
            {loading ? (
              <div className="progress-panel">
                <span className="eyebrow">GOOD THINGS TAKE A MOMENT</span>
                <Compass className="slow-spin" size={64} strokeWidth={1} />
                <h2>Your next story is taking shape.</h2>
                <p>
                  We’re researching your trip, arranging the days,
                  <br />
                  and giving the details a second look.
                </p>
                <ol className="progress-list">
                  {stages.map((label, i) => (
                    <li
                      key={label}
                      className={
                        stage === i ? "current" : stage > i ? "done" : ""
                      }
                    >
                      <span>
                        {stage > i ? (
                          <Check size={14} />
                        ) : stage === i ? (
                          <LoaderCircle size={14} className="spin" />
                        ) : (
                          i + 1
                        )}
                      </span>
                      {label}
                    </li>
                  ))}
                </ol>
                {revision > 0 && (
                  <p className="helper">
                    Refining your itinerary · revision {revision} of 2
                  </p>
                )}
                <p className="helper">
                  Longer trips can take several minutes. Keep this page open.
                </p>
              </div>
            ) : result ? (
              <>
                <div className="result-heading">
                  <div>
                    <span className="eyebrow">YOUR JOURNEY, ON PAPER</span>
                    <h2>
                      A little time in <em>{result.metadata.destination}.</em>
                    </h2>
                    <p>
                      {niceDate(result.metadata.start_date)} —{" "}
                      {niceDate(result.metadata.end_date)} ·{" "}
                      {result.metadata.total_days} days ·{" "}
                      {result.metadata.passengers} travelers
                    </p>
                  </div>
                  <button
                    className="icon-button"
                    onClick={download}
                    aria-label="Download itinerary"
                  >
                    <Download size={19} />
                  </button>
                </div>
                <div className="result-summary">
                  <span
                    className={`status ${result.metadata.planning_status === "FAILED" ? "failed" : ""}`}
                  >
                    {result.metadata.planning_status === "FAILED"
                      ? "Planning incomplete"
                      : result.metadata.planning_status === "PARTIAL"
                        ? "Itinerary & planning estimate"
                        : "Ready to explore"}
                  </span>
                  <span>
                    {result.metadata.review_status === "APPROVED"
                      ? "✓ Itinerary reviewed"
                      : "Review needs attention"}
                  </span>
                </div>
                {result.warnings.length > 0 && (
                  <details className="notice">
                    <summary>
                      <AlertCircle size={16} /> A few things to know (
                      {result.warnings.length})
                    </summary>
                    <ul>
                      {result.warnings.map((warning, i) => (
                        <li key={i}>{warning}</li>
                      ))}
                    </ul>
                  </details>
                )}
                {result.metadata.guide_mode === "SOURCE_GUIDE" && (
                  <p className="source-guide-note">
                    This guide uses verified destination sources. AI wording was
                    unavailable or could not be verified.
                  </p>
                )}
                <div className="tabs" role="tablist" aria-label="Trip details">
                  {["Itinerary", "Travel & stays", "Budget"].map((name) => (
                    <button
                      role="tab"
                      aria-selected={tab === name}
                      key={name}
                      onClick={() => setTab(name)}
                    >
                      {name}
                    </button>
                  ))}
                </div>
                <div role="tabpanel" aria-label={tab}>
                  {tab === "Itinerary" ? (
                    <div className="days">
                      {result.days.map((day) => (
                        <DayCard key={day.day} day={day} />
                      ))}
                    </div>
                  ) : tab === "Budget" ? (
                    <Budget budget={result.budget} />
                  ) : (
                    <Travel result={result} />
                  )}
                </div>
                <details className="activity">
                  <summary>Planning activity & review</summary>
                  <ol>
                    {result.agent_activity.map((item, i) => (
                      <li key={i}>{item}</li>
                    ))}
                  </ol>
                  {result.review?.issues?.map((issue, i) => (
                    <p key={i}>
                      {issue.problem} — {issue.suggested_fix}
                    </p>
                  ))}
                </details>
                <button
                  className="text-button"
                  onClick={() => {
                    setResult(null);
                    document
                      .getElementById("trip-form")
                      .scrollIntoView({ behavior: "smooth" });
                  }}
                >
                  <ArrowLeft size={15} /> Plan another escape
                </button>
              </>
            ) : (
              <>
                <DestinationPhoto onPhoto={setPhoto} photo={photo} />
                <div className="empty-copy">
                  <span className="eyebrow">
                    LESS RESEARCH. MORE DAYDREAMING.
                  </span>
                  <h2>
                    The best trips start
                    <br />
                    with a little curiosity.
                  </h2>
                  <p>
                    A seaside morning. A tucked-away café. A place you’ve
                    <br className="desktop-break" /> always wanted to see. Let’s
                    find your kind of journey.
                  </p>
                </div>
                <div className="benefits">
                  <div>
                    <MapPin size={20} />
                    <h3>Places with a story</h3>
                    <p>
                      Ideas shaped around
                      <br />
                      what you love.
                    </p>
                  </div>
                  <div>
                    <CalendarDays size={20} />
                    <h3>Days that flow</h3>
                    <p>
                      A thoughtful plan,
                      <br />
                      with places, food & local stories.
                    </p>
                  </div>
                  <div>
                    <Wallet size={20} />
                    <h3>Costs made clearer</h3>
                    <p>
                      See known prices
                      <br />
                      and what’s still missing.
                    </p>
                  </div>
                </div>
                <div className="editorial-note">
                  <span>01 /</span>
                  <p>
                    Go for the places.
                    <br />
                    <em>Stay for the feeling.</em>
                  </p>
                  <Compass size={35} strokeWidth={1} />
                </div>
              </>
            )}
          </section>
        </div>
        <footer>
          <span>
            voyage.{" "}
            <span className="muted">Made for the moments in between.</span>
          </span>
          <span>
            Explore thoughtfully <ArrowUpRight size={13} />
          </span>
        </footer>
      </main>
    </div>
  );
}

function Field({ label, icon: Icon, children }) {
  return (
    <label className="field">
      <span className="field-label">
        {Icon && <Icon size={13} />} {label}
      </span>
      {children}
    </label>
  );
}

function DestinationPhoto({ photo, onPhoto }) {
  // The optional photo endpoint keeps the provider key on the server.
  useEffect(() => {
    if (photo) return;
    const controller = new AbortController();
    fetch("/api/inspiration", { signal: controller.signal })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data?.url) onPhoto(data);
      })
      .catch(() => {});
    return () => controller.abort();
  }, [photo, onPhoto]);
  return (
    <div
      className={`destination-photo ${photo ? "has-photo" : ""}`}
      style={
        photo
          ? {
              backgroundImage: `linear-gradient(180deg, transparent 25%, rgba(13,40,33,.65)), url("${photo.url}")`,
            }
          : {}
      }
    >
      <div className="photo-top">
        <span>THE WORLD IS STILL FULL OF WONDER</span>
        <ArrowUpRight size={21} />
      </div>
      <div className="landscape-art" aria-hidden="true">
        <div className="sun-disc" />
        <div className="hill hill-back" />
        <div className="hill hill-front" />
        <div className="sea-lines" />
      </div>
      <div className="photo-bottom">
        <div>
          <span className="photo-kicker">A CHANGE OF SCENERY</span>
          <h2>
            Somewhere
            <br />
            you’ll remember.
          </h2>
        </div>
        <span className="photo-stamp">
          <Compass size={27} />
          <small>
            TAKE THE
            <br />
            SCENIC ROUTE
          </small>
        </span>
      </div>
      {photo && (
        <a
          className="photo-credit"
          href={safeLink(photo.photographer_url)}
          target="_blank"
          rel="noreferrer"
        >
          {photo.photographer} / Pexels
        </a>
      )}
    </div>
  );
}

function DayCard({ day }) {
  const visits = day.activities?.length ? day.activities : day.places || [];
  return (
    <article className="day-card guide-card">
      <header>
        <span className="day-number">{String(day.day).padStart(2, "0")}</span>
        <div>
          <span className="eyebrow">
            Day {day.day} · {niceDate(day.date)} · {day.location}
          </span>
          <h3>{day.title || `Discover ${day.location}`}</h3>
        </div>
        {day.weather?.success && (
          <span className="weather">
            <Sun size={15} />
            {day.weather.temperature}°C
          </span>
        )}
      </header>
      {day.highlights && (
        <div className="day-highlights">
          <span className="eyebrow">TODAY’S HIGHLIGHTS</span>
          <p>{day.highlights}</p>
        </div>
      )}
      <div className="guide-visits">
        <h4>
          <MapPin size={16} /> Places to visit & things to do
        </h4>
        {visits.length ? (
          visits.map((item, index) => (
            <section className="guide-visit" key={item.candidate_id}>
              <span className="visit-index">{index + 1}</span>
              <div>
                <h4>{item.name}</h4>
                <p>{item.why_visit || item.description}</p>
                {item.what_to_do && (
                  <p className="visit-advice">
                    <strong>What to do</strong> {item.what_to_do}
                  </p>
                )}
                <a
                  className="source-link"
                  href={safeLink(item.url)}
                  target="_blank"
                  rel="noreferrer"
                >
                  Read about this place on Wikipedia <ArrowUpRight size={12} />
                </a>
              </div>
            </section>
          ))
        ) : (
          <p className="helper">
            We couldn’t verify local attractions for this day. Try a more
            specific destination.
          </p>
        )}
      </div>
      {day.food?.length > 0 && (
        <div className="guide-food">
          <h4>
            <Utensils size={16} /> Foods to try
          </h4>
          {day.food.map((item) => (
            <div className="food-suggestion" key={item.candidate_id}>
              <a href={safeLink(item.url)} target="_blank" rel="noreferrer">
                {item.name} <ArrowUpRight size={12} />
              </a>
              <p>{item.what_to_try || item.description}</p>
            </div>
          ))}
        </div>
      )}
    </article>
  );
}

function Travel({ result }) {
  return (
    <div className="travel-details">
      <h3>The journey there & back</h3>
      {result.transport.length ? (
        result.transport.map((leg) => (
          <article className="travel-card" key={leg.id}>
            <Plane size={21} />
            <div>
              <h4>
                {leg.origin} → {leg.destination}
              </h4>
              <p>
                {niceDate(leg.departure_date)} · {leg.mode}
              </p>
              <p>
                {leg.result?.success
                  ? leg.result.price != null
                    ? `${leg.result.currency} ${leg.result.price.toLocaleString("en-IN")} · ${leg.result.source_type === "CONFIGURED_ESTIMATE" ? "Configured estimate" : "Provider price"}`
                    : "Price unavailable"
                  : leg.result?.reason || "Travel information unavailable"}
              </p>
              {leg.result?.fares && (
                <details>
                  <summary>Compare train classes</summary>
                  {leg.result.fares.map((fare) => (
                    <p key={fare.class}>
                      {fare.name}: {money(fare.party_total)} for your group
                    </p>
                  ))}
                </details>
              )}
            </div>
          </article>
        ))
      ) : (
        <p>No intercity journey required.</p>
      )}
      <h3>A place to settle in</h3>
      {result.accommodation.length ? (
        result.accommodation.map((stay) => (
          <article className="travel-card" key={stay.id}>
            <MapPin size={21} />
            <div>
              <h4>{stay.result?.success ? stay.result.name : stay.location}</h4>
              <p>
                {niceDate(stay.check_in)} — {niceDate(stay.check_out)} ·{" "}
                {stay.nights} nights
              </p>
              <p>
                {stay.result?.success
                  ? stay.result.total_price != null
                    ? `${stay.result.currency} ${stay.result.total_price.toLocaleString("en-IN")} total`
                    : "Stay total unavailable"
                  : stay.result?.reason || "Accommodation unavailable"}
              </p>
              {stay.result?.provider_quote != null && (
                <p>
                  Vendor quote: {money(stay.result.provider_quote)} · nightly or
                  full-stay basis unconfirmed; excluded from budget.
                </p>
              )}
            </div>
          </article>
        ))
      ) : (
        <p>No overnight stay needed for this trip.</p>
      )}
    </div>
  );
}

function Budget({ budget }) {
  const priced = budget.entries.filter((entry) => entry.amount !== null);
  const allowances = budget.planning_entries || [];
  const planned = budget.planning_total ?? budget.known_subtotal;
  const above = budget.user_budget > 0 && planned > budget.user_budget;
  return (
    <section className="budget-panel">
      <span className="eyebrow">A PRACTICAL PLAN FOR YOUR SPENDING</span>
      <h2>{money(planned)}</h2>
      <p>Planning total · known costs plus your spending allowances</p>
      <div className="budget-target">
        <span>Your trip budget</span>
        <strong>{money(budget.user_budget)}</strong>
      </div>
      <ul className="cost-list">
        {[...priced, ...allowances].map((entry, i) => (
          <li key={i}>
            <span>
              {entry.label}
              <small>
                {entry.provenance === "PLANNING_ALLOWANCE"
                  ? "Planning allowance · not a live quote"
                  : entry.provenance === "CONFIGURED_ESTIMATE"
                    ? "Configured fare estimate"
                    : "Provider price"}
              </small>
            </span>
            <strong>{money(entry.amount)}</strong>
          </li>
        ))}
      </ul>
      <div className={`budget-balance ${above ? "above" : ""}`}>
        <span>
          {budget.user_budget <= 0
            ? "No target budget set"
            : above
              ? "Above your planned budget"
              : "Room left in your planned budget"}
        </span>
        {budget.user_budget > 0 && (
          <strong>{money(Math.abs(budget.user_budget - planned))}</strong>
        )}
      </div>
      <p className="helper">
        Allowances cover the whole group and trip. You can change them in the
        trip form. Hotel allowances are used only where a confirmed stay price
        is missing.
      </p>
      <p className="budget-disclosure">
        This is a planning estimate, not a booking quote. Actual prices may
        vary.{" "}
        {budget.unpriced_categories?.includes("transport")
          ? "Transport without a price is excluded. "
          : ""}
        Wikipedia supports the place and food descriptions; it does not verify
        current prices.
      </p>
      <details className="budget-evidence">
        <summary>See confirmed costs and estimate details</summary>
        <p>
          Known subtotal: {money(budget.known_subtotal)}. Missing prices are
          replaced by the labelled allowances above where configured. No hotel
          is booked or guaranteed.
        </p>
      </details>
    </section>
  );
}
